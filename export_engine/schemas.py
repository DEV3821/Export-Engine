"""Schema scaffolds for the Local Knowledge Store Export Engine.

Each schema is a lightweight factory function returning a dict skeleton.
All schemas include audit fields where applicable.
"""

from typing import Any


# ── Audit / Safety block ───────────────────────────────────────────────

def _safety_block() -> dict[str, bool]:
    return {
        "mailboxWrite": False,
        "kanbanWrite": False,
        "rawSourceRetained": False,
    }


# ── Schema versions ────────────────────────────────────────────────────

SCHEMA_VERSION_SOURCE_CATALOG = "export.sourceCatalog.v1"
SCHEMA_VERSION_SOURCE_SCAN_RUN = "export.sourceScanRun.v1"
SCHEMA_VERSION_INGEST_PLAN = "export.ingestPlan.v1"
SCHEMA_VERSION_BACKFILL_STATE = "export.backfillState.v1"
SCHEMA_VERSION_REFRESH_STATE = "export.refreshState.v1"
SCHEMA_VERSION_KNOWLEDGE_RECORD = "export.knowledgeRecord.v1"
SCHEMA_VERSION_KNOWLEDGE_EXTRACT = "export.knowledgeExtract.v1"
SCHEMA_VERSION_CONVERSATION = "export.conversation.v1"
SCHEMA_VERSION_RETRIEVAL_CHUNK = "export.retrievalChunk.v1"
SCHEMA_VERSION_INGEST_RUN = "export.ingestRun.v1"
SCHEMA_VERSION_REFRESH_RUN = "export.refreshRun.v1"


# ── Factory functions ──────────────────────────────────────────────────


def new_source_catalog_entry(*, folder_path: str, folder_type: str) -> dict[str, Any]:
    """Skeleton for a source catalog entry (single folder)."""
    return {
        "_schema": SCHEMA_VERSION_SOURCE_CATALOG,
        "folderPath": folder_path,
        "folderType": folder_type,
        "mailboxName": "",
        "storeType": "primary",
        "itemCount": 0,
        "scannedAt": "",
        "_safety": _safety_block(),
    }


def new_source_catalog(
    *,
    store_display_name: str = "",
    store_id_hash: str = "",
    scope: str = "primary_user_store_only",
) -> dict[str, Any]:
    """Full source catalog document for a completed scan."""
    return {
        "_schema": SCHEMA_VERSION_SOURCE_CATALOG,
        "sourceAdapter": "OutlookComPrimaryStoreSource",
        "scope": scope,
        "storeDisplayName": store_display_name,
        "storeIdHash": store_id_hash,
        "scannedAt": "",
        "folders": [],
        "excludedStores": [],
        "audit": {
            "mailboxWrite": False,
            "kanbanWrite": False,
            "cloudApiCalls": False,
            "rawSourceRetained": False,
        },
        "warnings": [],
        "errors": [],
    }


def new_source_scan_run(
    *,
    run_id: str = "",
    catalog_path: str = "",
) -> dict[str, Any]:
    """Source scan run manifest."""
    return {
        "_schema": SCHEMA_VERSION_SOURCE_SCAN_RUN,
        "sourceAdapter": "OutlookComPrimaryStoreSource",
        "scope": "primary_user_store_only",
        "startedAt": "",
        "finishedAt": "",
        "storeDisplayName": "",
        "storeIdHash": "",
        "foldersSeen": 0,
        "foldersIncluded": 0,
        "foldersExcluded": 0,
        "excludedStoresSeen": 0,
        "mailboxWrites": 0,
        "kanbanWrites": 0,
        "cloudApiCalls": 0,
        "rawMessagesStored": 0,
        "rawSourcesRetained": 0,
        "catalogPath": catalog_path,
        "warnings": [],
        "errors": [],
    }


def new_folder_entry(
    *,
    folder_key: str,
    folder_path: str,
    display_name: str,
    default_role: str = "unknown",
    item_count: int = 0,
    included: bool = True,
    excluded_reason: str = "",
) -> dict[str, Any]:
    """A single folder entry inside a source catalog."""
    return {
        "folderKey": folder_key,
        "folderPath": folder_path,
        "displayName": display_name,
        "defaultRole": default_role,
        "itemCount": item_count,
        "included": included,
        "excludedReason": excluded_reason,
    }


def new_excluded_store_entry(
    *,
    display_name: str,
    store_id_hash: str,
    reason: str = "additional_store_excluded_by_default",
) -> dict[str, Any]:
    """An excluded store entry inside a source catalog."""
    return {
        "displayName": display_name,
        "storeIdHash": store_id_hash,
        "reason": reason,
    }


# ── Phase 1.3 — Planner schemas ────────────────────────────────────────


def new_ingest_plan_v1(
    *,
    plan_id: str = "",
    source_catalog_path: str = "",
    store_display_name: str = "",
    store_id_hash: str = "",
    since: str = "",
    until: str = "",
    chunk_mode: str = "monthly",
) -> dict[str, Any]:
    """Full ingest plan document for a historic backfill plan."""
    return {
        "_schema": SCHEMA_VERSION_INGEST_PLAN,
        "planId": plan_id,
        "createdAt": "",
        "sourceCatalogPath": source_catalog_path,
        "scope": "primary_user_store_only",
        "storeDisplayName": store_display_name,
        "storeIdHash": store_id_hash,
        "since": since,
        "until": until,
        "chunkMode": chunk_mode,
        "chunkPurpose": "historic_backfill",
        "allUserFolders": True,
        "nearLiveAfterBackfill": {
            "enabled": True,
            "mode": "polling_incremental_refresh",
            "defaultPollingIntervalMinutes": 5,
            "minimumPollingIntervalMinutes": 1,
            "implementedInThisPhase": False,
        },
        "folders": [],
        "chunks": [],
        "estimatedItems": 0,
        "estimatedExtracts": 0,
        "audit": {
            "mailboxWrite": False,
            "kanbanWrite": False,
            "cloudApiCalls": False,
            "rawSourceRetained": False,
        },
        "warnings": [],
        "errors": [],
    }


def new_plan_chunk(
    *,
    chunk_id: str = "",
    folder_key: str = "",
    folder_path: str = "",
    display_name: str = "",
    default_role: str = "unknown",
    since: str = "",
    until: str = "",
    estimated_items: int = 0,
) -> dict[str, Any]:
    """A single monthly historic backfill chunk inside an ingest plan."""
    return {
        "chunkId": chunk_id,
        "folderKey": folder_key,
        "folderPath": folder_path,
        "displayName": display_name,
        "defaultRole": default_role,
        "since": since,
        "until": until,
        "chunkPurpose": "historic_backfill",
        "status": "pending",
        "estimatedItems": estimated_items,
        "estimatedExtracts": 0,
        "attempts": 0,
        "lastError": "",
        "completedAt": "",
    }


def new_backfill_state(
    *,
    active_plan_id: str = "",
    active_plan_path: str = "",
    since: str = "",
    until: str = "",
) -> dict[str, Any]:
    """Backfill state document tracking resume progress."""
    return {
        "_schema": SCHEMA_VERSION_BACKFILL_STATE,
        "createdAt": "",
        "updatedAt": "",
        "activePlanId": active_plan_id,
        "activePlanPath": active_plan_path,
        "scope": "primary_user_store_only",
        "chunkMode": "monthly",
        "chunkPurpose": "historic_backfill",
        "since": since,
        "until": until,
        "chunksTotal": 0,
        "chunksPending": 0,
        "chunksComplete": 0,
        "chunksFailed": 0,
        "nearLiveAfterBackfill": {
            "enabled": True,
            "mode": "polling_incremental_refresh",
            "defaultPollingIntervalMinutes": 5,
            "minimumPollingIntervalMinutes": 1,
            "refreshStatePrepared": True,
        },
        "chunks": {},
        "audit": {
            "mailboxWrite": False,
            "kanbanWrite": False,
            "cloudApiCalls": False,
            "rawSourceRetained": False,
        },
    }


def new_refresh_state() -> dict[str, Any]:
    """Refresh readiness state scaffold."""
    return {
        "_schema": SCHEMA_VERSION_REFRESH_STATE,
        "createdAt": "",
        "updatedAt": "",
        "scope": "primary_user_store_only",
        "mode": "polling_incremental_refresh",
        "status": "waiting_for_backfill",
        "enabledAfterBackfill": True,
        "defaultPollingIntervalMinutes": 5,
        "minimumPollingIntervalMinutes": 1,
        "lastRefreshStartedAt": "",
        "lastRefreshFinishedAt": "",
        "folders": {},
        "audit": {
            "mailboxWrite": False,
            "kanbanWrite": False,
            "cloudApiCalls": False,
            "rawSourceRetained": False,
        },
    }


# ── Phase 1.4 — Ingest schemas ───────────────────────────────────────────


def new_ingest_run_v1(
    *,
    export_run_id: str = "",
    store_root: str = "",
    plan_id: str = "",
    plan_path: str = "",
    backfill_state_path: str = "",
    since: str = "",
    until: str = "",
    limit: int | None = None,
    max_chunks: int | None = None,
    resume: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Full ingest run manifest for a record ingest run."""
    return {
        "_schema": SCHEMA_VERSION_INGEST_RUN,
        "exportRunId": export_run_id,
        "startedAt": "",
        "finishedAt": "",
        "storeRoot": store_root,
        "scope": "primary_user_store_only",
        "sourceAdapter": "OutlookComPrimaryStoreSource",
        "planId": plan_id,
        "planPath": plan_path,
        "backfillStatePath": backfill_state_path,
        "since": since,
        "until": until,
        "chunkPurpose": "historic_backfill",
        "resume": resume,
        "dryRun": dry_run,
        "limit": limit,
        "maxChunks": max_chunks,
        "chunksAttempted": 0,
        "chunksCompleted": 0,
        "chunksPartial": 0,
        "chunksFailed": 0,
        "recordsSeen": 0,
        "recordsExported": 0,
        "recordsChanged": 0,
        "recordsSkippedDuplicate": 0,
        "nonMailItemsSkipped": 0,
        "attachmentsSeen": 0,
        "attachmentMetadataCaptured": 0,
        "extractsSeen": 0,
        "extractsParsed": 0,
        "extractsMetadataOnly": 0,
        "extractsFailed": 0,
        "rawMessagesStored": 0,
        "rawSourcesRetained": 0,
        "rawAttachmentsSaved": 0,
        "tempFilesDeleted": 0,
        "mailboxWrites": 0,
        "kanbanWrites": 0,
        "cloudApiCalls": 0,
        "extractsParsed": 0,
        "conversationsWritten": 0,
        "retrievalChunksWritten": 0,
        "sqliteRowsWritten": 0,
        "vaultNotesUpdated": 0,
        "canvasFilesUpdated": 0,
        "recordsWritten": [],
        "warnings": [],
        "errors": [],
    }


def new_canonical_record(
    *,
    record_key: str = "",
    export_run_id: str = "",
    store_display_name: str = "",
    store_id_hash: str = "",
    folder_path: str = "",
    folder_key: str = "",
    subject: str = "",
) -> dict[str, Any]:
    """Full canonical knowledge record for an exported Outlook message."""
    return {
        "_schema": SCHEMA_VERSION_KNOWLEDGE_RECORD,
        "recordType": "outlookMessage",
        "recordKey": record_key,
        "exportRunId": export_run_id,
        "exportedAt": "",
        "source": {
            "system": "Outlook",
            "sourceAdapter": "OutlookComPrimaryStoreSource",
            "scope": "primary_user_store_only",
            "storeDisplayName": store_display_name,
            "storeIdHash": store_id_hash,
            "mailbox": "",
            "folderPath": folder_path,
            "folderKey": folder_key,
            "messageClass": "",
            "direction": "unknown",
            "readOnly": True,
        },
        "identity": {
            "outlookEntryIdHash": "",
            "internetMessageId": "",
            "conversationId": "",
            "conversationTopic": "",
            "conversationKey": "",
            "contentHash": "",
        },
        "headers": {
            "subject": subject,
            "from": {"displayName": "", "emailAddress": "", "emailAddressHash": ""},
            "to": [],
            "cc": [],
            "sentDateTime": "",
            "receivedDateTime": "",
            "creationTime": "",
            "lastModificationTime": "",
        },
        "content": {
            "bodyPreview": "",
            "bodyText": "",
            "bodyTextHash": "",
            "htmlStripped": True,
            "quotedTextIncluded": True,
            "cleaningNotes": [],
        },
        "attachments": {
            "count": 0,
            "metadataCaptured": True,
            "rawAttachmentsSaved": False,
            "parseDeferred": True,
            "items": [],
        },
        "extracts": [],
        "classification": {
            "keywords": [],
            "ticketNumbers": [],
            "ipAddresses": [],
            "serverNames": [],
            "aeTitles": [],
            "possibleSystems": [],
            "possibleTopics": [],
        },
        "retrieval": {"chunkIds": []},
        "vault": {"notePaths": [], "canvasPaths": []},
        "audit": {
            "mailboxWrite": False,
            "kanbanWrite": False,
            "cloudApiCalls": False,
            "rawMsgStored": False,
            "rawSourceRetained": False,
            "rawAttachmentsSaved": False,
            "parseWarnings": [],
            "needsReview": False,
        },
    }


# ── Phase 1.1 / 1.2 compatible factories (unchanged) ───────────────────


def new_ingest_plan(*, plan_id: str, source_catalog_id: str) -> dict[str, Any]:
    """Skeleton for an ingest plan (backward compat)."""
    return {
        "_schema": SCHEMA_VERSION_INGEST_PLAN,
        "planId": plan_id,
        "sourceCatalogId": source_catalog_id,
        "folders": [],
        "dateRange": {"start": "", "end": ""},
        "batchSize": 100,
        "status": "pending",
        "createdAt": "",
        "_safety": _safety_block(),
    }


def new_knowledge_record(
    *, record_id: str, folder_path: str, subject: str
) -> dict[str, Any]:
    """Skeleton for a canonical knowledge record."""
    return {
        "_schema": SCHEMA_VERSION_KNOWLEDGE_RECORD,
        "recordId": record_id,
        "folderPath": folder_path,
        "subject": subject,
        "sentAt": "",
        "receivedAt": "",
        "from": "",
        "to": [],
        "cc": [],
        "bodyPreview": "",
        "bodyHash": "",
        "hasAttachments": False,
        "attachmentCount": 0,
        "conversationId": "",
        "categories": [],
        "isRead": False,
        "isFlagged": False,
        "sizeBytes": 0,
        "importedAt": "",
        "_safety": _safety_block(),
    }


def new_knowledge_extract(
    *, extract_id: str, record_id: str, extract_type: str
) -> dict[str, Any]:
    """Skeleton for an extract sidecar."""
    return {
        "_schema": SCHEMA_VERSION_KNOWLEDGE_EXTRACT,
        "extractId": extract_id,
        "recordId": record_id,
        "extractType": extract_type,
        "contentHash": "",
        "extractedAt": "",
        "_safety": _safety_block(),
    }


def new_conversation(*, conversation_id: str, subject: str) -> dict[str, Any]:
    """Skeleton for a conversation record."""
    return {
        "_schema": SCHEMA_VERSION_CONVERSATION,
        "conversationId": conversation_id,
        "subject": subject,
        "participants": [],
        "messageCount": 0,
        "startAt": "",
        "endAt": "",
        "messages": [],
        "builtAt": "",
        "_safety": _safety_block(),
    }


def new_retrieval_chunk(
    *, chunk_id: str, record_id: str, chunk_index: int
) -> dict[str, Any]:
    """Skeleton for a retrieval chunk."""
    return {
        "_schema": SCHEMA_VERSION_RETRIEVAL_CHUNK,
        "chunkId": chunk_id,
        "recordId": record_id,
        "chunkIndex": chunk_index,
        "text": "",
        "embedding": [],
        "tokenCount": 0,
        "_safety": _safety_block(),
    }


def new_ingest_run(*, run_id: str) -> dict[str, Any]:
    """Skeleton for an ingest run manifest."""
    return {
        "_schema": SCHEMA_VERSION_INGEST_RUN,
        "runId": run_id,
        "startedAt": "",
        "completedAt": "",
        "foldersScanned": 0,
        "itemsIngested": 0,
        "itemsSkipped": 0,
        "itemsFailed": 0,
        "status": "pending",
        "_safety": _safety_block(),
    }


def new_refresh_run(*, run_id: str) -> dict[str, Any]:
    """Skeleton for a refresh run manifest."""
    return {
        "_schema": SCHEMA_VERSION_REFRESH_RUN,
        "runId": run_id,
        "startedAt": "",
        "completedAt": "",
        "foldersScanned": 0,
        "itemsNew": 0,
        "itemsUpdated": 0,
        "itemsDeleted": 0,
        "itemsFailed": 0,
        "status": "pending",
        "_safety": _safety_block(),
    }


# ── Phase 1.6 — Build schemas ───────────────────────────────────────────


def new_conversation_record(
    *,
    conversation_key: str = "",
    export_run_id: str = "",
    subject_canonical: str = "",
) -> dict[str, Any]:
    """Conversation record grouping related messages."""
    return {
        "_schema": SCHEMA_VERSION_CONVERSATION,
        "conversationKey": conversation_key,
        "exportRunId": export_run_id,
        "sourceScope": "primary_user_store_only",
        "createdAt": "",
        "updatedAt": "",
        "messageRecordKeys": [],
        "subjectCanonical": subject_canonical,
        "participantHashes": [],
        "folderKeys": [],
        "dateRange": {"first": "", "last": ""},
        "messageCount": 0,
        "attachmentCount": 0,
        "extractCount": 0,
        "retrievalChunkIds": [],
        "audit": {
            "mailboxWrite": False,
            "kanbanWrite": False,
            "cloudApiCalls": False,
            "rawSourceRetained": False,
        },
    }


def new_retrieval_chunk_record(
    *,
    chunk_key: str = "",
    export_run_id: str = "",
    parent_type: str = "message",
    parent_key: str = "",
) -> dict[str, Any]:
    """Retrieval chunk for RAG indexing."""
    return {
        "_schema": SCHEMA_VERSION_RETRIEVAL_CHUNK,
        "chunkKey": chunk_key,
        "exportRunId": export_run_id,
        "parentType": parent_type,
        "parentKey": parent_key,
        "conversationKey": "",
        "sourceRecordKeys": [],
        "sourceExtractKeys": [],
        "chunkOrdinal": 0,
        "text": "",
        "textHash": "",
        "title": "",
        "date": "",
        "folderPath": "",
        "folderKey": "",
        "participantsHash": "",
        "evidence": {
            "recordKey": "",
            "extractKey": None,
            "conversationKey": None,
            "sourcePath": "",
            "sourceKind": "",
        },
        "audit": {
            "mailboxWrite": False,
            "kanbanWrite": False,
            "cloudApiCalls": False,
            "rawSourceRetained": False,
        },
    }


def new_sqlite_index_run(
    *,
    index_run_id: str = "",
    export_run_id: str = "",
    sqlite_path: str = "",
) -> dict[str, Any]:
    """SQLite recall index run manifest."""
    return {
        "_schema": "export.sqliteIndexRun.v1",
        "indexRunId": index_run_id,
        "exportRunId": export_run_id,
        "startedAt": "",
        "finishedAt": "",
        "sqlitePath": sqlite_path,
        "chunksIndexed": 0,
        "recordsIndexed": 0,
        "conversationsIndexed": 0,
        "extractsIndexed": 0,
        "mailboxWrites": 0,
        "kanbanWrites": 0,
        "cloudApiCalls": 0,
        "rawSourcesRetained": 0,
        "warnings": [],
        "errors": [],
    }


# ── Phase 1.7 — Query schemas ────────────────────────────────────────────


def new_query_request(
    *,
    query_text: str = "",
    limit: int = 10,
) -> dict[str, Any]:
    """Query request schema for the evidence-bound local query adapter."""
    return {
        "_schema": "export.queryRequest.v1",
        "queryText": query_text,
        "limit": limit,
        "filters": {
            "dateFrom": None,
            "dateTo": None,
            "folderPath": None,
            "folderKey": None,
            "parentTypes": [],
            "sourceKinds": [],
            "includeExtracts": True,
            "includeConversations": True,
        },
        "options": {
            "requireEvidence": True,
            "includeChunkText": False,
            "maxChunkChars": 1200,
            "minScore": 0.0,
        },
        "audit": {
            "mailboxWrite": False,
            "kanbanWrite": False,
            "cloudApiCalls": False,
            "outlookComUsed": False,
            "hermesUsed": False,
            "llmUsed": False,
            "rawSourceRetained": False,
        },
    }


def new_query_result(
    *,
    query_id: str = "",
    query_text: str = "",
    store_root: str = "",
) -> dict[str, Any]:
    """Query result schema for the evidence-bound local query adapter."""
    return {
        "_schema": "export.queryResult.v1",
        "queryId": query_id,
        "queryText": query_text,
        "createdAt": "",
        "storeRoot": store_root,
        "sqlitePath": "",
        "resultCount": 0,
        "evidenceCount": 0,
        "results": [],
        "warnings": [],
        "errors": [],
        "audit": {
            "mailboxWrites": 0,
            "kanbanWrites": 0,
            "cloudApiCalls": 0,
            "outlookComUsed": False,
            "hermesUsed": False,
            "llmUsed": False,
            "rawSourcesRetained": 0,
        },
    }
