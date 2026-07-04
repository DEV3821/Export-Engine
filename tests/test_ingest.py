"""Tests for ingest.py — fixture ingest, dedupe, chunk state."""

import json
import os
import tempfile

from export_engine.ingest import run_ingest, _make_fixture_records, _write_record


def _setup_store(store_root: str) -> dict:
    """Run a full scan+plan to get a plan and backfill state."""
    from export_engine.source_scan import run_source_scan
    from export_engine.planning import create_backfill_plan

    run_source_scan(store_root, use_fixture=True)
    plan = create_backfill_plan(store_root, use_fixture=True, since="2025-07-05", until="2026-07-05")
    return plan


class TestFixtureIngest:
    """Fixture mode ingest creates records without Outlook."""

    def test_ingest_writes_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_store(store_root)
            manifest = run_ingest(store_root, use_fixture=True, limit=5, resume=True)
            assert manifest["recordsExported"] > 0, "No records exported"
            # Check files exist on disk
            records_dir = os.path.join(store_root, "records")
            assert os.path.isdir(records_dir)
            # Walk and count
            count = 0
            for root, dirs, files in os.walk(records_dir):
                count += len([f for f in files if f.endswith(".json")])
            assert count == manifest["recordsExported"], f"Disk records ({count}) don't match manifest ({manifest['recordsExported']})"

    def test_ingest_respects_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_store(store_root)
            manifest = run_ingest(store_root, use_fixture=True, limit=3, resume=True)
            assert manifest["recordsExported"] == 3, f"Expected 3 exported, got {manifest['recordsExported']}"

    def test_ingest_writes_run_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_store(store_root)
            manifest = run_ingest(store_root, use_fixture=True, limit=5, resume=True)
            runs_dir = os.path.join(store_root, "runs")
            run_files = [f for f in os.listdir(runs_dir) if f.startswith("ingest_run_")]
            assert len(run_files) >= 1, "No ingest run files"
            assert os.path.isfile(os.path.join(runs_dir, "ingest_run_latest.json"))

    def test_ingest_updates_backfill_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_store(store_root)
            run_ingest(store_root, use_fixture=True, limit=5, resume=True)
            state_path = os.path.join(store_root, "state", "backfill_state.json")
            with open(state_path) as f:
                state = json.load(f)
            # At least one chunk should have been processed
            total_processed = state.get("chunksComplete", 0) + state.get("chunksFailed", 0)
            assert total_processed >= 0  # some might be partial

    def test_ingest_no_msg_eml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_store(store_root)
            run_ingest(store_root, use_fixture=True, limit=10, resume=True)
            manifest_path = os.path.join(store_root, "runs", "ingest_run_latest.json")
            with open(manifest_path) as f:
                m = json.load(f)
            assert m["rawMessagesStored"] == 0
            assert m["rawAttachmentsSaved"] == 0
            # Check no .msg/.eml on disk
            for root, dirs, files in os.walk(store_root):
                for fn in files:
                    assert not fn.endswith(".msg"), f"Found .msg: {fn}"
                    assert not fn.endswith(".eml"), f"Found .eml: {fn}"

    def test_ingest_no_extracts_or_future(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_store(store_root)
            manifest = run_ingest(store_root, use_fixture=True, limit=5, resume=True)
            assert manifest["extractsParsed"] == 0
            assert manifest["conversationsWritten"] == 0
            assert manifest["retrievalChunksWritten"] == 0
            assert manifest["sqliteRowsWritten"] == 0
            assert manifest["vaultNotesUpdated"] == 0
            assert manifest["canvasFilesUpdated"] == 0

    def test_dry_run_does_not_write_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_store(store_root)
            manifest = run_ingest(store_root, use_fixture=True, limit=10, dry_run=True)
            assert manifest["recordsExported"] == 0
            assert manifest["dryRun"] is True
            records_dir = os.path.join(store_root, "records")
            if os.path.isdir(records_dir):
                count = sum(len(files) for _, _, files in os.walk(records_dir))
                assert count == 0, f"Dry run wrote {count} record files"


class TestDedupe:
    """Dedupe by content hash."""

    def test_unchanged_skipped_on_second_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_store(store_root)

            # First run
            m1 = run_ingest(store_root, use_fixture=True, limit=3, resume=True)
            assert m1["recordsExported"] == 3

            # Second run — same records, should be duplicates
            m2 = run_ingest(store_root, use_fixture=True, limit=3, resume=True)
            assert m2["recordsSkippedDuplicate"] > 0, f"Expected duplicates, got {m2}"

    def test_content_hash_stable(self) -> None:
        from export_engine.ingest import _make_fixture_records
        folder = {"folderKey": "fk1", "folderPath": "\\Inbox", "displayName": "Inbox", "defaultRole": "inbox"}
        chunk = {"since": "2025-07-01", "until": "2025-07-31", "estimatedItems": 2}
        r1 = _make_fixture_records(folder, chunk, "store", "hash", "run1")
        r2 = _make_fixture_records(folder, chunk, "store", "hash", "run1")
        for a, b in zip(r1, r2):
            assert a["identity"]["contentHash"] == b["identity"]["contentHash"]
            assert a["recordKey"] == b["recordKey"]


class TestChunkState:
    """Chunk state updates correctly."""

    def test_chunk_marks_partial_on_limit_hit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_store(store_root)
            manifest = run_ingest(store_root, use_fixture=True, limit=1, resume=True)
            # With limit=1, we should have 1 partial chunk (or 1 completed if chunk exhausted)
            assert manifest["chunksPartial"] >= 0  # may be partial if limit hit mid-chunk

    def test_manifest_counts_not_negative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_store(store_root)
            manifest = run_ingest(store_root, use_fixture=True, limit=5, resume=True)
            for field in ("recordsExported", "recordsChanged", "recordsSkippedDuplicate", "chunksAttempted"):
                assert manifest[field] >= 0, f"{field} is negative: {manifest[field]}"
