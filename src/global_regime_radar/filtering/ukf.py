from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import log

import numpy as np
from scipy.special import expit

from global_regime_radar.regime.baseline import StateEstimate
from global_regime_radar.regime.dynamics import Coupling, Jump, persistence_coefficient

STATE_ORDER = ("A", "B", "C1", "C2", "C3", "D")
_STATE_INDEX = {state: index for index, state in enumerate(STATE_ORDER)}
_EPS = 1e-8


@dataclass(frozen=True)
class UKFState:
    mean: np.ndarray
    covariance: np.ndarray
    as_of: datetime

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        if self.mean.shape != (6,):
            raise ValueError("mean must have shape (6,)")
        if self.covariance.shape != (6, 6):
            raise ValueError("covariance must have shape (6, 6)")
        if not np.all(np.isfinite(self.mean)):
            raise ValueError("mean must be finite")
        if not np.all(np.isfinite(self.covariance)):
            raise ValueError("covariance must be finite")


@dataclass(frozen=True)
class RegimeMeasurement:
    state: str
    value: float
    variance: float
    coverage: float = 1.0

    def __post_init__(self) -> None:
        if self.state not in _STATE_INDEX:
            raise ValueError(f"unsupported state {self.state!r}")
        if not 0.0 <= self.value <= 1.0:
            raise ValueError("measurement value must be within [0, 1]")
        if self.variance <= 0:
            raise ValueError("measurement variance must be positive")
        if not 0.0 < self.coverage <= 1.0:
            raise ValueError("measurement coverage must be within (0, 1]")


@dataclass(frozen=True)
class FilteredState:
    state: str
    value: float
    variance: float
    ci_low: float
    ci_high: float
    confidence: str


def _clip_activation(values: np.ndarray) -> np.ndarray:
    return np.clip(values, _EPS, 1.0 - _EPS)


def _logit(values: np.ndarray) -> np.ndarray:
    values = _clip_activation(values)
    return np.log(values / (1.0 - values))


def _weights(
    dimension: int,
    *,
    alpha: float,
    beta: float,
    kappa: float,
) -> tuple[float, np.ndarray, np.ndarray]:
    if alpha <= 0:
        raise ValueError("alpha must be positive")
    lam = alpha**2 * (dimension + kappa) - dimension
    scale = dimension + lam
    if scale <= 0:
        raise ValueError("sigma-point scale must be positive")

    mean_weights = np.full(2 * dimension + 1, 1.0 / (2.0 * scale))
    covariance_weights = mean_weights.copy()
    mean_weights[0] = lam / scale
    covariance_weights[0] = mean_weights[0] + (1.0 - alpha**2 + beta)
    return scale, mean_weights, covariance_weights


def _positive_semidefinite(matrix: np.ndarray, floor: float = 1e-12) -> np.ndarray:
    symmetric = (matrix + matrix.T) / 2.0
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    eigenvalues = np.maximum(eigenvalues, floor)
    return (eigenvectors * eigenvalues) @ eigenvectors.T


def _sigma_points(
    mean: np.ndarray,
    covariance: np.ndarray,
    *,
    alpha: float,
    beta: float,
    kappa: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dimension = mean.size
    scale, mean_weights, covariance_weights = _weights(
        dimension,
        alpha=alpha,
        beta=beta,
        kappa=kappa,
    )
    covariance = _positive_semidefinite(covariance)
    root = np.linalg.cholesky(scale * covariance)

    points = np.empty((2 * dimension + 1, dimension))
    points[0] = mean
    for index in range(dimension):
        points[index + 1] = mean + root[:, index]
        points[dimension + index + 1] = mean - root[:, index]

    return points, mean_weights, covariance_weights


def _unscented_moments(
    values: np.ndarray,
    mean_weights: np.ndarray,
    covariance_weights: np.ndarray,
    additive_covariance: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    mean = np.sum(values * mean_weights[:, None], axis=0)
    residuals = values - mean
    covariance = np.zeros((mean.size, mean.size))
    for index, weight in enumerate(covariance_weights):
        covariance += weight * np.outer(residuals[index], residuals[index])
    if additive_covariance is not None:
        covariance += additive_covariance
    return mean, _positive_semidefinite(covariance)


def initialize_filter(
    values: dict[str, float],
    variances: dict[str, float],
    *,
    as_of: datetime,
) -> UKFState:
    missing = [state for state in STATE_ORDER if state not in values or state not in variances]
    if missing:
        raise ValueError(f"missing initialization states: {', '.join(missing)}")

    activation = np.array([values[state] for state in STATE_ORDER], dtype=float)
    if np.any((activation < 0.0) | (activation > 1.0)):
        raise ValueError("initial activation values must be within [0, 1]")

    latent_mean = _logit(activation)
    latent_variances: list[float] = []
    for state, value in zip(STATE_ORDER, activation, strict=True):
        variance = variances[state]
        if variance < 0:
            raise ValueError("initial variances must be non-negative")
        derivative = max(float(value * (1.0 - value)), 1e-4)
        latent_variance = variance / (derivative**2)
        latent_variances.append(min(max(latent_variance, 1e-8), 25.0))

    return UKFState(
        mean=latent_mean,
        covariance=np.diag(latent_variances),
        as_of=as_of,
    )


def measurement_from_estimate(
    estimate: StateEstimate,
    *,
    minimum_variance: float = 1e-6,
    minimum_coverage: float = 0.05,
) -> RegimeMeasurement | None:
    if estimate.observed_composite is None or estimate.coverage <= 0.0:
        return None
    effective_coverage = max(estimate.coverage, minimum_coverage)
    effective_variance = max(
        estimate.variance / effective_coverage,
        minimum_variance,
    )
    return RegimeMeasurement(
        state=estimate.state,
        value=estimate.observed_composite,
        variance=effective_variance,
        coverage=estimate.coverage,
    )


def _transition_sigma(
    latent: np.ndarray,
    *,
    delta_days: float,
    half_life_days: dict[str, float],
    couplings: list[Coupling],
    jumps: list[Jump],
) -> np.ndarray:
    activation = expit(latent)
    updated = activation.copy()

    for coupling in couplings:
        if coupling.source not in _STATE_INDEX or coupling.target not in _STATE_INDEX:
            raise ValueError("coupling references unsupported state")
        source_index = _STATE_INDEX[coupling.source]
        target_index = _STATE_INDEX[coupling.target]
        phi = persistence_coefficient(delta_days, half_life_days[coupling.target])
        updated[target_index] += (
            (1.0 - phi)
            * coupling.coefficient
            * (activation[source_index] - 0.5)
        )

    for jump in jumps:
        if jump.state not in _STATE_INDEX:
            raise ValueError(f"unsupported jump state {jump.state!r}")
        updated[_STATE_INDEX[jump.state]] += jump.magnitude

    return _logit(_clip_activation(updated))


def predict(
    state: UKFState,
    *,
    as_of: datetime,
    half_life_days: dict[str, float],
    process_variance_per_day: dict[str, float],
    couplings: list[Coupling] | None = None,
    jumps: list[Jump] | None = None,
    alpha: float = 0.3,
    beta: float = 2.0,
    kappa: float = 0.0,
) -> UKFState:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    delta_days = (as_of - state.as_of).total_seconds() / 86400.0
    if delta_days < 0:
        raise ValueError("as_of cannot move backwards")

    for key in STATE_ORDER:
        if key not in half_life_days or key not in process_variance_per_day:
            raise ValueError(f"missing filter configuration for {key}")
        if process_variance_per_day[key] < 0:
            raise ValueError("process variance must be non-negative")

    points, mean_weights, covariance_weights = _sigma_points(
        state.mean,
        state.covariance,
        alpha=alpha,
        beta=beta,
        kappa=kappa,
    )
    transformed = np.array(
        [
            _transition_sigma(
                point,
                delta_days=delta_days,
                half_life_days=half_life_days,
                couplings=couplings or [],
                jumps=jumps or [],
            )
            for point in points
        ]
    )
    process_covariance = np.diag(
        [process_variance_per_day[key] * delta_days for key in STATE_ORDER]
    )
    mean, covariance = _unscented_moments(
        transformed,
        mean_weights,
        covariance_weights,
        process_covariance,
    )
    return UKFState(mean=mean, covariance=covariance, as_of=as_of)


def update(
    predicted: UKFState,
    measurements: list[RegimeMeasurement],
    *,
    alpha: float = 0.3,
    beta: float = 2.0,
    kappa: float = 0.0,
    minimum_variance: float = 1e-6,
    minimum_coverage: float = 0.05,
) -> UKFState:
    if not measurements:
        return predicted

    ordered = sorted(measurements, key=lambda item: _STATE_INDEX[item.state])
    indices = np.array([_STATE_INDEX[item.state] for item in ordered], dtype=int)
    observed = np.array([item.value for item in ordered], dtype=float)

    points, mean_weights, covariance_weights = _sigma_points(
        predicted.mean,
        predicted.covariance,
        alpha=alpha,
        beta=beta,
        kappa=kappa,
    )
    measurement_points = expit(points[:, indices])
    measurement_mean = np.sum(
        measurement_points * mean_weights[:, None],
        axis=0,
    )

    residuals = measurement_points - measurement_mean
    innovation_covariance = np.zeros((len(ordered), len(ordered)))
    cross_covariance = np.zeros((6, len(ordered)))
    state_residuals = points - predicted.mean

    for index, weight in enumerate(covariance_weights):
        innovation_covariance += weight * np.outer(
            residuals[index],
            residuals[index],
        )
        cross_covariance += weight * np.outer(
            state_residuals[index],
            residuals[index],
        )

    measurement_noise = np.diag(
        [
            max(
                item.variance / max(item.coverage, minimum_coverage),
                minimum_variance,
            )
            for item in ordered
        ]
    )
    innovation_covariance = _positive_semidefinite(
        innovation_covariance + measurement_noise
    )

    gain = np.linalg.solve(
        innovation_covariance,
        cross_covariance.T,
    ).T
    posterior_mean = predicted.mean + gain @ (observed - measurement_mean)
    posterior_covariance = (
        predicted.covariance
        - gain @ innovation_covariance @ gain.T
    )
    return UKFState(
        mean=posterior_mean,
        covariance=_positive_semidefinite(posterior_covariance),
        as_of=predicted.as_of,
    )


def step(
    state: UKFState,
    measurements: list[RegimeMeasurement],
    *,
    as_of: datetime,
    half_life_days: dict[str, float],
    process_variance_per_day: dict[str, float],
    couplings: list[Coupling] | None = None,
    jumps: list[Jump] | None = None,
    alpha: float = 0.3,
    beta: float = 2.0,
    kappa: float = 0.0,
) -> UKFState:
    predicted = predict(
        state,
        as_of=as_of,
        half_life_days=half_life_days,
        process_variance_per_day=process_variance_per_day,
        couplings=couplings,
        jumps=jumps,
        alpha=alpha,
        beta=beta,
        kappa=kappa,
    )
    return update(
        predicted,
        measurements,
        alpha=alpha,
        beta=beta,
        kappa=kappa,
    )


def summarize(
    state: UKFState,
    *,
    alpha: float = 0.3,
    beta: float = 2.0,
    kappa: float = 0.0,
) -> dict[str, FilteredState]:
    points, mean_weights, covariance_weights = _sigma_points(
        state.mean,
        state.covariance,
        alpha=alpha,
        beta=beta,
        kappa=kappa,
    )
    activation_points = expit(points)
    activation_mean, activation_covariance = _unscented_moments(
        activation_points,
        mean_weights,
        covariance_weights,
    )

    result: dict[str, FilteredState] = {}
    for index, key in enumerate(STATE_ORDER):
        variance = max(float(activation_covariance[index, index]), 0.0)
        standard_deviation = variance**0.5
        ci_low = max(0.0, float(activation_mean[index] - 1.645 * standard_deviation))
        ci_high = min(1.0, float(activation_mean[index] + 1.645 * standard_deviation))
        if variance <= 0.01:
            confidence = "High"
        elif variance <= 0.04:
            confidence = "Medium"
        else:
            confidence = "Low"

        result[key] = FilteredState(
            state=key,
            value=float(np.clip(activation_mean[index], 0.0, 1.0)),
            variance=variance,
            ci_low=ci_low,
            ci_high=ci_high,
            confidence=confidence,
        )
    return result


def log_likelihood_gaussian(
    innovation: np.ndarray,
    covariance: np.ndarray,
) -> float:
    covariance = _positive_semidefinite(covariance)
    sign, logdet = np.linalg.slogdet(covariance)
    if sign <= 0:
        raise ValueError("covariance determinant must be positive")
    quadratic = float(innovation.T @ np.linalg.solve(covariance, innovation))
    dimension = innovation.size
    return -0.5 * (dimension * log(2.0 * np.pi) + logdet + quadratic)
