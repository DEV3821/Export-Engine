"""Limited canonical record ingest for the Local Knowledge Store.

Reads planned Outlook items (or fixture synthetic items) and writes hashed
canonical JSON message records.  Respects backfill state, supports --limit,
--resume, and --dry-run.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from .paths import get_store_root, ensure_store_layout
from .config import (
    OUTLOOK_SCOPE,
    DEFAULT_POLLING_INTERVAL,
    MINIMUM_POLLING_INTERVAL,
)
from .hashing import (
    sha256_text,
    stable_json_hash,
    make_folder_key,
    make_store_id_hash,
)


# ── Helpers ────────────────────────────────────────────────────────────


def _parse_date(s: str) -> datetime:
    parts = s.strip().split("-")
    return datetime(int(parts[0]), int(parts[1]), int(parts[2]), tzinfo=timezone.utc)


def _load_json(path: str) -> dict[str, Any] | None:
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Fixture record factory ─────────────────────────────────────────────


def _make_fixture_records(
    folder_entry: dict[str, Any],
    chunk: dict[str, Any],
    store_display_name: str,
    store_id_hash: str,
    export_run_id: str,
) -> list[dict[str, Any]]:
    """Generate synthetic records for fixture testing."""
    fk = folder_entry["folderKey"]
    fp = folder_entry["folderPath"]
    dn = folder_entry["displayName"]
    role = folder_entry.get("defaultRole", "custom")

    records: list[dict[str, Any]] = []
    est = chunk.get("estimatedItems", 3)

    for i in range(min(est, 5)):  # cap at 5 per chunk for tests
        ts = f"{chunk['since']}T10:0{i}:00"
        subj = f"Fixture message {i+1} from {dn}"
        raw = f"{fp}|{subj}|{ts}"
        rk = sha256_text(raw)
        body = f"This is synthetic fixture message {i+1} in folder {dn}."
        bh = sha256_text(body)
        cid = str(uuid.uuid4())

        rec = {
            "_schema": "export.knowledgeRecord.v1",
            "recordType": "outlookMessage",
            "recordKey": rk,
            "exportRunId": export_run_id,
            "exportedAt": datetime.now(timezone.utc).isoformat(),
            "source": {
                "system": "Outlook",
                "sourceAdapter": "OutlookComPrimaryStoreSource",
                "scope": "primary_user_store_only",
                "storeDisplayName": store_display_name,
                "storeIdHash": store_id_hash,
                "mailbox": "fixture@example.com",
                "folderPath": fp,
                "folderKey": fk,
                "messageClass": "IPM.Note",
                "direction": "received" if role in ("inbox",) else "sent",
                "readOnly": True,
            },
            "identity": {
                "outlookEntryIdHash": sha256_text(f"{rk}|entry"),
                "internetMessageId": f"<{rk}@fixture.local>",
                "conversationId": cid,
                "conversationTopic": subj,
                "conversationKey": sha256_text(cid),
                "contentHash": bh,
            },
            "headers": {
                "subject": subj,
                "from": {
                    "displayName": "Fixture Sender",
                    "emailAddress": f"sender{i}@example.com",
                    "emailAddressHash": sha256_text(f"sender{i}@example.com"),
                },
                "to": [{"displayName": "Fixture Recipient", "emailAddress": "recipient@example.com", "emailAddressHash": sha256_text("recipient@example.com")}],
                "cc": [],
                "sentDateTime": ts,
                "receivedDateTime": ts,
                "creationTime": ts,
                "lastModificationTime": ts,
            },
            "content": {
                "bodyPreview": body[:80],
                "bodyText": body,
                "bodyTextHash": bh,
                "htmlStripped": True,
                "quotedTextIncluded": False,
                "cleaningNotes": [],
            },
            "attachments": {
                "count": 1 if i == 0 else 0,
                "metadataCaptured": True,
                "rawAttachmentsSaved": False,
                "parseDeferred": True,
                "items": [{"originalName": "fixture.txt", "originalNameHash": sha256_text("fixture.txt"), "extension": ".txt", "sizeBytes": 42, "contentId": "", "contentHash": sha256_text("fixture content"), "rawSaved": False, "parseDeferred": True}] if i == 0 else [],
            },
            "extracts": [],
            "classification": {
                "keywords": [], "ticketNumbers": [], "ipAddresses": [],
                "serverNames": [], "aeTitles": [], "possibleSystems": [],
                "possibleTopics": [],
            },
            "retrieval": {"chunkIds": []},
            "vault": {"notePaths": [], "canvasPaths": []},
            "audit": {
                "mailboxWrite": False, "kanbanWrite": False,
                "cloudApiCalls": False, "rawMsgStored": False,
                "rawSourceRetained": False, "rawAttachmentsSaved": False,
                "parseWarnings": [], "needsReview": False,
            },
        }
        records.append(rec)
    return records


# ── Record writing + dedupe ────────────────────────────────────────────


def _write_record(
    store_root: str,
    record: dict[str, Any],
    existing_records: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    """Write a canonical record to disk.  Returns (record_key, action).

    action is one of: 'exported', 'changed', 'skipped_duplicate'
    """
    rk = record["recordKey"]
    ch = record["identity"]["contentHash"]

    # Build path: records/yyyy/mm/record_<recordKey>.json
    dt = record["headers"].get("sentDateTime") or record["headers"].get("receivedDateTime") or ""
    year, month = "unknown", "unknown"
    if dt and len(dt) >= 7:
        year = dt[:4]
        month = dt[5:7]

    rec_dir = os.path.join(store_root, "records", year, month)
    os.makedirs(rec_dir, exist_ok=True)
    rec_path = os.path.join(rec_dir, f"record_{rk}.json")

    # Check if exists
    if os.path.isfile(rec_path):
        with open(rec_path, encoding="utf-8") as f:
            existing = json.load(f)
        existing_ch = existing.get("identity", {}).get("contentHash", "")
        if existing_ch == ch:
            return rk, "skipped_duplicate"
        # Changed
        _write_json(rec_path, record)
        return rk, "changed"

    # New export
    _write_json(rec_path, record)
    return rk, "exported"


# ── Backfill state helpers ─────────────────────────────────────────────


def _load_backfill_state(store_root: str) -> dict[str, Any]:
    path = os.path.join(store_root, "state", "backfill_state.json")
    state = _load_json(path)
    if state is None:
        raise FileNotFoundError(
            f"No backfill state found at {path}. Run store-plan-ingest first."
        )
    return state


def _save_backfill_state(store_root: str, state: dict[str, Any]) -> None:
    path = os.path.join(store_root, "state", "backfill_state.json")
    state["updatedAt"] = datetime.now(timezone.utc).isoformat()
    _write_json(path, state)


# ── Main ingest ────────────────────────────────────────────────────────


def run_ingest(
    store_root: str | None = None,
    *,
    use_fixture: bool = False,
    limit: int | None = None,
    resume: bool = False,
    dry_run: bool = False,
    plan_path: str | None = None,
    max_chunks: int | None = None,
    chunk_id: str | None = None,
) -> dict[str, Any]:
    """Run a limited canonical record ingest.

    Returns the ingest run manifest.
    """
    resolved_root = get_store_root(store_root)
    ensure_store_layout(resolved_root)

    # Load plan
    if plan_path:
        plan = _load_json(plan_path)
        if plan is None:
            raise FileNotFoundError(f"Ingest plan not found at {plan_path}")
    else:
        plan = _load_json(os.path.join(resolved_root, "runs", "ingest_plan_latest.json"))
        if plan is None:
            raise FileNotFoundError(
                "No ingest plan found. Run store-plan-ingest first, "
                "or provide --plan."
            )

    # Validate plan
    if plan.get("scope") != "primary_user_store_only":
        raise ValueError(f"Plan scope is '{plan.get('scope')}', expected primary_user_store_only")
    if plan.get("chunkPurpose") != "historic_backfill":
        raise ValueError(f"Plan purpose is '{plan.get('chunkPurpose')}', expected historic_backfill")

    # Load backfill state
    backfill_path = os.path.join(resolved_root, "state", "backfill_state.json")
    state = _load_backfill_state(resolved_root)

    # Determine which chunks to process
    if chunk_id:
        chunks_to_process = [c for c in plan["chunks"] if c["chunkId"] == chunk_id]
        if not chunks_to_process:
            raise ValueError(f"Chunk ID {chunk_id} not found in plan")
    elif resume:
        chunks_to_process = [c for c in plan["chunks"] if c["status"] == "pending"]
    else:
        chunks_to_process = [c for c in plan["chunks"]]

    # Respect max_chunks
    if max_chunks and len(chunks_to_process) > max_chunks:
        chunks_to_process = chunks_to_process[:max_chunks]

    # Build run manifest
    now_iso = datetime.now(timezone.utc).isoformat()
    export_run_id = str(uuid.uuid4())

    plan_folders_by_key = {f["folderKey"]: f for f in plan.get("folders", [])}
    store_display_name = plan.get("storeDisplayName", "")
    store_id_hash = plan.get("storeIdHash", "")

    manifest: dict[str, Any] = {
        "_schema": "export.ingestRun.v1",
        "exportRunId": export_run_id,
        "startedAt": now_iso,
        "finishedAt": "",
        "storeRoot": resolved_root,
        "scope": "primary_user_store_only",
        "sourceAdapter": "OutlookComPrimaryStoreSource",
        "planId": plan.get("planId", ""),
        "planPath": plan_path or os.path.join(resolved_root, "runs", "ingest_plan_latest.json"),
        "backfillStatePath": backfill_path,
        "since": plan.get("since", ""),
        "until": plan.get("until", ""),
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
        "rawMessagesStored": 0,
        "rawSourcesRetained": 0,
        "rawAttachmentsSaved": 0,
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

    total_limit = limit or 0
    exported_count = 0

    for chunk in chunks_to_process:
        if total_limit and exported_count >= total_limit:
            break

        cid = chunk["chunkId"]
        fk = chunk["folderKey"]
        folder = plan_folders_by_key.get(fk, {})
        fp = chunk["folderPath"]
        dn = chunk["displayName"]
        role = chunk.get("defaultRole", "unknown")
        chunk_since = chunk["since"]
        chunk_until = chunk["until"]

        manifest["chunksAttempted"] += 1

        # Generate records
        if use_fixture:
            records = _make_fixture_records(
                folder, chunk,
                store_display_name, store_id_hash, export_run_id,
            )
        else:
            # Live Outlook enumeration — Phase 1.4 limited implementation
            records = _enumerate_outlook_items(
                folder, chunk,
                store_display_name, store_id_hash, export_run_id,
            )

        # Cap by remaining limit
        remaining = total_limit - exported_count if total_limit else len(records) + 1
        if len(records) > remaining:
            records = records[:remaining]

        chunk_records_seen = len(records)
        chunk_records_exported = 0
        chunk_records_changed = 0
        chunk_records_duplicate = 0
        chunk_attachments_seen = 0
        chunk_attachments_captured = 0
        chunk_non_mail = 0

        for rec in records:
            manifest["recordsSeen"] += 1
            chunk_records_seen += 1

            if dry_run:
                continue

            atts = rec.get("attachments", {})
            att_count = atts.get("count", 0)
            if att_count > 0:
                chunk_attachments_seen += att_count
                chunk_attachments_captured += 1

            rk, action = _write_record(resolved_root, rec, {})

            if action == "exported":
                chunk_records_exported += 1
                manifest["recordsExported"] += 1
                exported_count += 1
            elif action == "changed":
                chunk_records_changed += 1
                manifest["recordsChanged"] += 1
                exported_count += 1
            else:
                chunk_records_duplicate += 1
                manifest["recordsSkippedDuplicate"] += 1

            manifest["recordsWritten"].append(rk)

        manifest["attachmentsSeen"] += chunk_attachments_seen
        manifest["attachmentMetadataCaptured"] += chunk_attachments_captured

        # Update chunk state in backfill state
        chunk_exhausted = chunk_records_seen >= chunk.get("estimatedItems", 0) or not records
        hit_limit = total_limit and exported_count >= total_limit

        if dry_run:
            new_status = "pending"
        elif hit_limit and not chunk_exhausted:
            new_status = "partial"
        elif chunk_exhausted:
            new_status = "complete"
            manifest["chunksCompleted"] += 1
        else:
            new_status = "partial"
            manifest["chunksPartial"] += 1

        # Update chunk in state
        if cid in state.get("chunks", {}):
            state["chunks"][cid]["status"] = new_status
            state["chunks"][cid]["attempts"] = state["chunks"][cid].get("attempts", 0) + 1
            if new_status == "complete":
                state["chunks"][cid]["completedAt"] = datetime.now(timezone.utc).isoformat()

        if hit_limit:
            break

    # Finalize manifest
    manifest["finishedAt"] = datetime.now(timezone.utc).isoformat()

    # Recompute state counts
    chunks_dict = state.get("chunks", {})
    state["chunksPending"] = sum(1 for c in chunks_dict.values() if c.get("status") == "pending")
    state["chunksComplete"] = sum(1 for c in chunks_dict.values() if c.get("status") == "complete")
    state["chunksFailed"] = sum(1 for c in chunks_dict.values() if c.get("status") == "failed")

    if not dry_run:
        _save_backfill_state(resolved_root, state)

    # Write run manifest
    runs_dir = os.path.join(resolved_root, "runs")
    os.makedirs(runs_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    manifest_path = os.path.join(runs_dir, f"ingest_run_{ts}.json")
    _write_json(manifest_path, manifest)

    latest_path = os.path.join(runs_dir, "ingest_run_latest.json")
    _write_json(latest_path, manifest)

    return manifest


def _enumerate_outlook_items(
    folder: dict[str, Any],
    chunk: dict[str, Any],
    store_display_name: str,
    store_id_hash: str,
    export_run_id: str,
) -> list[dict[str, Any]]:
    """Enumerate real Outlook items for a folder+date chunk.

    Uses a COM folder index built from rootFolder by canonical path.
    """
    from .outlook_com_source import (
        outlook_available, _win32com, normalise_outlook_folder_path,
        resolve_com_folder_by_path, build_folder_index,
    )

    if not outlook_available():
        return []  # No items when Outlook unavailable

    outlook = _win32com.Dispatch("Outlook.Application")
    namespace = outlook.GetNamespace("MAPI")

    inbox = namespace.GetDefaultFolder(6)
    store = inbox.Store
    root = store.GetRootFolder()

    # Build folder index keyed by lower-cased canonical path
    idx, _ = build_folder_index(root, store_display_name=store_display_name)
    fp = chunk.get("folderPath", "")
    canonical = normalise_outlook_folder_path(fp)
    # The plan may contain legacy store-prefixed paths — normalise
    canonical = normalise_outlook_folder_path(canonical, store_display_name=store_display_name)

    # Look up in index
    folder_entry = idx.get(canonical.casefold())
    if folder_entry is None:
        return []

    # Resolve the actual COM folder
    target = resolve_com_folder_by_path(root, canonical)
    if target is None:
        return []

    # Apply date filter with half-open range
    since = chunk.get("since", "")
    until = chunk.get("until", "")

    records: list[dict[str, Any]] = []
    try:
        all_items = target.Items

        # Try Restrict first; fall back to Python-side filter if 0 items
        items = all_items
        use_python_filter = False
        if since and until:
            try:
                from datetime import timedelta
                since_dt_o = _parse_date(since)
                until_dt_o = _parse_date(until) + timedelta(days=1)
                since_str = since_dt_o.strftime("%m/%d/%Y %H:%M %p")
                until_str = until_dt_o.strftime("%m/%d/%Y %H:%M %p")
                role = chunk.get("defaultRole", "custom")
                date_field = "SentOn" if role in ("sent",) else "ReceivedTime"
                filter_str = f"[{date_field}] >= '{since_str}' AND [{date_field}] < '{until_str}'"
                restricted = all_items.Restrict(filter_str)
                if restricted.Count > 0:
                    items = restricted
                else:
                    use_python_filter = True
            except Exception:
                use_python_filter = True

        # Build the date bounds once for Python-side filtering
        py_sd = py_ud = None
        if use_python_filter and since and until:
            from datetime import timedelta
            py_sd = _parse_date(since)
            py_ud = _parse_date(until) + timedelta(days=1)

        for item in items:
            try:
                # Skip non-mail items
                msg_class = str(item.Class) if hasattr(item, "Class") else ""
                if "Mail" not in msg_class and "IPM.Note" not in str(getattr(item, "MessageClass", "")):
                    continue

                # Python-side date filter fallback
                if use_python_filter and py_sd is not None and py_ud is not None:
                    item_date = None
                    try:
                        date_field_name = "SentOn" if chunk.get("defaultRole") in ("sent",) else "ReceivedTime"
                        item_date = getattr(item, date_field_name, None)
                    except Exception:
                        pass
                    if item_date is not None:
                        try:
                            dt = item_date
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            if not (py_sd <= dt < py_ud):
                                continue
                        except Exception:
                            pass

                subj = str(getattr(item, "Subject", "") or "")
                sent_dt = str(getattr(item, "SentOn", "") or "")
                recv_dt = str(getattr(item, "ReceivedTime", "") or "")
                body = str(getattr(item, "Body", "") or "")
                body_preview = body[:200]

                entry_id = str(getattr(item, "EntryID", "") or "")
                rk = stable_json_hash({
                    "entryId": entry_id,
                    "folderKey": folder.get("folderKey", ""),
                    "subject": subj,
                })

                from_name = str(getattr(item, "SenderName", "") or "")
                from_email = str(getattr(item, "SenderEmailAddress", "") or "")

                role = chunk.get("defaultRole", "custom")
                direction = "sent" if role == "sent" else ("received" if role == "inbox" else "unknown")
                body_hash = sha256_text(body)

                rec = {
                    "_schema": "export.knowledgeRecord.v1",
                    "recordType": "outlookMessage",
                    "recordKey": rk,
                    "exportRunId": export_run_id,
                    "exportedAt": datetime.now(timezone.utc).isoformat(),
                    "source": {
                        "system": "Outlook",
                        "sourceAdapter": "OutlookComPrimaryStoreSource",
                        "scope": "primary_user_store_only",
                        "storeDisplayName": store_display_name,
                        "storeIdHash": store_id_hash,
                        "mailbox": store_display_name,
                        "folderPath": canonical,
                        "folderKey": folder.get("folderKey", ""),
                        "messageClass": str(getattr(item, "MessageClass", "")),
                        "direction": direction,
                        "readOnly": True,
                    },
                    "identity": {
                        "outlookEntryIdHash": sha256_text(entry_id),
                        "internetMessageId": str(getattr(item, "InternetMessageId", "") or ""),
                        "conversationId": str(getattr(item, "ConversationID", "") or ""),
                        "conversationTopic": str(getattr(item, "ConversationTopic", "") or ""),
                        "conversationKey": sha256_text(str(getattr(item, "ConversationID", "") or "")),
                        "contentHash": body_hash,
                    },
                    "headers": {
                        "subject": subj,
                        "from": {"displayName": from_name, "emailAddress": from_email, "emailAddressHash": sha256_text(from_email)},
                        "to": [], "cc": [],
                        "sentDateTime": sent_dt, "receivedDateTime": recv_dt,
                        "creationTime": str(getattr(item, "CreationTime", "") or ""),
                        "lastModificationTime": str(getattr(item, "LastModificationTime", "") or ""),
                    },
                    "content": {
                        "bodyPreview": body_preview, "bodyText": body, "bodyTextHash": body_hash,
                        "htmlStripped": True, "quotedTextIncluded": True, "cleaningNotes": [],
                    },
                    "attachments": {
                        "count": int(getattr(item, "Attachments", None).Count if hasattr(item, "Attachments") and item.Attachments else 0),
                        "metadataCaptured": True, "rawAttachmentsSaved": False,
                        "parseDeferred": True, "items": [],
                    },
                    "extracts": [],
                    "classification": {
                        "keywords": [], "ticketNumbers": [], "ipAddresses": [],
                        "serverNames": [], "aeTitles": [], "possibleSystems": [], "possibleTopics": [],
                    },
                    "retrieval": {"chunkIds": []},
                    "vault": {"notePaths": [], "canvasPaths": []},
                    "audit": {
                        "mailboxWrite": False, "kanbanWrite": False, "cloudApiCalls": False,
                        "rawMsgStored": False, "rawSourceRetained": False, "rawAttachmentsSaved": False,
                        "parseWarnings": [], "needsReview": False,
                    },
                }
                records.append(rec)
            except Exception:
                continue
    except Exception:
        pass

    return records



