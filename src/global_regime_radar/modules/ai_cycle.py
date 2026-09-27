from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class APCRObservation:
    entity_id: str
    period: str
    productivity: float
    ai_intensity: float
    post: bool


@dataclass(frozen=True)
class APCRResult:
    interaction_coefficient: float
    n_observations: int
    n_entities: int
    n_periods: int
    r_squared: float


def estimate_apcr_did(observations: list[APCRObservation]) -> APCRResult:
    if len(observations) < 4:
        raise ValueError("APCR requires at least four observations")

    entities = sorted({row.entity_id for row in observations})
    periods = sorted({row.period for row in observations})
    if len(entities) < 2:
        raise ValueError("APCR requires at least two entities")
    if len(periods) < 2:
        raise ValueError("APCR requires at least two periods")
    if len({row.post for row in observations}) < 2:
        raise ValueError("APCR requires both pre and post observations")

    entity_index = {entity: index for index, entity in enumerate(entities)}
    period_index = {period: index for index, period in enumerate(periods)}

    rows: list[list[float]] = []
    outcomes: list[float] = []
    for observation in observations:
        design = [
            1.0,
            observation.ai_intensity * float(observation.post),
        ]
        design.extend(
            float(entity_index[observation.entity_id] == index)
            for index in range(1, len(entities))
        )
        design.extend(
            float(period_index[observation.period] == index)
            for index in range(1, len(periods))
        )
        rows.append(design)
        outcomes.append(observation.productivity)

    matrix = np.asarray(rows, dtype=float)
    outcome = np.asarray(outcomes, dtype=float)

    if np.linalg.matrix_rank(matrix) < matrix.shape[1]:
        raise ValueError("APCR design matrix is rank deficient")

    coefficients, *_ = np.linalg.lstsq(matrix, outcome, rcond=None)
    fitted = matrix @ coefficients
    residual_sum = float(np.sum((outcome - fitted) ** 2))
    centered_sum = float(np.sum((outcome - np.mean(outcome)) ** 2))
    r_squared = 1.0 if centered_sum == 0 else 1.0 - residual_sum / centered_sum

    return APCRResult(
        interaction_coefficient=float(coefficients[1]),
        n_observations=len(observations),
        n_entities=len(entities),
        n_periods=len(periods),
        r_squared=r_squared,
    )


def geoi_score(
    *,
    performance_per_dollar_change_z: float | None,
    old_gpu_rental_yield_change_z: float | None,
    secondary_gpu_price_change_z: float | None,
) -> float | None:
    components = (
        performance_per_dollar_change_z,
        old_gpu_rental_yield_change_z,
        secondary_gpu_price_change_z,
    )
    if any(component is None for component in components):
        return None

    assert performance_per_dollar_change_z is not None
    assert old_gpu_rental_yield_change_z is not None
    assert secondary_gpu_price_change_z is not None

    return (
        0.40 * performance_per_dollar_change_z
        - 0.35 * old_gpu_rental_yield_change_z
        - 0.25 * secondary_gpu_price_change_z
    )


def pccb_score(
    *,
    non_accrual_z: float | None,
    pik_z: float | None,
    nav_markdown_z: float | None,
    gates_z: float | None,
) -> float | None:
    components = (non_accrual_z, pik_z, nav_markdown_z, gates_z)
    if any(component is None for component in components):
        return None

    assert non_accrual_z is not None
    assert pik_z is not None
    assert nav_markdown_z is not None
    assert gates_z is not None

    return (
        0.35 * non_accrual_z
        + 0.25 * pik_z
        + 0.25 * nav_markdown_z
        + 0.15 * gates_z
    )


@dataclass(frozen=True)
class GPUCreditBridge:
    initial_ltv: float
    collateral_price_change: float
    stressed_ltv: float
    ltv_change: float


def gpu_collateral_bridge(
    initial_ltv: float,
    collateral_price_change: float,
) -> GPUCreditBridge:
    if initial_ltv < 0:
        raise ValueError("initial_ltv must be non-negative")
    if collateral_price_change <= -1.0:
        raise ValueError("collateral_price_change must be greater than -1")

    stressed_ltv = initial_ltv / (1.0 + collateral_price_change)
    return GPUCreditBridge(
        initial_ltv=initial_ltv,
        collateral_price_change=collateral_price_change,
        stressed_ltv=stressed_ltv,
        ltv_change=stressed_ltv - initial_ltv,
    )
