"""Tests for schemas.py — Phase 1.3 schema additions."""

from export_engine.schemas import (
    new_ingest_plan_v1,
    new_plan_chunk,
    new_backfill_state,
    new_refresh_state,
    new_source_catalog_entry,
    new_source_catalog,
    new_ingest_plan,
    new_knowledge_record,
    new_conversation,
    new_retrieval_chunk,
    new_ingest_run,
    new_refresh_run,
)


class TestPhase13Schemas:
    """Phase 1.3 schema scaffold additions."""

    def test_ingest_plan_v1_structure(self) -> None:
        plan = new_ingest_plan_v1(
            plan_id="p1",
            source_catalog_path="/cat/path",
            store_display_name="test",
            store_id_hash="abc",
            since="2025-07-05",
            until="2026-07-05",
        )
        assert plan["_schema"] == "export.ingestPlan.v1"
        assert plan["planId"] == "p1"
        assert plan["sourceCatalogPath"] == "/cat/path"
        assert plan["storeDisplayName"] == "test"
        assert plan["storeIdHash"] == "abc"
        assert plan["since"] == "2025-07-05"
        assert plan["until"] == "2026-07-05"
        assert plan["chunkMode"] == "monthly"
        assert plan["chunkPurpose"] == "historic_backfill"
        assert plan["nearLiveAfterBackfill"]["enabled"] is True
        assert plan["nearLiveAfterBackfill"]["mode"] == "polling_incremental_refresh"
        assert plan["nearLiveAfterBackfill"]["defaultPollingIntervalMinutes"] == 5
        assert plan["nearLiveAfterBackfill"]["minimumPollingIntervalMinutes"] == 1
        assert plan["nearLiveAfterBackfill"]["implementedInThisPhase"] is False

    def test_ingest_plan_v1_audit(self) -> None:
        plan = new_ingest_plan_v1()
        assert plan["audit"]["mailboxWrite"] is False
        assert plan["audit"]["kanbanWrite"] is False
        assert plan["audit"]["cloudApiCalls"] is False
        assert plan["audit"]["rawSourceRetained"] is False

    def test_plan_chunk_structure(self) -> None:
        chunk = new_plan_chunk(
            chunk_id="cid1",
            folder_key="fk1",
            folder_path="\\Inbox",
            display_name="Inbox",
            since="2025-07-01",
            until="2025-07-31",
            estimated_items=5,
        )
        assert chunk["chunkId"] == "cid1"
        assert chunk["folderKey"] == "fk1"
        assert chunk["folderPath"] == "\\Inbox"
        assert chunk["displayName"] == "Inbox"
        assert chunk["since"] == "2025-07-01"
        assert chunk["until"] == "2025-07-31"
        assert chunk["chunkPurpose"] == "historic_backfill"
        assert chunk["status"] == "pending"
        assert chunk["estimatedItems"] == 5
        assert chunk["estimatedExtracts"] == 0
        assert chunk["attempts"] == 0
        assert chunk["lastError"] == ""

    def test_backfill_state_structure(self) -> None:
        state = new_backfill_state(
            active_plan_id="p1",
            active_plan_path="/path/to/plan",
            since="2025-07-05",
            until="2026-07-05",
        )
        assert state["_schema"] == "export.backfillState.v1"
        assert state["activePlanId"] == "p1"
        assert state["activePlanPath"] == "/path/to/plan"
        assert state["scope"] == "primary_user_store_only"
        assert state["chunkMode"] == "monthly"
        assert state["chunkPurpose"] == "historic_backfill"
        assert state["since"] == "2025-07-05"
        assert state["until"] == "2026-07-05"
        assert state["nearLiveAfterBackfill"]["refreshStatePrepared"] is True
        assert state["audit"]["mailboxWrite"] is False

    def test_refresh_state_structure(self) -> None:
        rs = new_refresh_state()
        assert rs["_schema"] == "export.refreshState.v1"
        assert rs["scope"] == "primary_user_store_only"
        assert rs["mode"] == "polling_incremental_refresh"
        assert rs["status"] == "waiting_for_backfill"
        assert rs["enabledAfterBackfill"] is True
        assert rs["defaultPollingIntervalMinutes"] == 5
        assert rs["minimumPollingIntervalMinutes"] == 1
        assert rs["audit"]["mailboxWrite"] is False

    def test_refresh_state_empty_folders(self) -> None:
        rs = new_refresh_state()
        assert rs["folders"] == {}
        assert rs["lastRefreshStartedAt"] == ""
        assert rs["lastRefreshFinishedAt"] == ""


class TestExistingSchemaCompat:
    """Phase 1.1/1.2 schemas still work."""

    SCHEMA_MAKERS = [
        ("source_catalog_entry", lambda: new_source_catalog_entry(folder_path="Inbox", folder_type="inbox")),
        ("source_catalog", lambda: new_source_catalog()),
        ("ingest_plan", lambda: new_ingest_plan(plan_id="p1", source_catalog_id="c1")),
        ("knowledge_record", lambda: new_knowledge_record(record_id="r1", folder_path="Inbox", subject="Test")),
        ("conversation", lambda: new_conversation(conversation_id="conv1", subject="Thread")),
        ("retrieval_chunk", lambda: new_retrieval_chunk(chunk_id="ch1", record_id="r1", chunk_index=0)),
        ("ingest_run", lambda: new_ingest_run(run_id="i1")),
        ("refresh_run", lambda: new_refresh_run(run_id="rf1")),
    ]

    def test_all_have_schema_version(self) -> None:
        for name, maker in self.SCHEMA_MAKERS:
            schema = maker()
            assert "_schema" in schema, f"{name} missing _schema"
            assert schema["_schema"].startswith("export."), f"{name} bad prefix"
            assert schema["_schema"].endswith(".v1"), f"{name} bad suffix"

    def test_all_have_safety(self) -> None:
        for name, maker in self.SCHEMA_MAKERS:
            schema = maker()
            safety = schema.get("_safety") or schema.get("audit")
            assert safety is not None, f"{name} missing safety"
            assert safety["mailboxWrite"] is False
            assert safety["kanbanWrite"] is False
