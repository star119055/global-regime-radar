import pytest

from global_regime_radar.research.apcr_watch import (
    release_watch_summary,
    render_markdown,
)


def test_release_watch_waits_for_complete_frozen_universe():
    summary = release_watch_summary(
        {
            "second_post_2025_probe": {
                "complete_2025_entities": ["44", "51"],
                "missing_2025_entities": ["52", "54"],
                "all_entities_have_2025": False,
            }
        }
    )
    assert summary["gate_status"] == "WAITING_FOR_BLS"
    assert summary["complete_count"] == 2
    assert summary["total_count"] == 4
    rendered = render_markdown(summary)
    assert "2/4" in rendered
    assert "52, 54" in rendered


def test_release_watch_opens_only_when_every_entity_is_complete():
    summary = release_watch_summary(
        {
            "second_post_2025_probe": {
                "complete_2025_entities": ["44", "51", "52", "54"],
                "missing_2025_entities": [],
                "all_entities_have_2025": True,
            }
        }
    )
    assert summary["gate_status"] == "OPEN_FOR_D22C7B_REVIEW"
    assert summary["total_count"] == 4
    assert "none" in render_markdown(summary)


def test_release_watch_rejects_inconsistent_complete_flag():
    with pytest.raises(ValueError, match="cannot be complete"):
        release_watch_summary(
            {
                "second_post_2025_probe": {
                    "complete_2025_entities": ["44"],
                    "missing_2025_entities": ["51"],
                    "all_entities_have_2025": True,
                }
            }
        )
