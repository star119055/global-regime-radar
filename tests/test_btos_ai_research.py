import json
from datetime import UTC, datetime

from global_regime_radar.research.btos_ai import (
    research_payload,
    select_snapshot,
    write_research_context,
)

REGISTRY = b"""
version: 1
snapshots:
  - snapshot_id: btos-ai-supplement-2026
    available_at: "2026-06-18T23:59:59+00:00"
    collection_start: "2025-11-17"
    collection_end: "2026-02-08"
    paper_reference_period: "2025-11_to_2026-01"
    sources:
      - source_id: census_release
        url: "https://example.test/release"
      - source_id: census_paper
        url: "https://example.test/paper"
    facts:
      firm_ai_use_share: 0.18
      employment_weighted_ai_use_share: 0.32
      expected_six_month_firm_ai_use_share: 0.22
      sintegration_unconditional_firm_weighted_mean: 0.053
      simpact_unconditional_firm_weighted_mean: 0.043
      sinvest_unconditional_firm_weighted_mean: 0.030
    semantics:
      authoritative_state_input: false
      candidate_state: A
      blocked_indicator_keys: [apcr_did, llier, geoi]
      interpretation: "research only"
      causal_claim_allowed: false
      notes:
        - "not APCR"
"""


def dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, 23, 59, 59, tzinfo=UTC)


def test_btos_research_snapshot_is_gated_by_release_time():
    assert select_snapshot(REGISTRY, dt(2026, 6, 17)) is None

    snapshot = select_snapshot(REGISTRY, dt(2026, 6, 19))
    assert snapshot is not None
    assert snapshot.snapshot_id == "btos-ai-supplement-2026"
    assert snapshot.facts["firm_ai_use_share"] == 0.18
    assert snapshot.facts["simpact_unconditional_firm_weighted_mean"] == 0.043


def test_btos_research_snapshot_cannot_be_authoritative_state_input():
    snapshot = select_snapshot(REGISTRY, dt(2026, 6, 19))
    assert snapshot is not None
    assert snapshot.authoritative_state_input is False
    assert snapshot.causal_claim_allowed is False
    assert snapshot.blocked_indicator_keys == ("apcr_did", "llier", "geoi")


def test_research_payload_has_zero_a_coverage_effect():
    snapshot = select_snapshot(REGISTRY, dt(2026, 6, 19))
    payload = research_payload(snapshot, decision_time=dt(2026, 6, 19))
    assert payload["status"] == "AVAILABLE"
    assert payload["authoritative_state_input"] is False
    assert payload["state_effect"]["A_coverage_increment"] == 0.0


def test_research_context_serialization_preserves_snapshot_hash(tmp_path):
    snapshot = select_snapshot(REGISTRY, dt(2026, 6, 19))
    assert snapshot is not None
    path = tmp_path / "ai-research-context.json"
    write_research_context(
        snapshot,
        decision_time=dt(2026, 6, 19),
        path=path,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["snapshot"]["snapshot_hash"] == snapshot.snapshot_hash
    assert payload["snapshot"]["facts"]["sinvest_unconditional_firm_weighted_mean"] == 0.03


def test_research_snapshot_hash_changes_when_facts_change():
    first = select_snapshot(REGISTRY, dt(2026, 6, 19))
    changed = REGISTRY.replace(b"firm_ai_use_share: 0.18", b"firm_ai_use_share: 0.19")
    second = select_snapshot(changed, dt(2026, 6, 19))
    assert first is not None and second is not None
    assert first.snapshot_hash != second.snapshot_hash
