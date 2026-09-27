from datetime import UTC, datetime

import pytest

from global_regime_radar.reporting.snapshot import (
    ChangeDriver,
    DailySnapshot,
    EvidenceItem,
    EvidenceKind,
    FatPitchStatus,
    FeedbackLoop,
    StateRow,
    canonical_payload,
    render_markdown,
    select_top_drivers,
    snapshot_hash,
)
from global_regime_radar.stress.engine import StressLevel


def dt(hour: int = 8) -> datetime:
    return datetime(2026, 9, 27, hour, 30, tzinfo=UTC)


def rows() -> tuple[StateRow, ...]:
    return tuple(
        StateRow(
            state=state,
            value=0.50 + index * 0.03,
            delta=(index - 2) * 0.01,
            confidence="Medium",
            coverage=0.8,
            variance=0.04,
        )
        for index, state in enumerate(("A", "B", "C1", "C2", "C3", "D"))
    )


def make_snapshot(generated_at: datetime | None = None) -> DailySnapshot:
    return DailySnapshot(
        as_of=dt(),
        generated_at=generated_at or dt(9),
        model_version="v6.1",
        conclusion="C3 is the strongest pressure while market function remains orderly.",
        states=rows(),
        stress_level=StressLevel.L2,
        fat_pitch={
            "B": FatPitchStatus.OFF,
            "C": FatPitchStatus.WATCH,
            "D": FatPitchStatus.OFF,
        },
        top_changes=select_top_drivers(
            [
                ChangeDriver("a", "A", 0.01, "small"),
                ChangeDriver("c3", "C3", 0.08, "largest"),
                ChangeDriver("repo", "Repo", -0.05, "second"),
                ChangeDriver("crop", "Crop", 0.03, "third"),
            ]
        ),
        feedback_loop=FeedbackLoop(
            "Capital cost loop",
            ("C3", "$/MW", "IRR", "LLIER", "A"),
        ),
        evidence=(
            EvidenceItem(
                EvidenceKind.OBSERVED,
                "Transformer lead time increased.",
                ("source-transformer",),
            ),
            EvidenceItem(
                EvidenceKind.INFERRED,
                "Higher project cost is pressuring IRR.",
            ),
        ),
        next_confirmation="Next 30Y Treasury auction.",
        falsification_conditions=("Transformer lead times normalize materially.",),
    )


def test_top_three_drivers_are_sorted_by_absolute_impact():
    top = make_snapshot().top_changes
    assert [item.key for item in top] == ["c3", "repo", "crop"]


def test_snapshot_hash_excludes_generation_time():
    first = make_snapshot(dt(9))
    second = make_snapshot(dt(10))
    assert snapshot_hash(first) == snapshot_hash(second)


def test_payload_orders_six_states_canonically():
    payload = canonical_payload(make_snapshot())
    assert [row["state"] for row in payload["states"]] == [
        "A",
        "B",
        "C1",
        "C2",
        "C3",
        "D",
    ]


def test_markdown_contains_decision_sections_and_evidence_labels():
    rendered = render_markdown(make_snapshot())
    assert "## 一句话结论" in rendered
    assert "## State Matrix" in rendered
    assert "## 今日 Top 3 变化" in rendered
    assert "**Observed**" in rendered
    assert "**Inferred**" in rendered
    assert "## 模型证伪条件" in rendered


def test_snapshot_requires_exact_six_states():
    with pytest.raises(ValueError, match="exactly A/B/C1/C2/C3/D"):
        DailySnapshot(
            as_of=dt(),
            generated_at=dt(9),
            model_version="v6.1",
            conclusion="x",
            states=rows()[:-1],
            stress_level=StressLevel.L1,
            fat_pitch={
                "B": FatPitchStatus.OFF,
                "C": FatPitchStatus.OFF,
                "D": FatPitchStatus.OFF,
            },
            top_changes=(),
            feedback_loop=FeedbackLoop("x", ("A", "B")),
            evidence=(),
            next_confirmation="x",
            falsification_conditions=(),
        )


def test_more_than_three_changes_is_rejected():
    with pytest.raises(ValueError, match="at most three"):
        DailySnapshot(
            as_of=dt(),
            generated_at=dt(9),
            model_version="v6.1",
            conclusion="x",
            states=rows(),
            stress_level=StressLevel.L1,
            fat_pitch={
                "B": FatPitchStatus.OFF,
                "C": FatPitchStatus.OFF,
                "D": FatPitchStatus.OFF,
            },
            top_changes=tuple(
                ChangeDriver(str(i), str(i), float(i), "x") for i in range(4)
            ),
            feedback_loop=FeedbackLoop("x", ("A", "B")),
            evidence=(),
            next_confirmation="x",
            falsification_conditions=(),
        )
