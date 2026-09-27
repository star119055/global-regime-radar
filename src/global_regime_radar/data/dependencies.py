from collections.abc import Iterable

from global_regime_radar.data.contracts import FeatureDependency


def validate_no_duplicate_state_contribution(
    dependencies: Iterable[FeatureDependency],
) -> None:
    seen: dict[tuple[str, str], FeatureDependency] = {}

    for dependency in dependencies:
        key = (dependency.parent_feature_id, dependency.target_state)
        prior = seen.get(key)
        if prior is not None and prior.child_indicator_id != dependency.child_indicator_id:
            raise ValueError(
                "raw feature contributes to the same latent state through multiple "
                f"indicators: {dependency.parent_feature_id} -> {dependency.target_state}"
            )
        seen[key] = dependency
