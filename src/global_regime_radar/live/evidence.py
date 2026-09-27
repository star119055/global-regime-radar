from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from global_regime_radar.data.contracts import Observation
from global_regime_radar.live.collector import LiveBundle
from global_regime_radar.regime.baseline import IndicatorEvidence

STATES = ("A", "B", "C1", "C2", "C3", "D")


@dataclass(frozen=True)
class LiveEvidenceItem:
    state: str
    key: str
    activation: float | None
    weight: float
    measurement_variance: float | None
    attribution_group: str
    evidence_ids: tuple[str, ...]
    note: str

    def __post_init__(self) -> None:
        if self.state not in STATES:
            raise ValueError(f"unsupported state {self.state!r}")
        if self.activation is not None and not 0.0 <= self.activation <= 1.0:
            raise ValueError("activation must be within [0, 1]")
        if self.weight <= 0:
            raise ValueError("weight must be positive")
        if self.measurement_variance is not None and self.measurement_variance < 0:
            raise ValueError("measurement_variance must be non-negative")

    def to_indicator_evidence(self) -> IndicatorEvidence:
        return IndicatorEvidence(
            key=self.key,
            activation=self.activation,
            weight=self.weight,
            measurement_variance=self.measurement_variance,
            attribution_group=self.attribution_group,
        )


@dataclass(frozen=True)
class GapItem:
    state: str
    key: str
    priority: str
    reason: str


@dataclass(frozen=True)
class LiveEvidenceDocument:
    as_of: datetime
    dataset_hash: str
    source_hashes: dict[str, str]
    items: tuple[LiveEvidenceItem, ...]
    source_failures: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        if not self.dataset_hash:
            raise ValueError("dataset_hash cannot be empty")

    @property
    def evidence(self) -> dict[str, list[IndicatorEvidence]]:
        grouped = {state: [] for state in STATES}
        for item in self.items:
            grouped[item.state].append(item.to_indicator_evidence())
        return grouped

    @property
    def gaps(self) -> tuple[str, ...]:
        gaps = [
            f"{item.state}:{item.key}:missing"
            for item in self.items
            if item.activation is None
        ]
        gaps.extend(f"source:{failure}" for failure in self.source_failures)
        return tuple(gaps)

    @property
    def state_coverage(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for state in STATES:
            rows = [item for item in self.items if item.state == state]
            total = sum(item.weight for item in rows)
            observed = sum(
                item.weight for item in rows if item.activation is not None
            )
            result[state] = observed / total if total else 0.0
        return result

    @property
    def gap_inventory(self) -> tuple[GapItem, ...]:
        priorities = {
            "A": "CRITICAL",
            "B": "MEDIUM",
            "C1": "HIGH",
            "C2": "HIGH",
            "C3": "CRITICAL",
            "D": "MEDIUM",
        }
        return tuple(
            GapItem(
                state=item.state,
                key=item.key,
                priority=priorities[item.state],
                reason=item.note,
            )
            for item in self.items
            if item.activation is None
        )


def _series(
    observations: tuple[Observation, ...],
    feature_id: str,
) -> list[tuple[datetime, float, tuple[str, ...]]]:
    rows: list[tuple[datetime, float, tuple[str, ...]]] = []
    for obs in observations:
        if (
            obs.feature_id == feature_id
            and obs.value is not None
            and obs.observation_start is not None
        ):
            rows.append((obs.observation_start, float(obs.value), (obs.observation_id,)))
    rows.sort(key=lambda row: row[0])
    return rows


def _sofr_dispersion_series(
    observations: tuple[Observation, ...],
) -> list[tuple[datetime, float, tuple[str, ...]]]:
    low = {
        obs.observation_start: obs
        for obs in observations
        if obs.feature_id == "sofr_percentile_1"
        and obs.value is not None
        and obs.observation_start is not None
    }
    high = {
        obs.observation_start: obs
        for obs in observations
        if obs.feature_id == "sofr_percentile_99"
        and obs.value is not None
        and obs.observation_start is not None
    }
    rows = []
    for observed in sorted(set(low) & set(high)):
        low_obs = low[observed]
        high_obs = high[observed]
        rows.append(
            (
                observed,
                float(high_obs.value) - float(low_obs.value),
                (low_obs.observation_id, high_obs.observation_id),
            )
        )
    return rows


def _auction_ratio_series(
    observations: tuple[Observation, ...],
    numerator_feature: str,
    denominator_feature: str,
) -> list[tuple[datetime, float, tuple[str, ...]]]:
    numerators = {
        (obs.entity_id, obs.observation_start): obs
        for obs in observations
        if obs.feature_id == numerator_feature
        and obs.value is not None
        and obs.observation_start is not None
    }
    denominators = {
        (obs.entity_id, obs.observation_start): obs
        for obs in observations
        if obs.feature_id == denominator_feature
        and obs.value is not None
        and obs.observation_start is not None
        and float(obs.value) > 0
    }
    rows = []
    for key in sorted(set(numerators) & set(denominators), key=lambda x: x[1]):
        numerator = numerators[key]
        denominator = denominators[key]
        rows.append(
            (
                key[1],
                float(numerator.value) / float(denominator.value),
                (numerator.observation_id, denominator.observation_id),
            )
        )
    return rows


def _issuance_duration_series(
    observations: tuple[Observation, ...],
) -> list[tuple[datetime, float, tuple[str, ...]]]:
    terms = {
        (obs.entity_id, obs.observation_start): obs
        for obs in observations
        if obs.feature_id == "auction_original_term_years"
        and obs.value is not None
        and obs.observation_start is not None
    }
    accepted = {
        (obs.entity_id, obs.observation_start): obs
        for obs in observations
        if obs.feature_id == "auction_total_accepted"
        and obs.value is not None
        and obs.observation_start is not None
        and float(obs.value) > 0
    }

    monthly: dict[tuple[int, int], list[tuple[Observation, Observation]]] = defaultdict(list)
    for key in set(terms) & set(accepted):
        observed = key[1]
        monthly[(observed.year, observed.month)].append((terms[key], accepted[key]))

    rows = []
    for month in sorted(monthly):
        pairs = monthly[month]
        total_amount = sum(float(amount.value) for _, amount in pairs)
        if total_amount <= 0:
            continue
        weighted_years = sum(
            float(term.value) * float(amount.value) for term, amount in pairs
        ) / total_amount
        as_of = max(term.observation_start for term, _ in pairs)
        evidence_ids = tuple(
            identifier
            for term, amount in pairs
            for identifier in (term.observation_id, amount.observation_id)
        )
        rows.append((as_of, weighted_years, evidence_ids))
    return rows


def _paired_mean_series(
    observations: tuple[Observation, ...],
    feature_ids: tuple[str, str],
) -> list[tuple[datetime, float, tuple[str, ...]]]:
    series = []
    for feature_id in feature_ids:
        series.append(
            {
                obs.observation_start: obs
                for obs in observations
                if obs.feature_id == feature_id
                and obs.value is not None
                and obs.observation_start is not None
            }
        )

    rows = []
    for observed in sorted(set(series[0]) & set(series[1])):
        left = series[0][observed]
        right = series[1][observed]
        rows.append(
            (
                observed,
                (float(left.value) + float(right.value)) / 2.0,
                (left.observation_id, right.observation_id),
            )
        )
    return rows


def _lbnl_execution_item(
    observations: tuple[Observation, ...],
    *,
    as_of: datetime,
    base_variance: float = 0.04,
    half_life_days: float = 365.0,
) -> LiveEvidenceItem:
    required = {
        "lbnl_active_generation_gw",
        "lbnl_active_storage_gw",
        "lbnl_draft_executed_ia_gw",
    }
    latest: dict[str, Observation] = {}
    for obs in observations:
        if (
            obs.feature_id in required
            and obs.value is not None
            and obs.observation_start is not None
        ):
            prior = latest.get(obs.feature_id)
            if prior is None or obs.observation_start > prior.observation_start:
                latest[obs.feature_id] = obs

    if set(latest) != required:
        return _missing(
            "C3",
            "interconnection_execution",
            "grid_execution",
            "LBNL annual advanced-stage interconnection snapshot is unavailable.",
        )

    generation = float(latest["lbnl_active_generation_gw"].value)
    storage = float(latest["lbnl_active_storage_gw"].value)
    ia_capacity = float(latest["lbnl_draft_executed_ia_gw"].value)
    active_total = generation + storage
    if active_total <= 0:
        return _missing(
            "C3",
            "interconnection_execution",
            "grid_execution",
            "LBNL active queue capacity is non-positive.",
        )

    activation = max(0.0, min(1.0, ia_capacity / active_total))
    observed = max(
        obs.observation_start for obs in latest.values() if obs.observation_start
    )
    age_days = max(0.0, (as_of - observed).total_seconds() / 86400.0)
    freshness = math.exp(-math.log(2.0) * age_days / half_life_days)
    measurement_variance = min(1.0, base_variance / max(freshness, 1e-6))

    return LiveEvidenceItem(
        state="C3",
        key="interconnection_execution",
        activation=activation,
        weight=1.0,
        measurement_variance=measurement_variance,
        attribution_group="grid_execution",
        evidence_ids=tuple(
            latest[key].observation_id for key in sorted(required)
        ),
        note=(
            "Annual LBNL advanced-stage execution proxy: draft/executed IA "
            "capacity divided by active generation plus storage queue capacity; "
            "IA is not COD, and annual freshness inflates measurement variance."
        ),
    )


def _robust_activation(
    rows: list[tuple[datetime, float, tuple[str, ...]]],
    *,
    direction: float,
    minimum_points: int = 8,
) -> tuple[float | None, float | None, tuple[str, ...]]:
    if len(rows) < minimum_points:
        return None, None, ()

    values = [row[1] for row in rows]
    center = statistics.median(values[:-1] or values)
    absolute_deviations = [abs(value - center) for value in values[:-1] or values]
    mad = statistics.median(absolute_deviations)
    scale = 1.4826 * mad

    if scale <= 1e-12:
        scale = statistics.pstdev(values[:-1] or values)
    if scale <= 1e-12:
        return None, None, ()

    z_score = direction * (values[-1] - center) / scale
    z_score = max(-4.0, min(4.0, z_score))
    activation = 1.0 / (1.0 + math.exp(-z_score))
    measurement_variance = max(0.01, 1.0 / min(len(values), 100))
    return activation, measurement_variance, rows[-1][2]


def _item(
    state: str,
    key: str,
    rows: list[tuple[datetime, float, tuple[str, ...]]],
    *,
    direction: float,
    group: str,
    note: str,
    minimum_points: int = 8,
) -> LiveEvidenceItem:
    activation, variance, evidence_ids = _robust_activation(
        rows,
        direction=direction,
        minimum_points=minimum_points,
    )
    return LiveEvidenceItem(
        state=state,
        key=key,
        activation=activation,
        weight=1.0,
        measurement_variance=variance,
        attribution_group=group,
        evidence_ids=evidence_ids,
        note=note,
    )


def _missing(state: str, key: str, group: str, note: str) -> LiveEvidenceItem:
    return LiveEvidenceItem(
        state=state,
        key=key,
        activation=None,
        weight=1.0,
        measurement_variance=None,
        attribution_group=group,
        evidence_ids=(),
        note=note,
    )


def build_live_evidence(bundle: LiveBundle) -> LiveEvidenceDocument:
    observations = bundle.observations

    items = (
        _missing(
            "A",
            "apcr",
            "ai_productivity",
            "AI-specific productivity realization is not supplied by generic productivity data.",
        ),
        _missing(
            "A",
            "llier",
            "ai_grid_execution",
            "Large-load interconnection execution source is not connected in live v2.",
        ),
        _missing(
            "A",
            "ai_capital_cycle",
            "ai_capital_cycle",
            "GPU / AI capital-cycle live evidence is not connected in live v2.",
        ),
        _item(
            "B",
            "repo_usage_stress",
            _series(observations, "repo_total_accepted"),
            direction=1.0,
            group="repo_usage",
            note="Higher repo facility usage relative to its recent distribution increases B pressure.",
        ),
        _item(
            "B",
            "sofr_dispersion_stress",
            _sofr_dispersion_series(observations),
            direction=1.0,
            group="sofr_distribution",
            note="Wider SOFR 99th-minus-1st percentile dispersion increases funding stress.",
        ),
        _item(
            "B",
            "auction_quality_stress",
            _series(observations, "auction_bid_to_cover"),
            direction=-1.0,
            group="treasury_auction_quality",
            note="Lower bid-to-cover relative to the recent live sample increases B pressure.",
        ),
        _item(
            "B",
            "auction_dealer_takedown_stress",
            _auction_ratio_series(
                observations,
                "auction_primary_dealer_accepted",
                "auction_total_accepted",
            ),
            direction=1.0,
            group="treasury_auction_dealer_takedown",
            note="Higher primary-dealer take-down share at auction is an independent B pressure proxy.",
        ),
        _missing(
            "B",
            "dealer_balance_sheet",
            "dealer_balance_sheet",
            "Broader primary-dealer balance-sheet live series is not yet wired.",
        ),
        _missing(
            "C1",
            "hormuz_disruption",
            "hormuz",
            "No live physical-flow / insurance feed is connected.",
        ),
        _missing(
            "C1",
            "crop_balance",
            "crop_balance",
            "USDA PSD requires a configured API key and is not silently substituted.",
        ),
        _missing(
            "C1",
            "hydro_gas",
            "hydro_gas",
            "EIA live energy data requires a configured API key.",
        ),
        _missing(
            "C2",
            "external_debt_stress",
            "external_debt",
            "High-frequency external sovereign vulnerability feed is not connected.",
        ),
        _missing(
            "C2",
            "reserve_adequacy",
            "reserve_adequacy",
            "IMF reserve-template live adapter is not connected.",
        ),
        _missing(
            "C2",
            "fx_stress",
            "fx_stress",
            "Point-in-time FX stress adapter is not connected.",
        ),
        _missing(
            "C3",
            "transformer_lead_time",
            "transformer_supply",
            "Live transformer / switchgear lead-time source is not connected.",
        ),
        _item(
            "C3",
            "capex_deflator",
            _paired_mean_series(
                observations,
                ("transformer_industry_ppi", "switchgear_industry_ppi"),
            ),
            direction=1.0,
            group="capex_cost",
            note=(
                "Higher BLS transformer/switchgear producer prices relative to "
                "their recent distribution increase C3 cost pressure."
            ),
        ),
        _lbnl_execution_item(
            observations,
            as_of=bundle.retrieved_at,
        ),
        _item(
            "D",
            "real_yield_repression",
            _series(observations, "treasury_real_yield_10y"),
            direction=-1.0,
            group="real_yield",
            note="Lower 10Y real yield relative to its recent live sample is a partial D proxy.",
        ),
        _item(
            "D",
            "issuance_duration",
            _issuance_duration_series(observations),
            direction=-1.0,
            group="treasury_issuance",
            note="Shorter accepted-amount-weighted Treasury auction duration increases D pressure.",
            minimum_points=4,
        ),
        _missing(
            "D",
            "regulatory_intervention",
            "regulatory_intervention",
            "Regulatory / reserve intervention remains event-driven and is not auto-inferred.",
        ),
        _missing(
            "D",
            "asset_gap",
            "financial_repression_asset_gap",
            "Gold / USD / real-yield asset-gap composite is not yet wired.",
        ),
    )

    source_hashes = {
        vintage.source_id: vintage.source_hash for vintage in bundle.vintages
    }
    failures = tuple(
        f"{failure.source}:{failure.error_type}:{failure.message}"
        for failure in bundle.source_failures
    )
    return LiveEvidenceDocument(
        as_of=bundle.retrieved_at,
        dataset_hash=bundle.dataset_hash,
        source_hashes=source_hashes,
        items=items,
        source_failures=failures,
    )


def document_payload(document: LiveEvidenceDocument) -> dict[str, object]:
    return {
        "as_of": document.as_of.isoformat(),
        "dataset_hash": document.dataset_hash,
        "source_hashes": document.source_hashes,
        "items": [asdict(item) for item in document.items],
        "source_failures": list(document.source_failures),
        "gaps": list(document.gaps),
        "state_coverage": document.state_coverage,
        "gap_inventory": [asdict(item) for item in document.gap_inventory],
    }


def write_document(document: LiveEvidenceDocument, path: Path) -> None:
    path.write_text(
        json.dumps(
            document_payload(document),
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def load_document(path: Path) -> LiveEvidenceDocument:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return LiveEvidenceDocument(
        as_of=datetime.fromisoformat(payload["as_of"]),
        dataset_hash=payload["dataset_hash"],
        source_hashes=dict(payload["source_hashes"]),
        items=tuple(LiveEvidenceItem(**item) for item in payload["items"]),
        source_failures=tuple(payload.get("source_failures", [])),
    )
