import math


def freshness(age_days: float, half_life_days: float) -> float:
    if half_life_days <= 0:
        raise ValueError("half_life_days must be positive")
    age_days = max(age_days, 0.0)
    return math.exp(-math.log(2.0) * age_days / half_life_days)


def measurement_variance(
    base_variance: float,
    freshness_value: float,
    confidence: float,
    epsilon: float = 1e-6,
) -> float:
    if base_variance < 0:
        raise ValueError("base_variance must be non-negative")
    effective_weight = max(freshness_value * confidence, epsilon)
    return base_variance / effective_weight
