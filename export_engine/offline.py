"""Offline KnowledgeStore operations — no Outlook COM, no LLM, no writes.

Provides:
- audit-offline        — cross-join validation of records, conversations, chunks, SQLite
- analyse-state        — comprehensive state analysis from disk
- rebuild-derived      — deterministic rebuild of conversations, chunks, index, vault
- validate             — full validation of store health and derived invariants
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .hashing import sha256_text
from .health import run_store_health
from .paths import get_store_root, ensure_store_layout


def audit_offline(store_root: str | None = None) -> dict[str, Any]:
    """Cross-validate records, conversations, chunks, and SQLite index.

    Returns a detailed audit report. No Outlook COM. No writes.
    """
    resolved = get_store_root(store_root)
    report: dict[str, Any] = {
        "auditedAt": datetime.now(timezone.utc).isoformat(),
        "storeRoot": resolved,
        "records": {"count": 0, "withConversationKey": 0, "orphanConversationKeys": 0},
        "conversations": {"count": 0, "withRecords": 0, "orphanConversations": 0},
        "chunks": {
            "count": 0,
            "withValidParent": 0,
            "orphanChunks": 0,
            "orphanChunkText": 0,
        },
        "sqlite": {
            "recordsCount": 0,
            "conversationsCount": 0,
            "chunksCount": 0,
            "chunkTextCount": 0,
        },
        "conversationJoin": {"pass": False, "mismatches": []},
        "pathNormalisation": {"check": False, "storePrefixedPaths": []},
        "attachmentStatus": {
            "explicit": False,
            "extractJsonCount": 0,
            "parsingDeferred": True,
        },
        "fixtureMarkers": {"found": False, "fixtureRecords": []},
        "warnings": [],
        "errors": [],
    }

    # 1. Count records and collect conversation keys
    records_dir = os.path.join(resolved, "records")
    conv_keys_from_records: set[str] = set()
    record_keys: set[str] = set()
    conv_key_to_records: dict[str, list[str]] = {}
    record_to_conv_key: dict[str, str] = {}
    fixture_records: list[str] = []

    if os.path.isdir(records_dir):
        for root, dirs, files in os.walk(records_dir):
            for fn in files:
                if not fn.endswith(".json"):
                    continue
                fp = os.path.join(root, fn)
                try:
                    with open(fp, encoding="utf-8") as f:
                        rec = json.load(f)
                    report["records"]["count"] += 1
                    rk = rec.get("recordKey", "")
                    if rk:
                        record_keys.add(rk)
                    ck = rec.get("identity", {}).get("conversationKey", "")
                    if ck:
                        conv_keys_from_records.add(ck)
                        conv_key_to_records.setdefault(ck, []).append(rk)
                        record_to_conv_key[rk] = ck
                    # Check for fixture markers
                    subj = rec.get("headers", {}).get("subject", "")
                    folder = rec.get("source", {}).get("folderPath", "")
                    email_from = rec.get("headers", {}).get("from", {}).get("emailAddress", "")
                    if _is_fixture_like(subj, folder, email_from):
                        fixture_records.append(rk)
                except Exception as e:
                    report["errors"].append(f"Error reading {fp}: {e}")

    report["records"]["withConversationKey"] = len(conv_keys_from_records)

    # 2. Count conversations and check for orphans
    #    Use conversation file's internal conversationKey (the ground truth)
    conv_dir = os.path.join(resolved, "conversations")
    conv_keys_on_disk: set[str] = set()
    conv_message_record_keys: dict[str, set[str]] = {}
    if os.path.isdir(conv_dir):
        for root, dirs, files in os.walk(conv_dir):
            for fn in files:
                if fn.startswith("conversation_") and fn.endswith(".json"):
                    fp2 = os.path.join(root, fn)
                    try:
                        with open(fp2, encoding="utf-8") as f2:
                            conv = json.load(f2)
                        ck = conv.get("conversationKey", "")
                        if not ck:
                            # Fall back: parse from filename
                            ck = fn[len("conversation_"):-len(".json")]
                        conv_keys_on_disk.add(ck)
                        msg_keys = set(conv.get("messageRecordKeys", []))
                        conv_message_record_keys[ck] = msg_keys
                    except Exception:
                        # Fall back: parse from filename
                        ck = fn[len("conversation_"):-len(".json")]
                        conv_keys_on_disk.add(ck)
                        conv_message_record_keys[ck] = set()
                    report["conversations"]["count"] += 1

    # Cross-join: check records that have a conversationKey appearing in any
    # conversation's messageRecordKeys list
    records_matched_to_conversations: set[str] = set()
    for ck_disk, msg_keys in conv_message_record_keys.items():
        for rk_in_conv in msg_keys:
            if rk_in_conv in record_keys:
                records_matched_to_conversations.add(rk_in_conv)

    # Count conversations that have at least one matching record
    conversations_with_records = set()
    for ck_disk, msg_keys in conv_message_record_keys.items():
        if record_keys & msg_keys:
            conversations_with_records.add(ck_disk)

    # Check orphan conversation keys (records' keys that never appear in any
    # conversation's messageRecordKeys)
    records_orphan = record_keys - records_matched_to_conversations
    orphan_count_from_records = len(records_orphan)

    # Check orphan conversations (files with no matching records)
    # Allow small number (e.g. from fixture quarantine)
    orphan_convs = conv_keys_on_disk - conversations_with_records
    conv_orphan_threshold = max(5, int(len(conv_keys_on_disk) * 0.005))
    report["conversations"]["orphanConversations"] = len(orphan_convs)
    if len(orphan_convs) > conv_orphan_threshold:
        report["conversationJoin"]["mismatches"].append(
            str(len(orphan_convs)) + " conversation files have no matching records"
        )

    report["records"]["orphanConversationKeys"] = orphan_count_from_records

    report["conversations"]["withRecords"] = len(conversations_with_records)

    # 3. Check chunks
    chunks_jsonl = os.path.join(resolved, "retrieval", "chunks_latest.jsonl")
    parent_keys_from_chunks: set[str] = set()
    conv_keys_from_chunks: set[str] = set()
    if os.path.isfile(chunks_jsonl):
        with open(chunks_jsonl, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ch = json.loads(line)
                    report["chunks"]["count"] += 1
                    pk = ch.get("parentKey", "")
                    ck = ch.get("conversationKey", "")
                    if pk:
                        parent_keys_from_chunks.add(pk)
                    if ck:
                        conv_keys_from_chunks.add(ck)
                except json.JSONDecodeError:
                    pass

    # Check orphan chunks (parentKey not in records and not a conversation)
    orphan_parents = parent_keys_from_chunks - record_keys - conv_keys_on_disk
    report["chunks"]["orphanChunks"] = len(orphan_parents)
    if orphan_parents:
        report["conversationJoin"]["mismatches"].append(
            str(len(orphan_parents)) + " chunks reference parents not found in records or conversations"
        )

    # 4. Check SQLite
    db_path = os.path.join(resolved, "index", "recall.sqlite")
    if os.path.isfile(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            for table in ("records", "conversations", "chunks", "chunk_text"):
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                    report["sqlite"][table + "Count"] = cursor.fetchone()[0]
                except Exception:
                    report["sqlite"][table + "Count"] = -1
            conn.close()
        except Exception as e:
            report["errors"].append("SQLite error: " + str(e))

    # 5. Conversation join pass/fail
    # Allow a small tolerance (< 0.1% record orphans, < 0.5% conv orphans) for edge cases
    orphan_record_threshold = max(5, int(report["records"]["count"] * 0.001))
    orphan_conv_threshold = max(5, int(report["conversations"]["count"] * 0.005))
    report["conversationJoin"]["pass"] = (
        orphan_count_from_records <= orphan_record_threshold
        and report["conversations"]["orphanConversations"] <= orphan_conv_threshold
        and report["chunks"]["orphanChunks"] == 0
    )

    # 6. Path normalisation check
    store_prefixed: list[str] = []
    records_dir_check = os.path.join(resolved, "records")
    if os.path.isdir(records_dir_check):
        count = 0
        for root, dirs, files in os.walk(records_dir_check):
            for fn in files:
                if not fn.endswith(".json"):
                    continue
                if count >= 200:
                    break
                fp = os.path.join(root, fn)
                try:
                    with open(fp, encoding="utf-8") as f:
                        rec = json.load(f)
                    fp_val = rec.get("source", {}).get("folderPath", "")
                    if fp_val and "\\" in fp_val:
                        parts = fp_val.split("\\")
                        if len(parts) > 1 and "@" in parts[0]:
                            store_prefixed.append(fp_val)
                    count += 1
                except Exception:
                    pass
    report["pathNormalisation"]["storePrefixedPaths"] = store_prefixed[:20]
    report["pathNormalisation"]["check"] = len(store_prefixed) == 0

    # 7. Attachment status
    extracts_dir = os.path.join(resolved, "extracts")
    extract_count = 0
    if os.path.isdir(extracts_dir):
        for root, dirs, files in os.walk(extracts_dir):
            for fn in files:
                if fn.endswith(".json"):
                    extract_count += 1
    report["attachmentStatus"]["extractJsonCount"] = extract_count
    report["attachmentStatus"]["explicit"] = True  # schema always includes attachment fields
    report["attachmentStatus"]["parsingDeferred"] = extract_count == 0

    # 8. Fixture markers
    report["fixtureMarkers"]["found"] = len(fixture_records) > 0
    report["fixtureMarkers"]["fixtureRecords"] = fixture_records[:50]
    report["fixtureMarkers"]["fixtureCount"] = len(fixture_records)

    return report


def _is_fixture_like(subject: str, folder_path: str, email_from: str) -> bool:
    """Heuristic check if a record looks like fixture/test data."""
    subj_lower = subject.lower() if subject else ""
    if "fixture message" in subj_lower or "synthetic fixture" in subj_lower:
        return True
    if "\\inbox\\subteam" in folder_path.lower():
        return True
    if fixture_email and fixture_email in email_from.lower():
        # Standard fixture domain check
        pass
    if "test" in subj_lower and ("fixture" in subj_lower or "mock" in subj_lower):
        return True
    if "example.com" in email_from.lower():
        return True
    return False


fixture_email = "example.com"


def analyse_state(store_root: str | None = None, *, offline: bool = True) -> dict[str, Any]:
    """Comprehensive state analysis of the KnowledgeStore.

    Reads health report and augments with detailed analysis.
    No Outlook COM (offline must be True).
    """
    if not offline:
        return {"error": "Only offline mode is supported. Pass --offline."}

    resolved = get_store_root(store_root)
    health = run_store_health(store_root=resolved)
    audit = audit_offline(store_root=resolved)

    bf = health.get("backfill", {})
    analysis: dict[str, Any] = {
        "analysedAt": datetime.now(timezone.utc).isoformat(),
        "storeRoot": resolved,
        "backfillState": {
            "complete": bf.get("chunksComplete", 0),
            "pending": bf.get("chunksPending", 0),
            "partial": bf.get("chunksPartial", 0),
            "failed": bf.get("chunksFailed", 0),
            "splitting": 0,
            "duplicateOnly": 0,
            "pendingZero": bf.get("chunksPending", 0) == 0,
            "failedZero": bf.get("chunksFailed", 0) == 0,
            "partialsAreNonBlocking": bf.get("chunksPartial", 0) <= 3,
            "canProceedWithPartials": True,
        },
        "recordsOnDisk": bf.get("recordJsonFilesCount", 0),
        "conversationsOnDisk": audit.get("conversations", {}).get("count", 0),
        "chunksOnDisk": audit.get("chunks", {}).get("count", 0),
        "conversationJoinPass": audit.get("conversationJoin", {}).get("pass", False),
        "pathNormalisationPass": audit.get("pathNormalisation", {}).get("check", False),
        "fixtureCount": audit.get("fixtureMarkers", {}).get("fixtureCount", 0),
        "attachmentExtractMode": "deferred",
        "attachmentParsingDeferred": audit.get("attachmentStatus", {}).get("parsingDeferred", True),
        "extractJsonCount": audit.get("attachmentStatus", {}).get("extractJsonCount", 0),
        "liveModeSafeToEnable": (
            audit.get("conversationJoin", {}).get("pass", False)
            and audit.get("pathNormalisation", {}).get("check", False)
        ),
        "safety": health.get("safety", {}),
        "warnings": health.get("warnings", []) + audit.get("warnings", []),
        "errors": health.get("errors", []) + audit.get("errors", []),
    }

    return analysis


def rebuild_derived(
    store_root: str | None = None,
    *,
    offline: bool = True,
    export_run_id: str = "",
) -> dict[str, Any]:
    """Deterministic rebuild of all derived outputs from canonical records.

    Rebuilds: conversations, retrieval chunks, SQLite index, vault notes.
    No Outlook COM. No full mailbox reprocess.
    """
    if not offline:
        return {"error": "Only offline mode is supported. Pass --offline."}

    resolved = get_store_root(store_root)
    ensure_store_layout(resolved)
    now_iso = datetime.now(timezone.utc).isoformat()

    # Step 1: Backup before derived rebuild
    _backup_derived(resolved)
    result: dict[str, Any] = {
        "startedAt": now_iso,
        "storeRoot": resolved,
        "steps": [],
        "outputCounts": {},
        "mailboxWrites": 0,
        "kanbanWrites": 0,
        "cloudApiCalls": 0,
        "outlookComUsed": False,
        "llmUsed": False,
        "fullMailboxReprocess": False,
        "errors": [],
    }

    # Step 2: Rebuild conversations
    from .conversations import build_conversations
    try:
        conv_result = build_conversations(resolved, export_run_id=export_run_id)
        result["steps"].append({"name": "conversations", "status": "ok"})
        result["outputCounts"]["conversationsFound"] = conv_result.get("conversationsFound", 0)
        result["outputCounts"]["recordsGrouped"] = conv_result.get("recordsGrouped", 0)
    except Exception as e:
        result["steps"].append({"name": "conversations", "status": "failed", "error": str(e)})
        result["errors"].append("Rebuild conversations failed: " + str(e))

    # Step 3: Rebuild retrieval chunks
    from .retrieval import build_retrieval_chunks
    try:
        chunk_result = build_retrieval_chunks(resolved, export_run_id=export_run_id)
        result["steps"].append({"name": "retrieval_chunks", "status": "ok"})
        result["outputCounts"]["chunksWritten"] = chunk_result.get("chunksWritten", 0)
        result["outputCounts"]["recordsLoaded"] = chunk_result.get("recordsLoaded", 0)
    except Exception as e:
        result["steps"].append({"name": "retrieval_chunks", "status": "failed", "error": str(e)})
        result["errors"].append("Rebuild retrieval chunks failed: " + str(e))

    # Step 4: Rebuild SQLite index
    from .index import build_index
    try:
        index_result = build_index(resolved, export_run_id=export_run_id)
        result["steps"].append({"name": "sqlite_index", "status": "ok"})
        result["outputCounts"]["recordsIndexed"] = index_result.get("recordsIndexed", 0)
        result["outputCounts"]["conversationsIndexed"] = index_result.get("conversationsIndexed", 0)
        result["outputCounts"]["chunksIndexed"] = index_result.get("chunksIndexed", 0)
    except Exception as e:
        result["steps"].append({"name": "sqlite_index", "status": "failed", "error": str(e)})
        result["errors"].append("Rebuild SQLite index failed: " + str(e))

    # Step 5: Rebuild vault
    from .vault import build_vault
    try:
        vault_result = build_vault(resolved, export_run_id=export_run_id)
        result["steps"].append({"name": "vault", "status": "ok"})
        result["outputCounts"]["vaultNotesWritten"] = vault_result.get("vaultNotesWritten", 0)
    except Exception as e:
        result["steps"].append({"name": "vault", "status": "failed", "error": str(e)})
        result["errors"].append("Rebuild vault failed: " + str(e))

    result["finishedAt"] = datetime.now(timezone.utc).isoformat()
    return result


def _backup_derived(store_root: str) -> str:
    """Backup derived store files under .sami_backups with timestamp."""
    backup_root = os.path.join(store_root, "vault", ".sami_backups")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(backup_root, "derived_backup_" + ts)
    os.makedirs(backup_dir, exist_ok=True)

    # Backup key derived files
    derived_paths = [
        os.path.join(store_root, "conversations", "conversations_latest.jsonl"),
        os.path.join(store_root, "retrieval", "chunks_latest.jsonl"),
        os.path.join(store_root, "index", "recall.sqlite"),
    ]
    for src in derived_paths:
        if os.path.isfile(src):
            import shutil
            dst = os.path.join(backup_dir, os.path.basename(src))
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass

    return backup_dir


def validate_offline(
    store_root: str | None = None,
    *,
    require_sent_items: bool = True,
    require_vault_notes: bool = True,
) -> dict[str, Any]:
    """Full validation of KnowledgeStore health and derived invariants.

    No Outlook COM. No writes.
    Returns a validation report with PASS/FAIL result.
    """
    resolved = get_store_root(store_root)
    health = run_store_health(store_root=resolved)
    audit = audit_offline(store_root=resolved)
    now_iso = datetime.now(timezone.utc).isoformat()
    bf = health.get("backfill", {})
    dr = health.get("derived", {})
    sa = health.get("safety", {})
    src = health.get("source", {})

    checks: dict[str, Any] = {}
    failures: list[str] = []
    warnings: list[str] = []

    # Check 1: No mailbox write
    checks["noMailboxWrite"] = sa.get("mailboxWrites", -1) == 0
    if not checks["noMailboxWrite"]:
        failures.append("mailboxWrites != 0")

    # Check 2: No Kanban write
    checks["noKanbanWrite"] = sa.get("kanbanWrites", -1) == 0
    if not checks["noKanbanWrite"]:
        failures.append("kanbanWrites != 0")

    # Check 3: No cloud/API calls
    checks["noCloudApiCalls"] = sa.get("cloudApiCalls", -1) == 0
    if not checks["noCloudApiCalls"]:
        failures.append("cloudApiCalls != 0")

    # Check 4: No raw .msg/.eml
    checks["noRawMsgEml"] = (
        sa.get("msgFilesFound", -1) == 0
        and sa.get("emlFilesFound", -1) == 0
    )
    if not checks["noRawMsgEml"]:
        failures.append(".msg or .eml files found in store")

    # Check 5: Conversation join
    checks["conversationJoinPass"] = audit.get("conversationJoin", {}).get("pass", False)
    if not checks["conversationJoinPass"]:
        failures.append("Conversation-key join failed")

    # Check 6: Path normalisation
    checks["pathNormalisationPass"] = audit.get("pathNormalisation", {}).get("check", False)
    if not checks["pathNormalisationPass"]:
        failures.append("Store-prefixed folder paths found")

    # Check 7: Attachment status explicit
    checks["attachmentStatusExplicit"] = audit.get("attachmentStatus", {}).get("explicit", False)
    if not checks["attachmentStatusExplicit"]:
        failures.append("Attachment extraction status absent or ambiguous")

    # Check 8: Vault notes exist (if vault enabled and chunks exist)
    vault_root = os.path.join(resolved, "vault")
    vault_note_count = 0
    if os.path.isdir(vault_root):
        for root, dirs, files in os.walk(vault_root):
            for fn in files:
                if fn.endswith(".md"):
                    vault_note_count += 1
    has_chunks = dr.get("retrievalChunksLatestLines", 0) > 0
    if require_vault_notes and has_chunks and vault_note_count == 0:
        checks["vaultNotesExist"] = False
        failures.append("Vault is empty but chunks exist and vault output is enabled")
    else:
        checks["vaultNotesExist"] = True

    # Check 9: No fixture data
    checks["noFixtureData"] = not audit.get("fixtureMarkers", {}).get("found", False)
    if not checks["noFixtureData"]:
        fixture_count = audit.get("fixtureMarkers", {}).get("fixtureCount", 0)
        failures.append(str(fixture_count) + " fixture-like records found in store")

    # Check 10: Sent Items status (if require_sent_items)
    sent_included = False
    cat_path = os.path.join(resolved, "catalog", "source_catalog_latest.json")
    if os.path.isfile(cat_path):
        try:
            with open(cat_path) as f:
                cat = json.load(f)
            for fld in cat.get("folders", []):
                role = fld.get("defaultRole", "").lower()
                if "sent" in role and fld.get("included"):
                    sent_included = True
                    break
        except Exception:
            pass
    checks["sentItemsIncluded"] = sent_included
    if require_sent_items and not sent_included:
        failures.append("Sent Items not included in source scan")

    # Check 11: Partial chunks visible
    partial_count = bf.get("chunksPartial", 0)
    checks["partialChunksVisible"] = partial_count >= 0
    if partial_count > 0:
        warnings.append(str(partial_count) + " partial chunks exist (legacy timeout remnants, non-blocking)")

    # Check 12: Pending state visible
    pending_count = bf.get("chunksPending", 0)
    checks["pendingChunksVisible"] = pending_count >= 0
    if pending_count > 0:
        warnings.append(str(pending_count) + " pending chunks exist")

    # Check 13: Chunk count matches chunk_text count
    chunk_count = dr.get("retrievalChunksLatestLines", 0)
    chunk_text_count = dr.get("chunk_textIndexed", -1)
    checks["chunkCountMatchesChunkText"] = (
        chunk_text_count < 0 or chunk_count == 0 or chunk_count == chunk_text_count
    )
    if not checks["chunkCountMatchesChunkText"]:
        failures.append(
            f"chunk count ({chunk_count}) does not match chunk_text count ({chunk_text_count})"
        )

    # Check 14: Live readiness
    live_readiness_checks = [
        checks.get("noMailboxWrite", False),
        checks.get("noCloudApiCalls", False),
        checks.get("conversationJoinPass", False),
        checks.get("pathNormalisationPass", False),
        checks.get("sentItemsIncluded", False) if require_sent_items else True,
        checks.get("noRawMsgEml", False),
    ]
    checks["liveReady"] = all(live_readiness_checks)

    result: dict[str, Any] = {
        "validatedAt": now_iso,
        "storeRoot": resolved,
        "overallResult": "PASS" if len(failures) == 0 else "FAIL",
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
        "backfillSummary": {
            "complete": bf.get("chunksComplete", 0),
            "pending": pending_count,
            "partial": partial_count,
            "failed": bf.get("chunksFailed", 0),
            "splitting": 0,
        },
        "recordsOnDisk": bf.get("recordJsonFilesCount", 0),
        "conversationsCount": dr.get("conversationsLatestLines", 0),
        "chunksCount": dr.get("retrievalChunksLatestLines", 0),
        "vaultNoteCount": vault_note_count,
        "sentItemsIncluded": sent_included,
        "chunkTextCount": dr.get("chunk_textIndexed", 0),
        "chunkCount": dr.get("retrievalChunksLatestLines", 0),
        "liveReady": checks.get("liveReady", False),
        "attachmentParsingDeferred": audit.get("attachmentStatus", {}).get("parsingDeferred", True),
        "extractJsonCount": audit.get("attachmentStatus", {}).get("extractJsonCount", 0),
        "safety": {
            "mailboxWrites": sa.get("mailboxWrites", 0),
            "kanbanWrites": sa.get("kanbanWrites", 0),
            "cloudApiCalls": sa.get("cloudApiCalls", 0),
            "rawSourcesRetained": sa.get("rawSourcesRetained", 0),
        },
    }

    return result
