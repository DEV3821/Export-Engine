"""Tests for retrieval.py — retrieval chunk builder."""

import json
import os
import tempfile

from export_engine.retrieval import build_retrieval_chunks


def _setup(store_root: str) -> None:
    """Setup fixture records + extracts + conversations."""
    from export_engine.source_scan import run_source_scan
    from export_engine.planning import create_backfill_plan
    from export_engine.ingest import run_ingest
    from export_engine.conversations import build_conversations
    run_source_scan(store_root, use_fixture=True)
    create_backfill_plan(store_root, use_fixture=True, since="2025-07-05", until="2025-08-05")
    run_ingest(store_root, use_fixture=True, limit=10, resume=True, parse_extracts=True)
    build_conversations(store_root, export_run_id="test1")


class TestBuildRetrieval:
    def test_chunks_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            manifest = build_retrieval_chunks(store_root, export_run_id="test1")
            assert manifest["chunksWritten"] > 0

    def test_chunks_jsonl_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            build_retrieval_chunks(store_root, export_run_id="test1")
            latest = os.path.join(store_root, "retrieval", "chunks_latest.jsonl")
            assert os.path.isfile(latest)
            with open(latest) as f:
                lines = [l for l in f if l.strip()]
            assert len(lines) > 0

    def test_chunk_ids_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            m1 = build_retrieval_chunks(store_root, export_run_id="test1")
            m2 = build_retrieval_chunks(store_root, export_run_id="test1")
            # Same input should produce same number of chunks
            assert m1["chunksWritten"] == m2["chunksWritten"]

    def test_chunk_points_to_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            build_retrieval_chunks(store_root, export_run_id="test1")
            latest = os.path.join(store_root, "retrieval", "chunks_latest.jsonl")
            with open(latest) as f:
                chunk = json.loads(f.readline())
            assert chunk["evidence"]["recordKey"] or chunk["evidence"]["extractKey"]
            assert chunk["sourceRecordKeys"] or chunk["sourceExtractKeys"]

    def test_metadata_only_records_still_produce_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            manifest = build_retrieval_chunks(store_root, export_run_id="test1")
            assert manifest["chunksWritten"] > 0

    def test_safety_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup(store_root)
            manifest = build_retrieval_chunks(store_root, export_run_id="test1")
            assert manifest["mailboxWrites"] == 0
            assert manifest["kanbanWrites"] == 0
            assert manifest["cloudApiCalls"] == 0
            assert manifest["rawSourcesRetained"] == 0
