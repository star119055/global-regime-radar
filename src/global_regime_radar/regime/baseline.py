from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class IndicatorEvidence:
    key: str
    activation: float | None
    weight: float
    measurement_variance: float | None = None
    attribution_group: str | None = None

    def __post_init__(self) -> None:
        if self.weight <= 0 or not isfinite(self.weight):
            raise ValueError("weight must be finite and positive")
        if self.activation is not None and not 0.0 <= self.activation <= 1.0:
            raise ValueError("activation must be within [0, 1]")
        if self.measurement_variance is not None and self.measurement_variance < 0:
            raise ValueError("measurement_variance must be non-negative")


@dataclass(frozen=True)
class StateEstimate:
    state: str
    value: float
    coverage: float
    observed_composite: float | None
    variance: float
    confidence: str
    observed_weight: float
    configured_weight: float


def _confidence(coverage: float, variance: float) -> str:
    if coverage >= 0.75 and variance <= 0.04:
        return "High"
    if coverage >= 0.40 and variance <= 0.10:
        return "Medium"
    return "Low"


def estimate_state(
    state: str,
    evidence: list[IndicatorEvidence],
    *,
    prior: float = 0.5,
    prior_variance: float = 0.09,
) -> StateEstimate:
    if not 0.0 <= prior <= 1.0:
        raise ValueError("prior must be within [0, 1]")
    if prior_variance < 0:
        raise ValueError("prior_variance must be non-negative")
    if not evidence:
        raise ValueError("evidence configuration cannot be empty")

    configured_weight = sum(item.weight for item in evidence)
    observed = [item for item in evidence if item.activation is not None]
    observed_weight = sum(item.weight for item in observed)
    coverage = observed_weight / configured_weight

    groups: set[str] = set()
    for item in observed:
        group = item.attribution_group
        if group is None:
            continue
        if group in groups:
            raise ValueError(
                f"duplicate attribution_group {group!r} for state {state}"
            )
        groups.add(group)

    if not observed:
        return StateEstimate(
            state=state,
            value=prior,
            coverage=0.0,
            observed_composite=None,
            variance=prior_variance,
            confidence="Low",
            observed_weight=0.0,
            configured_weight=configured_weight,
        )

    observed_composite = (
        sum(item.weight * float(item.activation) for item in observed)
        / observed_weight
    )

    observed_variance = (
        sum(
            item.weight * (
                item.measurement_variance
                if item.measurement_variance is not None
                else 0.0
            )
            for item in observed
        )
        / observed_weight
    )

    value = coverage * observed_composite + (1.0 - coverage) * prior

    # Mixture variance: uncertainty within each component plus uncertainty
    # introduced by disagreement between observed evidence and the prior.
    variance = (
        coverage * observed_variance
        + (1.0 - coverage) * prior_variance
        + coverage * (1.0 - coverage) * (observed_composite - prior) ** 2
    )

    return StateEstimate(
        state=state,
        value=value,
        coverage=coverage,
        observed_composite=observed_composite,
        variance=variance,
        confidence=_confidence(coverage, variance),
        observed_weight=observed_weight,
        configured_weight=configured_weight,
    )


def estimate_regime(
    state_evidence: dict[str, list[IndicatorEvidence]],
    *,
    priors: dict[str, float] | None = None,
    prior_variances: dict[str, float] | None = None,
) -> dict[str, StateEstimate]:
    priors = priors or {}
    prior_variances = prior_variances or {}
    expected_states = ("A", "B", "C1", "C2", "C3", "D")
    missing = [state for state in expected_states if state not in state_evidence]
    if missing:
        raise ValueError(f"missing state configurations: {', '.join(missing)}")

    return {
        state: estimate_state(
            state,
            state_evidence[state],
            prior=priors.get(state, 0.5),
            prior_variance=prior_variances.get(state, 0.09),
        )
        for state in expected_states
    }
