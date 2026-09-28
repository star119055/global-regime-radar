from global_regime_radar.research.llier_sources import (
    LLIERSourceCapability,
    LLIERSourceClass,
    classify_llier_source,
    source_gate_summary,
)


def test_ercot_aggregate_queue_is_context_only():
    source = LLIERSourceCapability(
        source_id="ercot_monthly",
        stable_project_id=False,
        project_mw=False,
        repeatable_status_history=False,
        explicit_exit_events=False,
        process_regime_metadata=True,
        machine_readable=False,
        aggregate_status_only=True,
    )
    assert classify_llier_source(source) is LLIERSourceClass.AGGREGATE_CONTEXT_ONLY


def test_process_notice_is_metadata_not_llier_data():
    source = LLIERSourceCapability(
        source_id="batch_zero_notice",
        stable_project_id=False,
        project_mw=False,
        repeatable_status_history=False,
        explicit_exit_events=False,
        process_regime_metadata=True,
        machine_readable=True,
    )
    assert classify_llier_source(source) is LLIERSourceClass.PROCESS_METADATA_ONLY


def test_authoritative_source_requires_project_identity_and_exit_history():
    source = LLIERSourceCapability(
        source_id="project_history",
        stable_project_id=True,
        project_mw=True,
        repeatable_status_history=True,
        explicit_exit_events=True,
        process_regime_metadata=True,
        machine_readable=True,
    )
    assert (
        classify_llier_source(source)
        is LLIERSourceClass.AUTHORITATIVE_COHORT_CAPABLE
    )


def test_source_gate_keeps_A_at_zero_without_authoritative_source():
    sources = [
        LLIERSourceCapability(
            source_id="aggregate",
            stable_project_id=False,
            project_mw=False,
            repeatable_status_history=False,
            explicit_exit_events=False,
            process_regime_metadata=True,
            machine_readable=False,
            aggregate_status_only=True,
        ),
        LLIERSourceCapability(
            source_id="notice",
            stable_project_id=False,
            project_mw=False,
            repeatable_status_history=False,
            explicit_exit_events=False,
            process_regime_metadata=True,
            machine_readable=True,
        ),
    ]
    summary = source_gate_summary(sources)
    assert summary["authoritative_source_available"] is False
    assert summary["authoritative_sources"] == []
    assert summary["A_coverage_increment"] == 0.0


def test_unavailable_project_feed_does_not_qualify():
    source = LLIERSourceCapability(
        source_id="blocked_feed",
        stable_project_id=True,
        project_mw=True,
        repeatable_status_history=True,
        explicit_exit_events=True,
        process_regime_metadata=True,
        machine_readable=True,
        available=False,
    )
    assert classify_llier_source(source) is LLIERSourceClass.UNAVAILABLE
