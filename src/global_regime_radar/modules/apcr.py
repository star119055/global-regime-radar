from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np


@dataclass(frozen=True)
class APCRPanelContract:
    contract_version: str
    treatment_source: str
    outcome_source: str
    entity_level: str
    treatment_measure: str
    treatment_measurement_regime: str
    treatment_baseline_start: datetime
    treatment_baseline_end: datetime
    post_start_year: int
    minimum_entities: int = 4
    minimum_pre_periods: int = 2
    minimum_post_periods: int = 1

    def __post_init__(self) -> None:
        for name in ("treatment_baseline_start", "treatment_baseline_end"):
            value = getattr(self, name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.treatment_baseline_end < self.treatment_baseline_start:
            raise ValueError("treatment baseline end must be >= start")
        if self.minimum_entities < 2:
            raise ValueError("minimum_entities must be >= 2")
        if self.minimum_pre_periods < 1 or self.minimum_post_periods < 1:
            raise ValueError("minimum pre/post periods must be positive")



@dataclass(frozen=True)
class APCRTreatmentObservation:
    entity_id: str
    period_id: int
    ai_use_share: float
    strata_scope: str
    source_vintage_id: str
    standard_error_share: float | None = None

    def __post_init__(self) -> None:
        if not self.entity_id:
            raise ValueError("entity_id cannot be empty")
        if self.period_id <= 0:
            raise ValueError("period_id must be positive")
        if not 0.0 <= self.ai_use_share <= 1.0:
            raise ValueError("ai_use_share must be within [0, 1]")
        if self.standard_error_share is not None and self.standard_error_share < 0:
            raise ValueError("standard_error_share must be non-negative")
        if self.strata_scope != "national_naics2_total":
            raise ValueError("APCR treatment requires national_naics2_total scope")
        if not self.source_vintage_id:
            raise ValueError("source_vintage_id cannot be empty")


@dataclass(frozen=True)
class APCRFrozenTreatment:
    entity_id: str
    baseline_ai_intensity: float
    period_ids: tuple[int, ...]
    source_vintage_ids: tuple[str, ...]
    aggregation: str = "simple_mean"


def freeze_apcr_baseline_treatment(
    observations: list[APCRTreatmentObservation],
    *,
    required_period_ids: tuple[int, ...] = (31, 32, 33, 34, 35, 36),
    minimum_entities: int = 4,
) -> tuple[APCRFrozenTreatment, ...]:
    if len(set(required_period_ids)) != len(required_period_ids):
        raise ValueError("required_period_ids must be unique")
    required = set(required_period_ids)
    by_entity: dict[str, dict[int, APCRTreatmentObservation]] = {}

    for row in observations:
        if row.period_id not in required:
            raise ValueError(f"unexpected APCR baseline period {row.period_id}")
        entity = by_entity.setdefault(row.entity_id, {})
        if row.period_id in entity:
            raise ValueError(
                f"duplicate APCR treatment entity-period: {(row.entity_id, row.period_id)}"
            )
        entity[row.period_id] = row

    complete_entities = []
    for entity_id, periods in sorted(by_entity.items()):
        if set(periods) != required:
            missing = sorted(required - set(periods))
            raise ValueError(
                f"APCR treatment entity {entity_id} missing baseline periods {missing}"
            )
        ordered = [periods[period_id] for period_id in required_period_ids]
        complete_entities.append(
            APCRFrozenTreatment(
                entity_id=entity_id,
                baseline_ai_intensity=float(
                    np.mean([row.ai_use_share for row in ordered])
                ),
                period_ids=required_period_ids,
                source_vintage_ids=tuple(row.source_vintage_id for row in ordered),
            )
        )

    if len(complete_entities) < minimum_entities:
        raise ValueError(
            f"APCR treatment requires at least {minimum_entities} complete entities"
        )
    if len({round(row.baseline_ai_intensity, 12) for row in complete_entities}) < 2:
        raise ValueError("APCR treatment requires cross-entity intensity variation")
    return tuple(complete_entities)

@dataclass(frozen=True)
class APCRPanelObservation:
    entity_id: str
    year: int
    productivity: float
    baseline_ai_intensity: float
    post: bool
    treatment_measurement_regime: str
    treatment_vintage_id: str
    productivity_vintage_id: str

    def __post_init__(self) -> None:
        if not self.entity_id:
            raise ValueError("entity_id cannot be empty")
        if not 0.0 <= self.baseline_ai_intensity <= 1.0:
            raise ValueError("baseline_ai_intensity must be within [0, 1]")
        if not self.treatment_vintage_id:
            raise ValueError("treatment_vintage_id cannot be empty")
        if not self.productivity_vintage_id:
            raise ValueError("productivity_vintage_id cannot be empty")


@dataclass(frozen=True)
class APCRPanelValidation:
    n_observations: int
    n_entities: int
    n_periods: int
    n_pre_periods: int
    n_post_periods: int
    balanced_entities: tuple[str, ...]


@dataclass(frozen=True)
class APCRPanelResult:
    interaction_coefficient: float
    n_observations: int
    n_entities: int
    n_periods: int
    r_squared: float
    treatment_measurement_regime: str
    treatment_intensity_min: float
    treatment_intensity_max: float


def validate_apcr_panel(
    observations: list[APCRPanelObservation],
    contract: APCRPanelContract,
) -> APCRPanelValidation:
    if not observations:
        raise ValueError("APCR panel cannot be empty")

    seen_pairs: set[tuple[str, int]] = set()
    intensity_by_entity: dict[str, float] = {}
    periods_by_entity: dict[str, dict[str, set[int]]] = {}

    for row in observations:
        pair = (row.entity_id, row.year)
        if pair in seen_pairs:
            raise ValueError(f"duplicate APCR entity-period row: {pair}")
        seen_pairs.add(pair)

        if row.treatment_measurement_regime != contract.treatment_measurement_regime:
            raise ValueError(
                "APCR treatment measurement regime does not match frozen contract"
            )

        expected_post = row.year >= contract.post_start_year
        if row.post != expected_post:
            raise ValueError(
                f"APCR post flag disagrees with post_start_year for {pair}"
            )

        previous = intensity_by_entity.setdefault(
            row.entity_id,
            row.baseline_ai_intensity,
        )
        if not np.isclose(previous, row.baseline_ai_intensity):
            raise ValueError(
                "baseline AI treatment intensity must be frozen within entity"
            )

        buckets = periods_by_entity.setdefault(
            row.entity_id,
            {"pre": set(), "post": set()},
        )
        buckets["post" if row.post else "pre"].add(row.year)

    entities = sorted(periods_by_entity)
    if len(entities) < contract.minimum_entities:
        raise ValueError(
            f"APCR requires at least {contract.minimum_entities} aligned entities"
        )

    pre_periods = sorted({row.year for row in observations if not row.post})
    post_periods = sorted({row.year for row in observations if row.post})
    if len(pre_periods) < contract.minimum_pre_periods:
        raise ValueError(
            f"APCR requires at least {contract.minimum_pre_periods} pre periods"
        )
    if len(post_periods) < contract.minimum_post_periods:
        raise ValueError(
            f"APCR requires at least {contract.minimum_post_periods} post periods"
        )

    balanced = tuple(
        entity
        for entity in entities
        if periods_by_entity[entity]["pre"] and periods_by_entity[entity]["post"]
    )
    if len(balanced) != len(entities):
        missing = sorted(set(entities) - set(balanced))
        raise ValueError(
            "every APCR entity requires pre and post outcomes; missing="
            + ",".join(missing)
        )

    if len(set(intensity_by_entity.values())) < 2:
        raise ValueError("APCR requires cross-entity treatment-intensity variation")

    return APCRPanelValidation(
        n_observations=len(observations),
        n_entities=len(entities),
        n_periods=len({row.year for row in observations}),
        n_pre_periods=len(pre_periods),
        n_post_periods=len(post_periods),
        balanced_entities=balanced,
    )


def estimate_apcr_baseline_did(
    observations: list[APCRPanelObservation],
    contract: APCRPanelContract,
) -> APCRPanelResult:
    validation = validate_apcr_panel(observations, contract)

    entities = sorted({row.entity_id for row in observations})
    periods = sorted({row.year for row in observations})
    entity_index = {entity: index for index, entity in enumerate(entities)}
    period_index = {period: index for index, period in enumerate(periods)}

    rows: list[list[float]] = []
    outcomes: list[float] = []
    for observation in observations:
        design = [
            1.0,
            observation.baseline_ai_intensity * float(observation.post),
        ]
        design.extend(
            float(entity_index[observation.entity_id] == index)
            for index in range(1, len(entities))
        )
        design.extend(
            float(period_index[observation.year] == index)
            for index in range(1, len(periods))
        )
        rows.append(design)
        outcomes.append(observation.productivity)

    matrix = np.asarray(rows, dtype=float)
    outcome = np.asarray(outcomes, dtype=float)

    if np.linalg.matrix_rank(matrix) < matrix.shape[1]:
        raise ValueError("APCR baseline-treatment design matrix is rank deficient")

    coefficients, *_ = np.linalg.lstsq(matrix, outcome, rcond=None)
    fitted = matrix @ coefficients
    residual_sum = float(np.sum((outcome - fitted) ** 2))
    centered_sum = float(np.sum((outcome - np.mean(outcome)) ** 2))
    r_squared = 1.0 if centered_sum == 0 else 1.0 - residual_sum / centered_sum

    intensities = [row.baseline_ai_intensity for row in observations]
    return APCRPanelResult(
        interaction_coefficient=float(coefficients[1]),
        n_observations=validation.n_observations,
        n_entities=validation.n_entities,
        n_periods=validation.n_periods,
        r_squared=r_squared,
        treatment_measurement_regime=contract.treatment_measurement_regime,
        treatment_intensity_min=min(intensities),
        treatment_intensity_max=max(intensities),
    )


def apcr_ready_for_state_activation(
    *,
    panel_valid: bool,
    beta_normalization_frozen: bool,
    point_in_time_vintages_complete: bool,
    prospective_validation_passed: bool,
) -> bool:
    return all(
        (
            panel_valid,
            beta_normalization_frozen,
            point_in_time_vintages_complete,
            prospective_validation_passed,
        )
    )
