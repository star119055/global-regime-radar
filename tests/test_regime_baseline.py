import pytest

from global_regime_radar.regime.baseline import (
    IndicatorEvidence,
    estimate_regime,
    estimate_state,
)


def test_no_observations_returns_prior_not_zero():
    result = estimate_state(
        "A",
        [
            IndicatorEvidence("apcr", None, 1.0),
            IndicatorEvidence("llier", None, 1.0),
        ],
        prior=0.55,
        prior_variance=0.12,
    )
    assert result.value == 0.55
    assert result.coverage == 0.0
    assert result.observed_composite is None
    assert result.variance == 0.12
    assert result.confidence == "Low"


def test_partial_missingness_blends_with_prior():
    result = estimate_state(
        "B",
        [
            IndicatorEvidence("repo", 0.9, 1.0, 0.01),
            IndicatorEvidence("auction", None, 1.0),
        ],
        prior=0.5,
    )
    assert result.coverage == 0.5
    assert result.observed_composite == 0.9
    assert result.value == pytest.approx(0.7)
    assert result.value != pytest.approx(0.45)


def test_full_coverage_uses_observed_weighted_composite():
    result = estimate_state(
        "C3",
        [
            IndicatorEvidence("lead_time", 0.8, 2.0, 0.01),
            IndicatorEvidence("capex_deflator", 0.2, 1.0, 0.01),
        ],
    )
    assert result.coverage == 1.0
    assert result.value == pytest.approx(0.6)
    assert result.variance == pytest.approx(0.01)


def test_missingness_increases_uncertainty_relative_to_same_observed_signal():
    full = estimate_state(
        "D",
        [
            IndicatorEvidence("tids", 0.7, 1.0, 0.01),
            IndicatorEvidence("rri", 0.7, 1.0, 0.01),
        ],
    )
    partial = estimate_state(
        "D",
        [
            IndicatorEvidence("tids", 0.7, 1.0, 0.01),
            IndicatorEvidence("rri", None, 1.0),
        ],
    )
    assert partial.variance > full.variance


def test_duplicate_attribution_group_fails_fast():
    with pytest.raises(ValueError, match="duplicate attribution_group"):
        estimate_state(
            "B",
            [
                IndicatorEvidence("repo", 0.8, 1.0, attribution_group="dealer"),
                IndicatorEvidence("basis", 0.7, 1.0, attribution_group="dealer"),
            ],
        )


def test_invalid_activation_rejected():
    with pytest.raises(ValueError, match="activation"):
        IndicatorEvidence("x", 1.2, 1.0)


def test_six_state_regime_output_is_deterministic():
    evidence = {
        state: [IndicatorEvidence(f"{state}-signal", 0.6, 1.0, 0.02)]
        for state in ("A", "B", "C1", "C2", "C3", "D")
    }
    first = estimate_regime(evidence)
    second = estimate_regime(evidence)
    assert first == second
    assert tuple(first) == ("A", "B", "C1", "C2", "C3", "D")


def test_regime_requires_all_six_states():
    with pytest.raises(ValueError, match="missing state configurations"):
        estimate_regime({"A": [IndicatorEvidence("a", 0.5, 1.0)]})
