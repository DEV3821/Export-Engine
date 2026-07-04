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


# ── Phase 1.1 compatible factories ─────────────────────────────────────


def new_ingest_plan(*, plan_id: str, source_catalog_id: str) -> dict[str, Any]:
    """Skeleton for an ingest plan."""
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
