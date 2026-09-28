import pytest

from global_regime_radar.research.apcr_candidate import estimate_candidate


def _treatment(entity: str, intensity: float) -> dict[str, object]:
    return {
        "entity_id": entity,
        "baseline_ai_intensity": intensity,
        "source_vintage_ids": [f"{entity}-v{period}" for period in range(6)],
    }


def _outcomes(entity_effect: float, intensity: float) -> list[dict[str, object]]:
    result = []
    for year, time_effect in [(2021, 0.0), (2022, 1.0), (2023, 2.0), (2024, 3.0)]:
        post = year >= 2024
        result.append(
            {
                "year": year,
                "value": (
                    100.0
                    + entity_effect
                    + time_effect
                    + 20.0 * intensity * float(post)
                ),
            }
        )
    return result


def test_apcr_candidate_recovers_main_beta_and_keeps_state_disabled():
    intensities = {"23": 0.01, "44": 0.03, "51": 0.14, "54": 0.09}
    frozen = [
        _treatment(entity, intensity)
        for entity, intensity in intensities.items()
    ]
    annual = {
        entity: _outcomes(index * 2.0, intensity)
        for index, (entity, intensity) in enumerate(intensities.items())
    }

    result = estimate_candidate(
        frozen_treatment=frozen,
        annual_observations=annual,
        productivity_vintage_id="bls-current",
    )

    assert result["status"] == "ESTIMATED_RESEARCH_ONLY"
    assert result["main"]["interaction_coefficient"] == pytest.approx(20.0)
    assert result["main_beta_per_10pp_ai_share"] == pytest.approx(2.0)
    assert result["A_coverage_increment"] == 0.0
    assert result["authoritative_state_input"] is False
    assert result["causal_claim_allowed"] is False
    assert len(result["leave_one_sector_out_beta"]) == 4


def test_apcr_candidate_reports_preperiod_placebo():
    intensities = {"23": 0.01, "44": 0.03, "51": 0.14, "54": 0.09}
    frozen = [
        _treatment(entity, intensity)
        for entity, intensity in intensities.items()
    ]
    annual = {}
    for index, (entity, intensity) in enumerate(intensities.items()):
        rows = []
        for year, time_effect in [(2021, 0.0), (2022, 1.0), (2023, 2.0), (2024, 3.0)]:
            fake_pretrend = 8.0 * intensity * float(year >= 2023)
            main_effect = 20.0 * intensity * float(year >= 2024)
            rows.append(
                {
                    "year": year,
                    "value": 100 + index + time_effect + fake_pretrend + main_effect,
                }
            )
        annual[entity] = rows

    result = estimate_candidate(
        frozen_treatment=frozen,
        annual_observations=annual,
        productivity_vintage_id="bls-current",
    )
    placebo = result["pre_period_placebo"]
    assert placebo["result"]["interaction_coefficient"] == pytest.approx(8.0)
    assert placebo["absolute_beta_ratio_to_main"] is not None
    assert "pretrend_not_validated" in result["promotion_blockers"]


def test_apcr_candidate_refuses_incomplete_panel_without_imputation():
    frozen = [
        _treatment("23", 0.01),
        _treatment("44", 0.03),
        _treatment("51", 0.14),
        _treatment("54", 0.09),
    ]
    annual = {
        "23": _outcomes(0.0, 0.01),
        "44": _outcomes(1.0, 0.03),
        "51": _outcomes(2.0, 0.14),
        "54": _outcomes(3.0, 0.09)[:-1],
    }
    result = estimate_candidate(
        frozen_treatment=frozen,
        annual_observations=annual,
        productivity_vintage_id="bls-current",
    )
    assert result["status"] == "INSUFFICIENT_PANEL"
    assert result["A_coverage_increment"] == 0.0
