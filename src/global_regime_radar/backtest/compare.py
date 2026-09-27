from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleMetricDelta:
    metric: str
    core_value: float
    augmented_value: float
    delta: float


@dataclass(frozen=True)
class ModuleComparison:
    core_run_id: str
    augmented_run_id: str
    deltas: tuple[ModuleMetricDelta, ...]


def compare_module_metrics(
    *,
    core_run_id: str,
    augmented_run_id: str,
    core_metrics: dict[str, float],
    augmented_metrics: dict[str, float],
) -> ModuleComparison:
    if set(core_metrics) != set(augmented_metrics):
        raise ValueError("core and augmented runs must expose the same metric keys")

    deltas = tuple(
        ModuleMetricDelta(
            metric=metric,
            core_value=core_metrics[metric],
            augmented_value=augmented_metrics[metric],
            delta=augmented_metrics[metric] - core_metrics[metric],
        )
        for metric in sorted(core_metrics)
    )
    return ModuleComparison(
        core_run_id=core_run_id,
        augmented_run_id=augmented_run_id,
        deltas=deltas,
    )
