from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class APCRPromotionGate:
    panel_valid: bool
    full_rank_design: bool
    post_period_count: int
    minimum_post_periods_for_promotion: int
    point_in_time_vintages_complete: bool
    treatment_regime_clean: bool
    pretrend_confounding_resolved: bool
    beta_normalization_frozen: bool
    prospective_validation_passed: bool

    def blockers(self) -> tuple[str, ...]:
        blockers: list[str] = []
        if not self.panel_valid:
            blockers.append("panel_validation_failed")
        if not self.full_rank_design:
            blockers.append("full_rank_design_failed")
        if self.post_period_count < self.minimum_post_periods_for_promotion:
            blockers.append(
                "insufficient_post_periods_for_promotion"
            )
        if not self.point_in_time_vintages_complete:
            blockers.append("point_in_time_vintages_incomplete")
        if not self.treatment_regime_clean:
            blockers.append("treatment_regime_contamination")
        if not self.pretrend_confounding_resolved:
            blockers.append("sector_specific_trend_confounding_not_resolved")
        if not self.beta_normalization_frozen:
            blockers.append("beta_normalization_not_frozen")
        if not self.prospective_validation_passed:
            blockers.append("prospective_validation_not_passed")
        return tuple(blockers)


def evaluate_apcr_promotion(
    candidate: dict[str, Any],
    *,
    gate: APCRPromotionGate,
) -> dict[str, Any]:
    blockers = gate.blockers()
    eligible = not blockers

    diagnostics = candidate.get("sector_pretrend_diagnostics", {})
    return {
        "status": "ELIGIBLE_FOR_STATE_MAPPING" if eligible else "BLOCKED_RESEARCH_ONLY",
        "promotion_eligible": eligible,
        "authoritative_state_input": eligible,
        "A_coverage_increment": 1.0 if eligible else 0.0,
        "gate": asdict(gate),
        "blockers": list(blockers),
        "observed_diagnostics": {
            "raw_beta": candidate.get("main", {}).get(
                "interaction_coefficient"
            ),
            "pre_period_placebo_ratio": candidate.get(
                "pre_period_placebo", {}
            ).get("absolute_beta_ratio_to_main"),
            "baseline_ai_vs_pretrend_correlation": diagnostics.get(
                "baseline_ai_intensity_vs_pretrend_slope_correlation"
            ),
            "trend_adjusted_beta": diagnostics.get(
                "trend_adjusted_twfe", {}
            ).get("interaction_coefficient"),
            "trend_adjusted_to_raw_ratio": diagnostics.get(
                "trend_adjusted_to_raw_absolute_beta_ratio"
            ),
        },
        "threshold_policy": (
            "No ex-post correlation/placebo/trend-ratio pass threshold is frozen. "
            "Promotion remains blocked until pretrend confounding is resolved "
            "by a separately predeclared design."
        ),
    }
