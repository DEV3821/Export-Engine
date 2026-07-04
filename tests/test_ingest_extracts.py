"""Tests for ingest with --parse-extracts."""

import json
import os
import tempfile

from export_engine.ingest import run_ingest


def _setup_store(store_root: str) -> None:
    """Run a full scan+plan to get a plan and backfill state."""
    from export_engine.source_scan import run_source_scan
    from export_engine.planning import create_backfill_plan
    run_source_scan(store_root, use_fixture=True)
    create_backfill_plan(store_root, use_fixture=True, since="2025-07-05", until="2026-07-05")


class TestIngestExtracts:
    """Fixture ingest with --parse-extracts."""

    def test_parse_extracts_writes_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_store(store_root)
            manifest = run_ingest(store_root, use_fixture=True, limit=5, resume=True, parse_extracts=True)
            assert manifest["extractsSeen"] > 0, "No extracts created"
            assert manifest["tempFilesDeleted"] > 0, "Temp files not counted"
            # Check extract files exist on disk
            extract_dir = os.path.join(store_root, "extracts")
            assert os.path.isdir(extract_dir)
            count = 0
            for root, dirs, files in os.walk(extract_dir):
                count += len([f for f in files if f.endswith(".json")])
            assert count == manifest["extractsSeen"], f"Disk extracts ({count}) != manifest ({manifest['extractsSeen']})"

    def test_parse_extracts_no_raw_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_store(store_root)
            run_ingest(store_root, use_fixture=True, limit=10, resume=True, parse_extracts=True)
            # Check no raw files in temp/parsing
            temp_parsing = os.path.join(store_root, "temp", "parsing")
            if os.path.isdir(temp_parsing):
                remaining = os.listdir(temp_parsing)
                assert len(remaining) == 0, f"Temp files remain: {remaining}"
            # Check manifest
            manifest_path = os.path.join(store_root, "runs", "ingest_run_latest.json")
            with open(manifest_path) as f:
                m = json.load(f)
            assert m["rawAttachmentsSaved"] == 0
            assert m["rawSourcesRetained"] == 0
            assert m["rawMessagesStored"] == 0

    def test_parent_record_updated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_store(store_root)
            manifest = run_ingest(store_root, use_fixture=True, limit=10, resume=True, parse_extracts=True)
            # Read one of the written records
            records_dir = os.path.join(store_root, "records")
            found = False
            for root, dirs, files in os.walk(records_dir):
                for fn in files:
                    if fn.endswith(".json"):
                        with open(os.path.join(root, fn)) as f:
                            rec = json.load(f)
                        if rec.get("extracts"):
                            found = True
                            # Verify extract reference
                            assert rec["attachments"]["parseDeferred"] is False
                            for ex in rec["extracts"]:
                                assert "extractKey" in ex
                                assert "extractPath" in ex
                            break
                if found:
                    break
            assert found, "No record with extracts found"

    def test_future_counts_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_store(store_root)
            manifest = run_ingest(store_root, use_fixture=True, limit=5, resume=True, parse_extracts=True)
            assert manifest["conversationsWritten"] == 0
            assert manifest["retrievalChunksWritten"] == 0
            assert manifest["sqliteRowsWritten"] == 0
            assert manifest["vaultNotesUpdated"] == 0
            assert manifest["canvasFilesUpdated"] == 0

    def test_safety_counts_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_store(store_root)
            manifest = run_ingest(store_root, use_fixture=True, limit=5, resume=True, parse_extracts=True)
            assert manifest["mailboxWrites"] == 0
            assert manifest["kanbanWrites"] == 0
            assert manifest["cloudApiCalls"] == 0
            assert manifest["rawMessagesStored"] == 0
            assert manifest["rawAttachmentsSaved"] == 0
