"""Tests for schemas.py — schema scaffold safety fields."""

from export_engine.schemas import (
    new_source_catalog_entry,
    new_source_catalog,
    new_source_scan_run,
    new_folder_entry,
    new_excluded_store_entry,
    new_ingest_plan,
    new_knowledge_record,
    new_knowledge_extract,
    new_conversation,
    new_retrieval_chunk,
    new_ingest_run,
    new_refresh_run,
)


class TestSchemaSafetyFlags:
    """Every schema that includes audit fields must have safety flags set to False."""

    SCHEMA_MAKERS = [
        ("source_catalog_entry", lambda: new_source_catalog_entry(folder_path="Inbox", folder_type="inbox")),
        ("source_catalog", lambda: new_source_catalog()),
        ("ingest_plan", lambda: new_ingest_plan(plan_id="p1", source_catalog_id="c1")),
        ("knowledge_record", lambda: new_knowledge_record(record_id="r1", folder_path="Inbox", subject="Test")),
        ("knowledge_extract", lambda: new_knowledge_extract(extract_id="e1", record_id="r1", extract_type="body")),
        ("conversation", lambda: new_conversation(conversation_id="conv1", subject="Thread")),
        ("retrieval_chunk", lambda: new_retrieval_chunk(chunk_id="ch1", record_id="r1", chunk_index=0)),
        ("ingest_run", lambda: new_ingest_run(run_id="i1")),
        ("refresh_run", lambda: new_refresh_run(run_id="rf1")),
    ]

    def test_all_schemas_have_safety_block(self) -> None:
        for name, maker in self.SCHEMA_MAKERS:
            schema = maker()
            # New schemas use "audit" at top level instead of "_safety" on entry
            safety = schema.get("_safety") or schema.get("audit")
            assert safety is not None, f"{name} missing safety/audit block"
            assert "mailboxWrite" in safety, f"{name} missing mailboxWrite"
            assert "kanbanWrite" in safety, f"{name} missing kanbanWrite"
            assert "rawSourceRetained" in safety, f"{name} missing rawSourceRetained"

    def test_all_safety_flags_false(self) -> None:
        for name, maker in self.SCHEMA_MAKERS:
            schema = maker()
            safety = schema.get("_safety") or schema.get("audit")
            assert safety["mailboxWrite"] is False, f"{name} mailboxWrite not False"
            assert safety["kanbanWrite"] is False, f"{name} kanbanWrite not False"
            assert safety["rawSourceRetained"] is False, f"{name} rawSourceRetained not False"

    def test_all_schemas_have_schema_version(self) -> None:
        for name, maker in self.SCHEMA_MAKERS:
            schema = maker()
            assert "_schema" in schema, f"{name} missing _schema version key"
            assert schema["_schema"].startswith("export."), f"{name} _schema does not start with export."
            assert schema["_schema"].endswith(".v1"), f"{name} _schema does not end with .v1"


class TestNewSchemas:
    """Phase 1.2 schema additions."""

    def test_source_catalog_structure(self) -> None:
        cat = new_source_catalog(store_display_name="test", store_id_hash="abc")
        assert cat["storeDisplayName"] == "test"
        assert cat["storeIdHash"] == "abc"
        assert cat["scope"] == "primary_user_store_only"
        assert isinstance(cat["folders"], list)
        assert isinstance(cat["excludedStores"], list)
        assert cat["audit"]["mailboxWrite"] is False

    def test_source_scan_run_structure(self) -> None:
        run = new_source_scan_run(run_id="r1", catalog_path="/some/path")
        assert run["_schema"] == "export.sourceScanRun.v1"
        assert run["scope"] == "primary_user_store_only"
        assert run["foldersSeen"] == 0
        assert run["foldersIncluded"] == 0
        assert run["foldersExcluded"] == 0
        assert run["excludedStoresSeen"] == 0
        assert run["mailboxWrites"] == 0
        assert run["kanbanWrites"] == 0
        assert run["cloudApiCalls"] == 0
        assert run["rawMessagesStored"] == 0
        assert run["rawSourcesRetained"] == 0
        assert run["catalogPath"] == "/some/path"

    def test_folder_entry_structure(self) -> None:
        entry = new_folder_entry(
            folder_key="abc123",
            folder_path="\\Inbox\\Projects",
            display_name="Projects",
        )
        assert entry["folderKey"] == "abc123"
        assert entry["folderPath"] == "\\Inbox\\Projects"
        assert entry["displayName"] == "Projects"
        assert entry["defaultRole"] == "unknown"
        assert entry["included"] is True
        assert entry["excludedReason"] == ""

    def test_folder_entry_excluded(self) -> None:
        entry = new_folder_entry(
            folder_key="def456",
            folder_path="\\Deleted Items",
            display_name="Deleted Items",
            default_role="deleted",
            included=False,
            excluded_reason="excluded_by_default_role_deleted",
        )
        assert entry["included"] is False
        assert entry["excludedReason"] == "excluded_by_default_role_deleted"

    def test_excluded_store_entry(self) -> None:
        entry = new_excluded_store_entry(
            display_name="Shared Team Mailbox",
            store_id_hash="hash123",
        )
        assert entry["displayName"] == "Shared Team Mailbox"
        assert entry["storeIdHash"] == "hash123"
        assert entry["reason"] == "additional_store_excluded_by_default"


class TestExistingSchemaStructure:
    """Phase 1.1 schema structural checks (unchanged)."""

    def test_source_catalog_entry_structure(self) -> None:
        entry = new_source_catalog_entry(folder_path="Inbox", folder_type="inbox")
        assert entry["folderPath"] == "Inbox"
        assert entry["folderType"] == "inbox"
        assert entry["storeType"] == "primary"

    def test_knowledge_record_structure(self) -> None:
        rec = new_knowledge_record(record_id="r1", folder_path="Inbox", subject="Test")
        assert rec["recordId"] == "r1"
        assert rec["folderPath"] == "Inbox"
        assert rec["hasAttachments"] is False
        assert rec["attachmentCount"] == 0

    def test_ingest_plan_structure(self) -> None:
        plan = new_ingest_plan(plan_id="p1", source_catalog_id="c1")
        assert plan["status"] == "pending"
        assert plan["dateRange"] == {"start": "", "end": ""}

    def test_ingest_run_structure(self) -> None:
        run = new_ingest_run(run_id="i1")
        assert run["status"] == "pending"
        assert run["itemsIngested"] == 0

    def test_refresh_run_structure(self) -> None:
        run = new_refresh_run(run_id="rf1")
        assert run["status"] == "pending"
        assert run["itemsNew"] == 0
