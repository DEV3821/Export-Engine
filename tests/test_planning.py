"""Tests for planning.py — date chunking, plan creation, and fixture planning."""

import json
import os
import tempfile

from export_engine.planning import (
    create_backfill_plan,
    load_source_catalog,
    _monthly_chunks,
    _parse_date,
    _default_since_until,
    _make_chunk_id,
)


class TestDateChunking:
    """Monthly date chunking behaviour."""

    def test_exact_one_month(self) -> None:
        chunks = _monthly_chunks("2025-07-01", "2025-07-31")
        assert len(chunks) == 1
        assert chunks[0] == ("2025-07-01", "2025-07-31")

    def test_partial_first_month(self) -> None:
        chunks = _monthly_chunks("2025-07-05", "2025-07-31")
        assert len(chunks) == 1
        assert chunks[0] == ("2025-07-05", "2025-07-31")

    def test_partial_last_month(self) -> None:
        chunks = _monthly_chunks("2025-07-01", "2025-07-15")
        assert len(chunks) == 1
        assert chunks[0] == ("2025-07-01", "2025-07-15")

    def test_full_year_produces_13_chunks(self) -> None:
        """2025-07-05 to 2026-07-05 spans 13 calendar months."""
        chunks = _monthly_chunks("2025-07-05", "2026-07-05")
        assert len(chunks) == 13

    def test_first_chunk_partial_start(self) -> None:
        chunks = _monthly_chunks("2025-07-05", "2026-07-05")
        assert chunks[0] == ("2025-07-05", "2025-07-31")

    def test_last_chunk_partial_end(self) -> None:
        chunks = _monthly_chunks("2025-07-05", "2026-07-05")
        assert chunks[-1] == ("2026-07-01", "2026-07-05")

    def test_mid_month_chunks_align(self) -> None:
        chunks = _monthly_chunks("2025-07-05", "2026-07-05")
        # Middle chunks should be full months
        assert ("2025-08-01", "2025-08-31") in chunks
        assert ("2025-12-01", "2025-12-31") in chunks
        assert ("2026-06-01", "2026-06-30") in chunks

    def test_invalid_range_rejected(self) -> None:
        import pytest
        with pytest.raises(ValueError, match="must be before"):
            _monthly_chunks("2025-07-05", "2025-07-01")

    def test_default_since_until_length(self) -> None:
        since, until = _default_since_until()
        assert len(since.split("-")) == 3
        assert len(until.split("-")) == 3
        assert since < until

    def test_parse_date(self) -> None:
        d = _parse_date("2025-07-05")
        assert d.year == 2025
        assert d.month == 7
        assert d.day == 5


class TestChunkID:
    """Chunk IDs are deterministic and hash-based."""

    def test_chunk_id_deterministic(self) -> None:
        cid1 = _make_chunk_id("fk_abc", "2025-07-01", "2025-07-31")
        cid2 = _make_chunk_id("fk_abc", "2025-07-01", "2025-07-31")
        assert cid1 == cid2
        assert len(cid1) == 64

    def test_chunk_id_different_folder(self) -> None:
        cid1 = _make_chunk_id("fk_abc", "2025-07-01", "2025-07-31")
        cid2 = _make_chunk_id("fk_def", "2025-07-01", "2025-07-31")
        assert cid1 != cid2

    def test_chunk_id_different_date(self) -> None:
        cid1 = _make_chunk_id("fk_abc", "2025-07-01", "2025-07-31")
        cid2 = _make_chunk_id("fk_abc", "2025-08-01", "2025-08-31")
        assert cid1 != cid2

    def test_chunk_id_no_raw_names(self) -> None:
        """Chunk ID must not contain raw folder names."""
        cid = _make_chunk_id("fk_hash", "2025-07-01", "2025-07-31")
        assert "Inbox" not in cid
        assert "Sent" not in cid


class TestFixturePlanning:
    """Fixture-based planning creates correct numbers and files."""

    def test_plan_writes_plan_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            plan = create_backfill_plan(
                store_root, use_fixture=True,
                since="2025-07-05", until="2026-07-05",
            )
            runs_dir = os.path.join(store_root, "runs")
            plan_files = [f for f in os.listdir(runs_dir) if f.startswith("ingest_plan_")]
            assert len(plan_files) >= 1, "Plan file not written"
            assert os.path.isfile(os.path.join(runs_dir, "ingest_plan_latest.json"))

    def test_plan_writes_backfill_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            create_backfill_plan(
                store_root, use_fixture=True,
                since="2025-07-05", until="2026-07-05",
            )
            state_path = os.path.join(store_root, "state", "backfill_state.json")
            assert os.path.isfile(state_path)

    def test_plan_writes_refresh_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            create_backfill_plan(
                store_root, use_fixture=True,
                since="2025-07-05", until="2026-07-05",
            )
            refresh_path = os.path.join(store_root, "state", "refresh_state.json")
            assert os.path.isfile(refresh_path)

    def test_plan_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            plan = create_backfill_plan(
                store_root, use_fixture=True,
                since="2025-07-05", until="2026-07-05",
            )
            assert plan["_schema"] == "export.ingestPlan.v1"

    def test_backfill_state_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            create_backfill_plan(
                store_root, use_fixture=True,
                since="2025-07-05", until="2026-07-05",
            )
            state_path = os.path.join(store_root, "state", "backfill_state.json")
            with open(state_path) as f:
                state = json.load(f)
            assert state["_schema"] == "export.backfillState.v1"

    def test_refresh_state_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            create_backfill_plan(
                store_root, use_fixture=True,
                since="2025-07-05", until="2026-07-05",
            )
            refresh_path = os.path.join(store_root, "state", "refresh_state.json")
            with open(refresh_path) as f:
                rs = json.load(f)
            assert rs["_schema"] == "export.refreshState.v1"

    def test_plan_chunk_purpose_historic_backfill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            plan = create_backfill_plan(
                store_root, use_fixture=True,
                since="2025-07-05", until="2026-07-05",
            )
            assert plan["chunkPurpose"] == "historic_backfill"
            for c in plan["chunks"]:
                assert c["chunkPurpose"] == "historic_backfill"

    def test_refresh_state_status_waiting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            create_backfill_plan(
                store_root, use_fixture=True,
                since="2025-07-05", until="2026-07-05",
            )
            refresh_path = os.path.join(store_root, "state", "refresh_state.json")
            with open(refresh_path) as f:
                rs = json.load(f)
            assert rs["status"] == "waiting_for_backfill"
            assert rs["mode"] == "polling_incremental_refresh"

    def test_52_chunks_for_4_folders_and_13_months(self) -> None:
        """4 included folders x 13 monthly chunks = 52."""
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            plan = create_backfill_plan(
                store_root, use_fixture=True,
                since="2025-07-05", until="2026-07-05",
            )
            assert len(plan["folders"]) == 4, f"Expected 4 folders, got {len(plan['folders'])}"
            assert len(plan["chunks"]) == 52, f"Expected 52 chunks, got {len(plan['chunks'])}"

    def test_only_included_folders_in_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            plan = create_backfill_plan(
                store_root, use_fixture=True,
                since="2025-07-05", until="2026-07-05",
            )
            folder_paths = [f["folderPath"] for f in plan["folders"]]
            assert "\\Inbox" in folder_paths
            assert "\\Sent Items" in folder_paths
            assert "\\Inbox\\SubTeam" in folder_paths
            assert "\\Inbox\\Projects" in folder_paths
            # Not included
            assert "\\Deleted Items" not in folder_paths
            assert "\\Junk Email" not in folder_paths
            assert "\\Drafts" not in folder_paths
            assert "\\Calendar" not in folder_paths

    def test_plan_no_email_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            plan = create_backfill_plan(
                store_root, use_fixture=True,
                since="2025-07-05", until="2026-07-05",
            )
            text = json.dumps(plan)
            assert "bodyPreview" not in text
            assert "Here is the latest" not in text

    def test_plan_no_msg_eml(self) -> None:
        """No .msg or .eml references in plan."""
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            plan = create_backfill_plan(
                store_root, use_fixture=True,
                since="2025-07-05", until="2026-07-05",
            )
            text = json.dumps(plan)
            assert ".msg" not in text
            assert ".eml" not in text

    def test_near_live_polling_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            plan = create_backfill_plan(
                store_root, use_fixture=True,
                since="2025-07-05", until="2026-07-05",
            )
            nlb = plan["nearLiveAfterBackfill"]
            assert nlb["enabled"] is True
            assert nlb["mode"] == "polling_incremental_refresh"
            assert nlb["defaultPollingIntervalMinutes"] == 5
            assert nlb["minimumPollingIntervalMinutes"] == 1

    def test_audit_flags_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            plan = create_backfill_plan(
                store_root, use_fixture=True,
                since="2025-07-05", until="2026-07-05",
            )
            assert plan["audit"]["mailboxWrite"] is False
            assert plan["audit"]["kanbanWrite"] is False
            assert plan["audit"]["cloudApiCalls"] is False
            assert plan["audit"]["rawSourceRetained"] is False


class TestPlanWithoutCatalog:
    """Behaviour when no source catalog exists."""

    def test_raises_file_not_found(self) -> None:
        import pytest
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(os.path.join(store_root, "catalog"), exist_ok=True)
            with pytest.raises(FileNotFoundError, match="No source catalog found"):
                create_backfill_plan(store_root)
