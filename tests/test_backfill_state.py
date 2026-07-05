"""Tests for ingest run manifest and backfill state updates."""

from export_engine.schemas import new_ingest_run_v1, new_backfill_state


class TestIngestRunManifest:
    """Ingest run manifest schema."""

    def test_schema_version(self) -> None:
        m = new_ingest_run_v1()
        assert m["_schema"] == "export.ingestRun.v1"

    def test_scope(self) -> None:
        m = new_ingest_run_v1()
        assert m["scope"] == "primary_user_store_only"

    def test_counts_start_at_zero(self) -> None:
        m = new_ingest_run_v1()
        assert m["recordsSeen"] == 0
        assert m["recordsExported"] == 0
        assert m["recordsChanged"] == 0
        assert m["recordsSkippedDuplicate"] == 0
        assert m["chunksAttempted"] == 0

    def test_future_counts_zero(self) -> None:
        m = new_ingest_run_v1()
        assert m["extractsParsed"] == 0
        assert m["conversationsWritten"] == 0
        assert m["retrievalChunksWritten"] == 0
        assert m["sqliteRowsWritten"] == 0
        assert m["vaultNotesUpdated"] == 0
        assert m["canvasFilesUpdated"] == 0

    def test_safety_counts_zero(self) -> None:
        m = new_ingest_run_v1()
        assert m["mailboxWrites"] == 0
        assert m["kanbanWrites"] == 0
        assert m["cloudApiCalls"] == 0
        assert m["rawMessagesStored"] == 0
        assert m["rawSourcesRetained"] == 0
        assert m["rawAttachmentsSaved"] == 0

    def test_limit_and_resume(self) -> None:
        m = new_ingest_run_v1(limit=25, resume=True)
        assert m["limit"] == 25
        assert m["resume"] is True

    def test_dry_run(self) -> None:
        m = new_ingest_run_v1(dry_run=True)
        assert m["dryRun"] is True


class TestBackfillStateSchema:
    """Backfill state schema from Phase 1.3 (used by ingest)."""

    def test_schema_version(self) -> None:
        s = new_backfill_state()
        assert s["_schema"] == "export.backfillState.v1"

    def test_counts(self) -> None:
        s = new_backfill_state()
        assert s["chunksTotal"] == 0
        assert s["chunksPending"] == 0
        assert s["chunksComplete"] == 0
        assert s["chunksFailed"] == 0

    def test_chunks_dict(self) -> None:
        s = new_backfill_state()
        assert s["chunks"] == {}

    def test_near_live(self) -> None:
        s = new_backfill_state()
        assert s["nearLiveAfterBackfill"]["refreshStatePrepared"] is True
        assert s["nearLiveAfterBackfill"]["defaultPollingIntervalMinutes"] == 5
