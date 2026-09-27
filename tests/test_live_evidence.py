import json
from datetime import UTC, datetime, timedelta

from global_regime_radar.data.contracts import DataVintage, Observation
from global_regime_radar.live.collector import LiveBundle, collect_public_core
from global_regime_radar.live.evidence import build_live_evidence
from global_regime_radar.live.http import FetchBytes

RETRIEVED = datetime(2026, 9, 27, 0, 30, tzinfo=UTC)


def _sofr_payload() -> bytes:
    rows = []
    for day in range(1, 12):
        rows.append(
            {
                "effectiveDate": f"2026-09-{day:02d}",
                "type": "SOFR",
                "percentRate": 3.8,
                "volumeInBillions": 2000 + day,
                "percentPercentile1": 3.70,
                "percentPercentile99": 3.80 + day * 0.01,
            }
        )
    return json.dumps({"refRates": rows}).encode()


def _repo_payload() -> bytes:
    rows = []
    for day in range(1, 12):
        rows.append(
            {
                "operationId": f"RP-{day}",
                "operationDate": f"2026-09-{day:02d}",
                "lastUpdated": f"2026-09-{day:02d} 13:00:00",
                "totalAmtSubmitted": day * 10,
                "totalAmtAccepted": day * 10,
            }
        )
    return json.dumps({"repo": {"operations": rows}}).encode()


def _auction_payload() -> bytes:
    rows = []
    for day in range(1, 12):
        rows.append(
            {
                "record_date": f"2026-09-{day:02d}",
                "cusip": f"CUSIP{day}",
                "security_type": "Note",
                "security_term": "2-Year",
                "original_security_term": "2-Year",
                "auction_date": f"2026-09-{day:02d}",
                "bid_to_cover_ratio": str(2.9 - day * 0.04),
                "primary_dealer_accepted": "10",
                "direct_bidder_accepted": "10",
                "indirect_bidder_accepted": "80",
                "total_accepted": "100",
            }
        )
    return json.dumps({"data": rows}).encode()


def _real_yield_csv() -> bytes:
    rows = ["Date,5 YR,7 YR,10 YR,20 YR,30 YR"]
    for day in range(1, 12):
        rows.append(f"09/{day:02d}/2026,1.1,1.2,{1.6-day*0.03:.2f},1.4,1.5")
    return ("\n".join(rows) + "\n").encode()


def _oni_text() -> bytes:
    return (
        b"2025 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0 1.1 1.2\n"
        b"2026 0.0 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0 1.1\n"
    )


class FakeFetcher:
    def __call__(self, url: str) -> bytes:
        if "rates/secured/sofr" in url:
            return _sofr_payload()
        if "/rp/repo/" in url:
            return _repo_payload()
        if "auctions_query" in url:
            return _auction_payload()
        if "daily-treasury-rates.csv" in url:
            return _real_yield_csv()
        if "oni.data" in url:
            return _oni_text()
        raise AssertionError(f"unexpected URL: {url}")


def test_collect_public_core_uses_injected_fetcher_and_hashes_sources():
    bundle = collect_public_core(
        RETRIEVED,
        fetcher=FakeFetcher(),
        lookback_days=180,
    )
    assert len(bundle.vintages) == 5
    assert bundle.source_failures == ()
    assert bundle.dataset_hash
    assert any(obs.feature_id == "sofr_rate" for obs in bundle.observations)
    assert any(obs.feature_id == "enso_oni" for obs in bundle.observations)


def test_source_failure_is_explicit_and_other_sources_survive():
    class PartialFetcher(FakeFetcher):
        def __call__(self, url: str) -> bytes:
            if "oni.data" in url:
                raise OSError("NOAA unavailable")
            return super().__call__(url)

    bundle = collect_public_core(
        RETRIEVED,
        fetcher=PartialFetcher(),
        lookback_days=180,
    )
    assert len(bundle.source_failures) == 1
    assert bundle.source_failures[0].source == "noaa_oni"
    assert any(obs.feature_id == "sofr_rate" for obs in bundle.observations)


def test_live_evidence_maps_only_supported_states():
    document = build_live_evidence(
        collect_public_core(
            RETRIEVED,
            fetcher=FakeFetcher(),
            lookback_days=180,
        )
    )
    items = {item.key: item for item in document.items}
    assert items["sofr_dispersion_stress"].activation is not None
    assert items["auction_quality_stress"].activation is not None
    assert items["real_yield_repression"].activation is not None
    assert items["apcr"].activation is None
    assert items["hormuz_disruption"].activation is None
    assert items["transformer_lead_time"].activation is None


def test_noaa_oni_is_not_silently_mapped_to_c1():
    document = build_live_evidence(
        collect_public_core(
            RETRIEVED,
            fetcher=FakeFetcher(),
            lookback_days=180,
        )
    )
    c1 = [item for item in document.items if item.state == "C1"]
    assert all(item.activation is None for item in c1)


def test_live_document_retains_source_hashes_and_evidence_ids():
    document = build_live_evidence(
        collect_public_core(
            RETRIEVED,
            fetcher=FakeFetcher(),
            lookback_days=180,
        )
    )
    assert "nyfed_sofr" in document.source_hashes
    b_observed = [
        item
        for item in document.items
        if item.state == "B" and item.activation is not None
    ]
    assert b_observed
    assert all(item.evidence_ids for item in b_observed)


def test_document_gaps_are_explicit_for_unconnected_state_families():
    document = build_live_evidence(
        collect_public_core(
            RETRIEVED,
            fetcher=FakeFetcher(),
            lookback_days=180,
        )
    )
    assert "A:apcr:missing" in document.gaps
    assert "C2:external_debt_stress:missing" in document.gaps
    assert "C3:transformer_lead_time:missing" in document.gaps


def test_bundle_can_be_constructed_without_network_for_downstream_tests():
    vintage = DataVintage(
        vintage_id="v1",
        source_id="test",
        retrieved_at=RETRIEVED,
        source_hash="abc",
    )
    observation = Observation(
        observation_id="o1",
        feature_id="enso_oni",
        source_id="test",
        value=0.5,
        observation_start=RETRIEVED - timedelta(days=30),
        observation_end=RETRIEVED - timedelta(days=30),
        available_at=RETRIEVED,
        ingested_at=RETRIEVED,
        vintage_id="v1",
    )
    bundle = LiveBundle(
        retrieved_at=RETRIEVED,
        observations=(observation,),
        vintages=(vintage,),
        source_failures=(),
        dataset_hash="hash",
    )
    document = build_live_evidence(bundle)
    assert document.dataset_hash == "hash"


def test_fetch_type_contract_accepts_callable():
    fetcher: FetchBytes = FakeFetcher()
    assert fetcher("https://psl.noaa.gov/data/correlation/oni.data") == _oni_text()
