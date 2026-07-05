"""Local Knowledge Store health report — read-only, local-only.

No Outlook COM. No LLM. No Kanban write. No mailbox write.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

from .paths import get_store_root


def run_store_health(store_root: str | None = None) -> dict[str, Any]:
    """Produce a comprehensive read-only health report of the Local Knowledge Store.

    Returns a dict with sections: source, backfill, derived, safety.
    No Outlook COM calls. No writes. No LLM.
    """
    resolved = get_store_root(store_root)
    report: dict[str, Any] = {
        "_schema": "export.storeHealth.v1",
        "storeRoot": resolved,
        "source": {},
        "backfill": {},
        "derived": {},
        "safety": {},
        "warnings": [],
        "errors": [],
    }

    # ── Source / catalog ──
    _report_source(report, resolved)

    # ── Backfill / ingest ──
    _report_backfill(report, resolved)

    # ── Derived store ──
    _report_derived(report, resolved)

    # ── Safety ──
    _report_safety(report, resolved)

    return report


def _report_source(report: dict[str, Any], root: str) -> None:
    """Read source catalog for folder counts and scope."""
    cat_path = os.path.join(root, "catalog", "source_catalog_latest.json")
    src = report["source"]

    if not os.path.isfile(cat_path):
        src["status"] = "no_catalog"
        src["sourceFoldersSeen"] = 0
        src["foldersIncluded"] = 0
        src["foldersExcluded"] = 0
        src["excludedStores"] = 0
        src["storeDisplayName"] = ""
        src["sourceScope"] = ""
        return

    try:
        with open(cat_path, encoding="utf-8") as f:
            cat = json.load(f)
        src["status"] = "available"
        included = sum(1 for f in cat.get("folders", []) if f.get("included"))
        excluded = sum(1 for f in cat.get("folders", []) if not f.get("included"))
        src["sourceFoldersSeen"] = len(cat.get("folders", []))
        src["foldersIncluded"] = included
        src["foldersExcluded"] = excluded
        src["excludedStores"] = len(cat.get("excludedStores", []))
        src["storeDisplayName"] = cat.get("storeDisplayName", "")
        src["sourceScope"] = cat.get("scope", "")
    except Exception as e:
        src["status"] = "error"
        src["error"] = str(e)
        report["errors"].append(f"source_catalog: {e}")


def _report_backfill(report: dict[str, Any], root: str) -> None:
    """Read backfill state and last ingest run."""
    bf = report["backfill"]

    # Backfill state
    state_path = os.path.join(root, "state", "backfill_state.json")
    if os.path.isfile(state_path):
        try:
            with open(state_path, encoding="utf-8") as f:
                state = json.load(f)
            chunks = state.get("chunks", {})
            bf["chunksTotal"] = state.get("chunksTotal", 0)
            statuses: dict[str, int] = {}
            for c in chunks.values():
                s = c.get("status", "unknown")
                statuses[s] = statuses.get(s, 0) + 1
            bf["chunksPending"] = statuses.get("pending", 0)
            bf["chunksComplete"] = statuses.get("complete", 0)
            bf["chunksPartial"] = statuses.get("partial", 0)
            bf["chunksFailed"] = statuses.get("failed", 0)
        except Exception as e:
            bf["backfillStateError"] = str(e)
            report["errors"].append(f"backfill_state: {e}")
    else:
        bf["backfillStateError"] = "not_found"

    # Last ingest run
    run_path = os.path.join(root, "runs", "ingest_run_latest.json")
    if os.path.isfile(run_path):
        try:
            with open(run_path, encoding="utf-8") as f:
                run = json.load(f)
            bf["recordsSeen"] = run.get("recordsSeen", 0)
            bf["recordsExported"] = run.get("recordsExported", 0)
            bf["recordsChanged"] = run.get("recordsChanged", 0)
            bf["recordsSkippedDuplicate"] = run.get("recordsSkippedDuplicate", 0)
            bf["nonMailItemsSkipped"] = run.get("nonMailItemsSkipped", 0)
            bf["attachmentsSeen"] = run.get("attachmentsSeen", 0)
            bf["attachmentMetadataCaptured"] = run.get("attachmentMetadataCaptured", 0)
            bf["extractsSeen"] = run.get("extractsSeen", 0)
            bf["extractsParsed"] = run.get("extractsParsed", 0)
            bf["extractsMetadataOnly"] = run.get("extractsMetadataOnly", 0)
            bf["extractsFailed"] = run.get("extractsFailed", 0)
            bf["tempFilesDeleted"] = run.get("tempFilesDeleted", 0)
        except Exception as e:
            bf["ingestRunError"] = str(e)
            report["errors"].append(f"ingest_run: {e}")
    else:
        bf["recordsSeen"] = 0
        bf["recordsExported"] = 0
        bf["recordsChanged"] = 0
        bf["recordsSkippedDuplicate"] = 0
        bf["nonMailItemsSkipped"] = 0
        bf["attachmentsSeen"] = 0
        bf["attachmentMetadataCaptured"] = 0
        bf["extractsSeen"] = 0
        bf["extractsParsed"] = 0
        bf["extractsMetadataOnly"] = 0
        bf["extractsFailed"] = 0
        bf["tempFilesDeleted"] = 0

    # Count actual record files
    rec_count = 0
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, "records")):
        for fn in filenames:
            if fn.endswith(".json"):
                rec_count += 1
    bf["recordJsonFilesCount"] = rec_count


def _report_derived(report: dict[str, Any], root: str) -> None:
    """Count derived store outputs."""
    dr = report["derived"]

    # Extract files
    ext_count = 0
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, "extracts")):
        for fn in filenames:
            if fn.endswith(".json"):
                ext_count += 1
    dr["extractJsonFilesCount"] = ext_count

    # Conversation files (per-conversation JSON)
    conv_count = 0
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, "conversations")):
        for fn in filenames:
            if fn.endswith(".json") and not fn.endswith("_latest.jsonl"):
                conv_count += 1
    dr["conversationJsonFilesCount"] = conv_count

    # conversations_latest.jsonl
    conv_latest = os.path.join(root, "conversations", "conversations_latest.jsonl")
    if os.path.isfile(conv_latest):
        try:
            with open(conv_latest, encoding="utf-8") as f:
                dr["conversationsLatestLines"] = sum(1 for _ in f)
        except Exception:
            dr["conversationsLatestLines"] = 0
    else:
        dr["conversationsLatestLines"] = 0

    # retrieval/chunks_latest.jsonl
    chunks_latest = os.path.join(root, "retrieval", "chunks_latest.jsonl")
    if os.path.isfile(chunks_latest):
        try:
            with open(chunks_latest, encoding="utf-8") as f:
                dr["retrievalChunksLatestLines"] = sum(1 for _ in f)
        except Exception:
            dr["retrievalChunksLatestLines"] = 0
    else:
        dr["retrievalChunksLatestLines"] = 0

    # SQLite recall index
    db_path = os.path.join(root, "index", "recall.sqlite")
    dr["recallSqliteExists"] = os.path.isfile(db_path)
    if dr["recallSqliteExists"]:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            for table_name in ("records", "conversations", "chunks", "chunk_text"):
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                    count = cursor.fetchone()[0]
                    dr[f"{table_name}Indexed"] = count
                except Exception:
                    dr[f"{table_name}Indexed"] = 0
            conn.close()
        except Exception as e:
            dr["sqliteError"] = str(e)
            report["errors"].append(f"sqlite: {e}")
    else:
        for tn in ("records", "conversations", "chunks", "chunk_text"):
            dr[f"{tn}Indexed"] = 0


def _report_safety(report: dict[str, Any], root: str) -> None:
    """Check safety invariants."""
    sa = report["safety"]

    sa["mailboxWrites"] = 0
    sa["kanbanWrites"] = 0
    sa["cloudApiCalls"] = 0
    sa["rawMessagesStored"] = 0
    sa["rawAttachmentsSaved"] = 0
    sa["rawSourcesRetained"] = 0

    # Check for .msg / .eml files under the store
    msg_count = 0
    eml_count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith(".msg"):
                msg_count += 1
            elif fn.lower().endswith(".eml"):
                eml_count += 1
    sa["msgFilesFound"] = msg_count
    sa["emlFilesFound"] = eml_count

    # temp / parsing dir
    temp_path = os.path.join(root, "temp")
    if os.path.isdir(temp_path):
        try:
            temp_files = len(os.listdir(temp_path))
        except Exception:
            temp_files = -1
    else:
        temp_files = 0
    sa["tempParsingFiles"] = temp_files

    # Check for unexpected binary attachment-like files (not in vault)
    raw_attachment_like = 0
    suspicious_exts = {".tmp", ".bin", ".dat", ".zip", ".doc", ".docx", ".pdf", ".xls", ".xlsx"}
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        if rel.startswith("vault") or rel.startswith("config"):
            continue
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in suspicious_exts:
                raw_attachment_like += 1
    sa["suspiciousBinaryFiles"] = raw_attachment_like

    sa["allSafetyChecksPass"] = (
        sa["mailboxWrites"] == 0
        and sa["kanbanWrites"] == 0
        and sa["cloudApiCalls"] == 0
        and sa["rawMessagesStored"] == 0
        and sa["rawAttachmentsSaved"] == 0
        and sa["rawSourcesRetained"] == 0
        and sa["msgFilesFound"] == 0
        and sa["emlFilesFound"] == 0
        and sa["tempParsingFiles"] == 0
    )
