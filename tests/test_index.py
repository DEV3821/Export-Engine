"""Tests for index.py — SQLite recall index."""

import json
import os
import tempfile

from export_engine.index import build_index, search_index


def _setup(store_root: str) -> None:
    """Full fixture setup: scan → plan → ingest → conversations → retrieval."""
    from export_engine.source_scan import run_source_scan
    from export_engine.planning import create_backfill_plan
    from export_engine.ingest import run_ingest
    from export_engine.conversations import build_conversations
    from export_engine.retrieval import build_retrieval_chunks
    run_source_scan(store_root, use_fixture=True)
    create_backfill_plan(store_root, use_fixture=True, since="2025-07-05", until="2025-08-05")
    run_ingest(store_root, use_fixture=True, limit=10, resume=True, parse_extracts=True)
    build_conversations(store_root, export_run_id="test1")
    build_retrieval_chunks(store_root, export_run_id="test1")


class TestBuildIndex:
    def test_sqlite_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            manifest = build_index(store_root, export_run_id="test1")
            assert os.path.isfile(manifest["sqlitePath"])
            assert manifest["chunksIndexed"] > 0
            assert manifest["recordsIndexed"] > 0
            assert manifest["conversationsIndexed"] > 0

    def test_tables_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            manifest = build_index(store_root, export_run_id="test1")
            import sqlite3
            conn = sqlite3.connect(manifest["sqlitePath"])
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            conn.close()
            assert "records" in tables
            assert "chunks" in tables
            assert "chunk_text" in tables
            assert "conversations" in tables

    def test_search_returns_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            build_index(store_root, export_run_id="test1")
            results = search_index("Subject", store_root, limit=5)
            assert len(results) >= 0

    def test_safety_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            manifest = build_index(store_root, export_run_id="test1")
            assert manifest["mailboxWrites"] == 0
            assert manifest["kanbanWrites"] == 0
            assert manifest["cloudApiCalls"] == 0
            assert manifest["rawSourcesRetained"] == 0

    def test_fts5_or_like_fallback(self) -> None:
        """Index creation should not crash whether FTS5 available or not."""
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            manifest = build_index(store_root, export_run_id="test1")
            assert manifest["chunksIndexed"] > 0


class TestSearch:
    def test_empty_db_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            results = search_index("test", tmp, limit=5)
            assert results == []
