"""Tests for bridge.py — Hermes/Mr Kanban retrieval bridge."""

import json
import os
import tempfile

from export_engine.bridge import build_bridge_query_from_card, run_bridge_retrieval


def _setup(store_root: str) -> None:
    """Full fixture setup for bridge testing."""
    from export_engine.source_scan import run_source_scan
    from export_engine.planning import create_backfill_plan
    from export_engine.ingest import run_ingest
    from export_engine.conversations import build_conversations
    from export_engine.retrieval import build_retrieval_chunks
    from export_engine.index import build_index
    run_source_scan(store_root, use_fixture=True)
    create_backfill_plan(store_root, use_fixture=True, since="2025-07-05", until="2025-08-05")
    run_ingest(store_root, use_fixture=True, limit=10, resume=True, parse_extracts=True)
    build_conversations(store_root, export_run_id="test1")
    build_retrieval_chunks(store_root, export_run_id="test1")
    build_index(store_root, export_run_id="test1")


class TestBridgeQueryConstruction:
    def test_card_only_creates_query(self) -> None:
        card = {"cardTitle": "UltraRad Firewall", "currentState": "Waiting on vendor"}
        q = build_bridge_query_from_card(card)
        assert "UltraRad" in q
        assert "Waiting" in q

    def test_question_added(self) -> None:
        card = {"cardTitle": "RIS Access"}
        q = build_bridge_query_from_card(card, "Who approved this?")
        assert "RIS Access" in q
        assert "Who approved" in q

    def test_empty_card_returns_empty(self) -> None:
        q = build_bridge_query_from_card({})
        assert q.strip() == ""

    def test_empty_fields_ignored(self) -> None:
        card = {"cardTitle": "Test", "cardStatus": "", "cardRisk": "High", "cardLead": ""}
        q = build_bridge_query_from_card(card)
        assert "Test" in q
        assert "High" in q
        assert "cardStatus" not in q

    def test_no_invented_terms(self) -> None:
        card = {"cardTitle": "VPN Issue"}
        q = build_bridge_query_from_card(card)
        assert "urgent" not in q.lower()
        assert "critical" not in q.lower()


class TestBridgeRetrieval:
    def test_returns_evidence_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sr = os.path.join(tmp, "KnowledgeStore"); os.makedirs(sr, exist_ok=True)
            _setup(sr)
            pack = run_bridge_retrieval(query_text="Fixture message", store_root=sr, limit=5)
            assert pack["_schema"] == "export.bridgeEvidencePack.v1"
            assert pack["evidenceCount"] > 0

    def test_evidence_has_pointers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sr = os.path.join(tmp, "KnowledgeStore"); os.makedirs(sr, exist_ok=True)
            _setup(sr)
            pack = run_bridge_retrieval(query_text="Fixture message", store_root=sr, limit=5)
            for item in pack["evidenceItems"]:
                assert item.get("chunkKey")
                assert item.get("recordKey") or item.get("extractKey")

    def test_respects_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sr = os.path.join(tmp, "KnowledgeStore"); os.makedirs(sr, exist_ok=True)
            _setup(sr)
            pack = run_bridge_retrieval(query_text="Fixture message", store_root=sr, limit=3)
            assert pack["evidenceCount"] <= 3

    def test_card_plus_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sr = os.path.join(tmp, "KnowledgeStore"); os.makedirs(sr, exist_ok=True)
            _setup(sr)
            card = {"cardTitle": "Fixture message"}
            pack = run_bridge_retrieval(card_context=card, question="What's happening?", store_root=sr)
            assert pack["mode"] == "card_plus_question"
            assert "Fixture message" in pack["queryText"]

    def test_card_context_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sr = os.path.join(tmp, "KnowledgeStore"); os.makedirs(sr, exist_ok=True)
            _setup(sr)
            card = {"cardTitle": "Fixture"}
            pack = run_bridge_retrieval(card_context=card, store_root=sr)
            assert pack["mode"] == "card_context"

    def test_free_query_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sr = os.path.join(tmp, "KnowledgeStore"); os.makedirs(sr, exist_ok=True)
            _setup(sr)
            pack = run_bridge_retrieval(query_text="Fixture", store_root=sr)
            assert pack["mode"] == "free_query"

    def test_missing_index_clean_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sr = os.path.join(tmp, "KnowledgeStore"); os.makedirs(sr, exist_ok=True)
            pack = run_bridge_retrieval(query_text="test", store_root=sr)
            assert pack["evidenceCount"] == 0
            assert len(pack.get("warnings", [])) > 0

    def test_safety_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sr = os.path.join(tmp, "KnowledgeStore"); os.makedirs(sr, exist_ok=True)
            _setup(sr)
            pack = run_bridge_retrieval(query_text="Fixture", store_root=sr)
            for k in ["mailboxWrites", "kanbanWrites", "cloudApiCalls", "rawSourcesRetained"]:
                assert pack["audit"][k] == 0, f"{k} != 0"
            assert pack["audit"]["outlookComUsed"] is False
            assert pack["audit"]["llmUsed"] is False
            assert pack["audit"]["answerGenerated"] is False
