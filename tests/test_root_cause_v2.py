"""Unit and integration tests for the v2 root cause engine."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core import get_settings
from app.ml.root_cause_v2 import HistoricalIncident, RootCauseEngineV2
from app.ml.root_cause_v2.embedder import HashFallbackEmbedder, cosine_similarity
from app.ml.root_cause_v2.featurizer import featurize
from app.ml.root_cause_v2.incident_store import InMemoryIncidentStore
from app.ml.root_cause_v2.llm_client import StubLLMClient
from app.ml.root_cause_v2.parser import ParseError, parse_llm_response
from app.models import Anomaly, AnomalyType, InterfaceMetric, Severity


# ---------------- fixtures ----------------

@pytest.fixture()
def embedder():
    return HashFallbackEmbedder()


@pytest.fixture()
def empty_store(embedder):
    return InMemoryIncidentStore(embedder)


@pytest.fixture()
def seeded_store(embedder):
    store = InMemoryIncidentStore(embedder)
    incidents = [
        HistoricalIncident(
            incident_id="HIST-001",
            timestamp=datetime(2025, 8, 1, tzinfo=timezone.utc),
            device_class="core_router",
            text="On a core router (rtr-A), interface Gi0/1 saturated at 95% with 600 discards.",
            root_cause="congestion",
            root_cause_detail="ISP uplink saturation",
            actions_taken=["Apply QoS", "Identify top talkers", "Plan upgrade"],
            resolution_minutes=45,
        ),
        HistoricalIncident(
            incident_id="HIST-002",
            timestamp=datetime(2025, 9, 1, tzinfo=timezone.utc),
            device_class="core_router",
            text="On a core router (rtr-B), interface Gi0/2 had 250 errors at 12% utilization. Faulty SFP.",
            root_cause="physical_layer",
            root_cause_detail="Bad SFP module — low light levels",
            actions_taken=["Replace SFP", "Verify clean counters", "Update runbook"],
            resolution_minutes=90,
        ),
        HistoricalIncident(
            incident_id="HIST-003",
            timestamp=datetime(2025, 10, 1, tzinfo=timezone.utc),
            device_class="distribution_switch",
            text="On a distribution switch (dist-X), interface Te0/0/2 had 91% utilization with 600 discards during backup.",
            root_cause="congestion",
            root_cause_detail="Backup traffic saturation",
            actions_taken=["Apply QoS to backup", "Mark backup as low priority"],
            resolution_minutes=120,
        ),
    ]
    for inc in incidents:
        store.add(inc, embedder.embed(inc.text))
    return store


@pytest.fixture()
def congested_metric():
    return InterfaceMetric(
        device_name="core-rtr-test",
        interface_name="Gi0/1",
        interface_description="Test ISP uplink",
        in_utilization_percent=92.0,
        out_utilization_percent=89.5,
        in_errors_1h=0,
        out_errors_1h=0,
        in_discards_1h=400,
        out_discards_1h=350,
    )


@pytest.fixture()
def congested_anomalies():
    return [
        Anomaly(type=AnomalyType.UTILIZATION_HIGH, severity=Severity.HIGH,
                description="Utilization 92% exceeds critical", metric_value=92.0),
        Anomaly(type=AnomalyType.DISCARD_SPIKE, severity=Severity.HIGH,
                description="750 discards", metric_value=750),
    ]


# ---------------- featurizer ----------------

def test_featurizer_classifies_core_router(congested_metric, congested_anomalies):
    features = featurize(congested_metric, congested_anomalies)
    assert features.device_class == "core_router"
    assert "saturated" in features.summary_text.lower() or "92.0" in features.summary_text
    assert features.structured_metrics["max_utilization"] == 92.0
    assert len(features.anomaly_signatures) == 2


def test_featurizer_classifies_unknown():
    metric = InterfaceMetric(
        device_name="weird-device-name",
        interface_name="Eth0",
        interface_description="",
        in_utilization_percent=10.0, out_utilization_percent=10.0,
        in_errors_1h=0, out_errors_1h=0, in_discards_1h=0, out_discards_1h=0,
    )
    features = featurize(metric, [])
    assert features.device_class == "unknown"


# ---------------- embedder ----------------

def test_hash_embedder_deterministic(embedder):
    a = embedder.embed("the quick brown fox")
    b = embedder.embed("the quick brown fox")
    assert (a == b).all()
    assert a.shape == (384,)


def test_hash_embedder_similar_texts_have_higher_similarity(embedder):
    a = embedder.embed("congestion ISP uplink saturation")
    b = embedder.embed("congestion ISP uplink saturation high traffic")
    c = embedder.embed("physical layer bad SFP optical errors")
    sim_ab = cosine_similarity(a, b)
    sim_ac = cosine_similarity(a, c)
    assert sim_ab > sim_ac


# ---------------- incident store ----------------

def test_store_add_and_count(empty_store, embedder):
    inc = HistoricalIncident(
        incident_id="X-1", timestamp=datetime.now(timezone.utc),
        device_class="core_router", text="hello world",
        root_cause="x", root_cause_detail="x", actions_taken=[],
    )
    empty_store.add(inc, embedder.embed(inc.text))
    assert empty_store.count() == 1


def test_store_search_returns_top_k(seeded_store, embedder):
    query = embedder.embed("core router congestion saturation")
    results = seeded_store.search(query, k=2)
    assert len(results) == 2
    # Top result should be the most similar one
    assert results[0].similarity >= results[1].similarity


def test_store_device_class_filter(seeded_store, embedder):
    query = embedder.embed("any query")
    results = seeded_store.search(query, k=10, device_class_filter="core_router")
    assert all(r.incident.device_class == "core_router" for r in results)


def test_store_filter_falls_back_when_no_match(seeded_store, embedder):
    query = embedder.embed("any query")
    # No incidents with this device_class — should fall back to unfiltered
    results = seeded_store.search(query, k=3, device_class_filter="nonexistent_class")
    assert len(results) > 0


def test_store_save_and_load(seeded_store, embedder, tmp_path):
    out = tmp_path / "store.json"
    seeded_store.save(out)
    assert out.exists()
    loaded = InMemoryIncidentStore.load(out, embedder)
    assert loaded.count() == seeded_store.count()


# ---------------- parser ----------------

def test_parser_accepts_clean_json():
    raw = json.dumps({
        "probable_cause": "Test cause",
        "confidence": 0.85,
        "details": "Test details",
        "recommended_actions": ["a", "b"],
        "referenced_incident_ids": ["INC-1"],
        "reasoning": "Test reasoning",
    })
    result = parse_llm_response(raw)
    assert result.probable_cause == "Test cause"
    assert result.confidence == 0.85
    assert result.recommended_actions == ["a", "b"]


def test_parser_strips_markdown_fences():
    raw = "```json\n" + json.dumps({
        "probable_cause": "Test", "confidence": 0.5,
        "details": "x", "recommended_actions": ["y"],
    }) + "\n```"
    result = parse_llm_response(raw)
    assert result.probable_cause == "Test"


def test_parser_extracts_embedded_json():
    raw = "Here is my analysis:\n" + json.dumps({
        "probable_cause": "Test", "confidence": 0.5,
        "details": "x", "recommended_actions": ["y"],
    }) + "\nThanks!"
    result = parse_llm_response(raw)
    assert result.probable_cause == "Test"


def test_parser_clamps_confidence():
    raw = json.dumps({
        "probable_cause": "x", "confidence": 1.5,
        "details": "x", "recommended_actions": ["y"],
    })
    result = parse_llm_response(raw)
    assert result.confidence == 1.0


def test_parser_rejects_missing_required_field():
    raw = json.dumps({"probable_cause": "x", "confidence": 0.5})
    with pytest.raises(ParseError):
        parse_llm_response(raw)


def test_parser_rejects_empty():
    with pytest.raises(ParseError):
        parse_llm_response("")


def test_parser_rejects_garbage():
    with pytest.raises(ParseError):
        parse_llm_response("this is not json at all")


# ---------------- engine integration ----------------

def test_engine_returns_none_for_no_anomalies(seeded_store, embedder):
    settings = get_settings()
    engine = RootCauseEngineV2(
        settings, embedder=embedder, store=seeded_store, llm_client=StubLLMClient()
    )
    metric = InterfaceMetric(
        device_name="d", interface_name="i", interface_description="",
        in_utilization_percent=10.0, out_utilization_percent=10.0,
        in_errors_1h=0, out_errors_1h=0, in_discards_1h=0, out_discards_1h=0,
    )
    assert engine.suggest(metric, []) is None


def test_engine_uses_rag_for_congestion(
    seeded_store, embedder, congested_metric, congested_anomalies
):
    settings = get_settings()
    engine = RootCauseEngineV2(
        settings, embedder=embedder, store=seeded_store,
        llm_client=StubLLMClient(),
        min_similarity=0.0,  # accept any retrieval for test stability
    )
    suggestion = engine.suggest(congested_metric, congested_anomalies)
    assert suggestion is not None
    assert suggestion.confidence > 0.0
    assert len(suggestion.recommended_actions) >= 1


def test_engine_falls_back_on_cold_start(
    empty_store, embedder, congested_metric, congested_anomalies
):
    """With an empty store, the engine should fall back to the rule engine."""
    settings = get_settings()
    engine = RootCauseEngineV2(
        settings, embedder=embedder, store=empty_store, llm_client=StubLLMClient()
    )
    suggestion = engine.suggest(congested_metric, congested_anomalies)
    # Should still produce a suggestion via the v1 rule fallback
    assert suggestion is not None
    assert "fallback" in suggestion.details.lower()


def test_engine_preserves_v1_signature(
    seeded_store, embedder, congested_metric, congested_anomalies
):
    """The v2 engine must be a drop-in replacement — same return type."""
    from app.models import RootCauseSuggestion

    settings = get_settings()
    engine = RootCauseEngineV2(
        settings, embedder=embedder, store=seeded_store,
        llm_client=StubLLMClient(), min_similarity=0.0,
    )
    suggestion = engine.suggest(congested_metric, congested_anomalies)
    assert isinstance(suggestion, RootCauseSuggestion)
    assert hasattr(suggestion, "probable_cause")
    assert hasattr(suggestion, "confidence")
    assert hasattr(suggestion, "recommended_actions")
