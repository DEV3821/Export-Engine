"""Tests for query_adapter.py — evidence-bound local query adapter."""

import json
import os
import tempfile

from export_engine.query_adapter import run_local_query, build_evidence_pack


def _setup(store_root: str) -> None:
    """Full fixture setup for query testing."""
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


class TestQueryAdapter:
    def test_returns_structured_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            qr = run_local_query("Fixture message", store_root, limit=5)
            assert qr["_schema"] == "export.queryResult.v1"
            assert qr["resultCount"] > 0

    def test_has_query_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            qr = run_local_query("Fixture", store_root)
            assert len(qr["queryId"]) > 10

    def test_has_evidence_pointers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            qr = run_local_query("Fixture", store_root, limit=5)
            for r in qr["results"]:
                ev = r.get("evidence", {})
                assert ev.get("recordKey") or ev.get("extractKey") or ev.get("conversationKey")

    def test_respects_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            qr = run_local_query("Fixture", store_root, limit=3)
            assert qr["resultCount"] <= 3

    def test_include_chunk_text_false_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            qr = run_local_query("Fixture", store_root, limit=3, include_chunk_text=False)
            for r in qr["results"]:
                assert len(r["textPreview"]) <= 200  # default preview

    def test_include_chunk_text_true(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            qr = run_local_query("Fixture", store_root, limit=3, include_chunk_text=True, max_chunk_chars=500)
            for r in qr["results"]:
                assert len(r["textPreview"]) <= 500

    def test_max_chunk_chars_respected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            qr = run_local_query("Fixture", store_root, limit=3, include_chunk_text=True, max_chunk_chars=50)
            for r in qr["results"]:
                assert len(r["textPreview"]) <= 50

    def test_no_match_gives_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            qr = run_local_query("XYZZYX_NONEXISTENT_QUERY_12345", store_root)
            assert qr["resultCount"] == 0
            assert len(qr["warnings"]) > 0

    def test_missing_index_gives_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(os.path.join(store_root, "index"), exist_ok=True)
            qr = run_local_query("test", store_root)
            assert qr["resultCount"] == 0
            assert any("index not found" in w for w in qr["warnings"])

    def test_safety_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            qr = run_local_query("Fixture", store_root)
            assert qr["audit"]["mailboxWrites"] == 0
            assert qr["audit"]["kanbanWrites"] == 0
            assert qr["audit"]["cloudApiCalls"] == 0
            assert qr["audit"]["outlookComUsed"] is False
            assert qr["audit"]["hermesUsed"] is False
            assert qr["audit"]["llmUsed"] is False
            assert qr["audit"]["rawSourcesRetained"] == 0


class TestEvidencePack:
    def test_build_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            qr = run_local_query("Fixture", store_root, limit=3)
            pack = build_evidence_pack(qr, query_text="Fixture", limit=3)
            assert pack["evidenceCount"] > 0
            assert pack["audit"]["outlookComUsed"] is False
            for item in pack["evidence"]:
                assert "chunkKey" in item
                assert "evidence" in item


class TestQueryFilters:
    def test_date_from_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            qr_all = run_local_query("Fixture", store_root)
            qr_filtered = run_local_query("Fixture", store_root, date_from="2099-01-01")
            assert qr_filtered["resultCount"] <= qr_all["resultCount"]

    def test_no_extracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            qr_all = run_local_query("Fixture", store_root)
            qr_noex = run_local_query("Fixture", store_root, include_extracts=False)
            for r in qr_noex["results"]:
                assert r.get("parentType") != "attachmentExtract"

    def test_no_conversations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            qr_nocv = run_local_query("Fixture", store_root, include_conversations=False)
            for r in qr_nocv["results"]:
                assert r.get("parentType") != "conversation"
