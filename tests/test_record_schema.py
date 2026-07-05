"""Tests for canonical record schema."""

from export_engine.schemas import new_canonical_record


class TestRecordSchema:
    """Canonical record schema structure."""

    def _make(self, **kw) -> dict:
        return new_canonical_record(**kw)

    def test_schema_version(self) -> None:
        r = self._make()
        assert r["_schema"] == "export.knowledgeRecord.v1"

    def test_record_type(self) -> None:
        r = self._make()
        assert r["recordType"] == "outlookMessage"

    def test_source_scope(self) -> None:
        r = self._make()
        assert r["source"]["scope"] == "primary_user_store_only"

    def test_source_read_only(self) -> None:
        r = self._make()
        assert r["source"]["readOnly"] is True

    def test_audit_mailbox_write_false(self) -> None:
        r = self._make()
        assert r["audit"]["mailboxWrite"] is False

    def test_audit_kanban_write_false(self) -> None:
        r = self._make()
        assert r["audit"]["kanbanWrite"] is False

    def test_audit_cloud_api_false(self) -> None:
        r = self._make()
        assert r["audit"]["cloudApiCalls"] is False

    def test_audit_raw_msg_false(self) -> None:
        r = self._make()
        assert r["audit"]["rawMsgStored"] is False

    def test_audit_raw_source_retained_false(self) -> None:
        r = self._make()
        assert r["audit"]["rawSourceRetained"] is False

    def test_audit_raw_attachments_saved_false(self) -> None:
        r = self._make()
        assert r["audit"]["rawAttachmentsSaved"] is False

    def test_retrieval_chunk_ids_empty(self) -> None:
        r = self._make()
        assert r["retrieval"]["chunkIds"] == []

    def test_vault_note_paths_empty(self) -> None:
        r = self._make()
        assert r["vault"]["notePaths"] == []

    def test_vault_canvas_paths_empty(self) -> None:
        r = self._make()
        assert r["vault"]["canvasPaths"] == []

    def test_extracts_empty(self) -> None:
        r = self._make()
        assert r["extracts"] == []

    def test_attachments_parse_deferred(self) -> None:
        r = self._make()
        assert r["attachments"]["parseDeferred"] is True
        assert r["attachments"]["rawAttachmentsSaved"] is False

    def test_record_key_sets_correctly(self) -> None:
        r = self._make(record_key="abc123")
        assert r["recordKey"] == "abc123"

    def test_subject_sets_correctly(self) -> None:
        r = self._make(subject="Test Subject")
        assert r["headers"]["subject"] == "Test Subject"

    def test_folder_path_sets(self) -> None:
        r = self._make(folder_path="\\Inbox\\Projects")
        assert r["source"]["folderPath"] == "\\Inbox\\Projects"
