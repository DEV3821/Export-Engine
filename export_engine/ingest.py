"""Limited canonical record ingest for the Local Knowledge Store.

Reads planned Outlook items (or fixture synthetic items) and writes hashed
canonical JSON message records.  Respects backfill state, supports --limit,
--resume, and --dry-run.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
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


# ── Atomic JSON write ─────────────────────────────────────────────────


def _write_json_atomic(path: str, data: Any) -> None:
    """Write JSON atomically: write to .tmp, flush, then rename.

    Prevents corruption if the process is killed mid-write.
    Falls back to direct write if atomic rename fails (e.g. on Windows temp dirs).
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except (OSError, PermissionError):
        # Fall back to direct write if rename fails
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


def _save_state_atomic(store_root: str, state: dict[str, Any]) -> None:
    """Atomic write of backfill state (rename-based, corruption-safe)."""
    path = os.path.join(store_root, "state", "backfill_state.json")
    state["updatedAt"] = datetime.now(timezone.utc).isoformat()
    _write_json_atomic(path, state)


# ── Recompute state summary counts ────────────────────────────────────


def _recompute_state_counts(state: dict[str, Any]) -> None:
    """Recompute summary counts from individual chunk statuses."""
    chunks_dict = state.get("chunks", {})
    state["chunksPending"] = sum(1 for c in chunks_dict.values() if c.get("status") == "pending")
    state["chunksComplete"] = sum(1 for c in chunks_dict.values() if c.get("status") == "complete")
    state["chunksPartial"] = sum(1 for c in chunks_dict.values() if c.get("status") == "partial")
    state["chunksFailed"] = sum(1 for c in chunks_dict.values() if c.get("status") == "failed")


# ── Outlook ingest context (reused across chunks in one command) ──────


_OUTLOOK_CONTEXT: dict[str, Any] | None = None


def open_outlook_context(
    store_display_name: str = "",
) -> dict[str, Any] | None:
    """Initialise Outlook COM once and build the folder index.

    Returns a context dict or None if Outlook is unavailable.
    The context is cached for the lifetime of the Python process so
    _enumerate_outlook_items can reuse it across chunks within one
    store-ingest command.
    """
    global _OUTLOOK_CONTEXT
    if _OUTLOOK_CONTEXT is not None:
        return _OUTLOOK_CONTEXT

    from .outlook_com_source import (
        outlook_available, _win32com, build_folder_index,
        normalise_outlook_folder_path,
    )

    if not outlook_available():
        _OUTLOOK_CONTEXT = None
        return None

    try:
        outlook = _win32com.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        inbox = namespace.GetDefaultFolder(6)
        store = inbox.Store
        root = store.GetRootFolder()
        idx, _ = build_folder_index(root, store_display_name=store_display_name)

        ctx: dict[str, Any] = {
            "outlook": outlook,
            "namespace": namespace,
            "inbox": inbox,
            "store": store,
            "root": root,
            "folder_index": idx,
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "read_only": True,
        }
        _OUTLOOK_CONTEXT = ctx
        return ctx
    except Exception as e:
        _OUTLOOK_CONTEXT = None
        return None


def close_outlook_context() -> None:
    """Clear the cached Outlook context."""
    global _OUTLOOK_CONTEXT
    _OUTLOOK_CONTEXT = None


def reset_outlook_context() -> None:
    """Force reset — used for testing or recovery."""
    global _OUTLOOK_CONTEXT
    _OUTLOOK_CONTEXT = None


# ── Enumerate Outlook items (with optional shared context) ────────────


def _enumerate_outlook_items(
    folder: dict[str, Any],
    chunk: dict[str, Any],
    store_display_name: str,
    store_id_hash: str,
    export_run_id: str,
    outlook_ctx: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Enumerate real Outlook items for a folder+date chunk.

    Reuses the provided outlook_ctx if given, otherwise falls back
    to creating a fresh COM dispatch (legacy behaviour).
    """
    from .outlook_com_source import (
        outlook_available, _win32com, normalise_outlook_folder_path,
        resolve_com_folder_by_path, build_folder_index,
    )

    if not outlook_available():
        return []

    # Use context's root and folder index if available
    if outlook_ctx is not None:
        root = outlook_ctx["root"]
        idx = outlook_ctx["folder_index"]
    else:
        outlook = _win32com.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        inbox = namespace.GetDefaultFolder(6)
        store = inbox.Store
        root = store.GetRootFolder()
        idx, _ = build_folder_index(root, store_display_name=store_display_name)

    fp = chunk.get("folderPath", "")
    canonical = normalise_outlook_folder_path(fp)
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
        # Try Restrict first. If Restrict returns 0 items reliably,
        # do NOT fall back to Python-side iteration of the full folder
        # (which is extremely slow for folders with thousands of items).
        # If the Restrict itself throws an exception, fall back to Python
        # iteration (belt-and-suspenders for edge cases).
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
                    # Restrict returned 0 items — genuinely empty date range.
                    # Do NOT fall back to Python-side full-folder iteration.
                    return []
            except Exception:
                # Restrict threw an exception — fall back to Python-side
                # filtering as a safety net.
                use_python_filter = True

        py_sd = py_ud = None
        if use_python_filter and since and until:
            from datetime import timedelta
            py_sd = _parse_date(since)
            py_ud = _parse_date(until) + timedelta(days=1)

        for item in items:
            try:
                msg_class = str(item.Class) if hasattr(item, "Class") else ""
                if "Mail" not in msg_class and "IPM.Note" not in str(getattr(item, "MessageClass", "")):
                    continue

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

                entry_id = str(getattr(item, "EntryID", "") or "")
                rk = stable_json_hash({
                    "entryId": entry_id,
                    "folderKey": folder.get("folderKey", ""),
                    "subject": subj,
                })

                # ── Pre-check: if record key already exists on disk,
                #    skip the expensive Body/attachment COM reads and
                #    build a minimal duplicate record ──
                dt_for_path = sent_dt or recv_dt or ""
                r_year, r_month = "unknown", "unknown"
                if dt_for_path and len(dt_for_path) >= 7:
                    r_year = dt_for_path[:4]
                    r_month = dt_for_path[5:7]
                existing_path = os.path.join(
                    get_store_root(),
                    "records", r_year, r_month, f"record_{rk}.json"
                )
                is_duplicate = os.path.isfile(existing_path)

                if is_duplicate:
                    body = ""
                    body_preview = ""
                    # Read existing body hash from the record file so
                    # _write_record sees a matching hash and skips the write
                    try:
                        with open(existing_path, encoding="utf-8") as ef:
                            existing_rec = json.load(ef)
                        body_hash = existing_rec.get("identity", {}).get("contentHash", sha256_text(""))
                    except Exception:
                        body_hash = sha256_text("")
                else:
                    body = str(getattr(item, "Body", "") or "")
                    body_preview = body[:200]
                    body_hash = sha256_text(body)

                from_name = str(getattr(item, "SenderName", "") or "")
                from_email = str(getattr(item, "SenderEmailAddress", "") or "")

                role = chunk.get("defaultRole", "custom")
                direction = "sent" if role == "sent" else ("received" if role == "inbox" else "unknown")
                # body_hash already set above — do not recompute

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
            except Exception as item_err:
                # Record item-level error but continue processing the chunk
                if "chunk_warnings" not in chunk:
                    chunk["chunk_warnings"] = []
                chunk["chunk_warnings"].append(f"Item error in {fp}: {item_err}")
                continue
    except Exception as chunk_err:
        # Chunk-level error — leave chunk in current state, log error
        if "chunk_errors" not in chunk:
            chunk["chunk_errors"] = []
        chunk["chunk_errors"].append(f"Chunk enumeration error for {fp}: {chunk_err}")
        return records  # Return whatever we got

    return records


# ── Per-chunk progress printing ───────────────────────────────────────


def _print_chunk_progress(
    chunk_index: int,
    total_chunks: int,
    chunk: dict[str, Any],
    cid: str,
    elapsed: float,
    total_elapsed: float,
    manifest: dict[str, Any],
    state: dict[str, Any],
) -> None:
    """Print a visible per-chunk progress block."""
    pct = (chunk_index / total_chunks * 100) if total_chunks > 0 else 0
    remaining = total_chunks - chunk_index
    fp = chunk.get("folderPath", "?")
    dn = chunk.get("displayName", "?")
    since = chunk.get("since", "?")
    until = chunk.get("until", "?")

    # Count current chunk stats from manifest diff
    seen = manifest.get("recordsSeen", 0)
    exported = manifest.get("recordsExported", 0)
    changed = manifest.get("recordsChanged", 0)
    dups = manifest.get("recordsSkippedDuplicate", 0)
    nonmail = manifest.get("nonMailItemsSkipped", 0)
    atts_seen = manifest.get("attachmentsSeen", 0)
    atts_cap = manifest.get("attachmentMetadataCaptured", 0)
    ext_seen = manifest.get("extractsSeen", 0)
    ext_parsed = manifest.get("extractsParsed", 0)
    ext_meta = manifest.get("extractsMetadataOnly", 0)
    ext_failed = manifest.get("extractsFailed", 0)

    # State summary counts
    state_pending = state.get("chunksPending", 0)
    state_complete = state.get("chunksComplete", 0)
    state_partial = state.get("chunksPartial", 0)
    state_failed = state.get("chunksFailed", 0)

    print()
    print("=" * 70)
    print(f"  Chunk {chunk_index}/{total_chunks} ({pct:.1f}%) — {remaining} remaining")
    print(f"  Folder: {dn}  Path: {fp}")
    print(f"  Date range: {since}  to  {until}")
    print(f"  Chunk ID: {cid[:16]}...")
    print(f"  Elapsed: {elapsed:.1f}s chunk  |  {total_elapsed:.1f}s total")
    print("-" * 70)
    print(f"  Records seen: {seen}  |  Exported: {exported}  |  Changed: {changed}")
    print(f"  Duplicates skipped: {dups}  |  Non-mail skipped: {nonmail}")
    print(f"  Attachments seen: {atts_seen}  |  Metadata captured: {atts_cap}")
    print(f"  Extracts seen: {ext_seen}  |  Parsed: {ext_parsed}  |  Metadata: {ext_meta}  |  Failed: {ext_failed}")
    print("-" * 70)
    print(f"  State summary — Pending: {state_pending}  Complete: {state_complete}  Partial: {state_partial}  Failed: {state_failed}")
    print("=" * 70)


# ── Dense chunk helpers ───────────────────────────────────────────────


def _get_restricted_count(
    folder: dict[str, Any],
    chunk: dict[str, Any],
    outlook_ctx: dict[str, Any] | None,
) -> int:
    """Quick pre-check: how many items would Restrict return for this chunk?

    Returns -1 if count cannot be determined (fixture, no Outlook, etc.).
    """
    from export_engine.outlook_com_source import (
        outlook_available, _win32com, normalise_outlook_folder_path,
        resolve_com_folder_by_path, build_folder_index,
    )
    if not outlook_available() or outlook_ctx is None:
        return -1
    try:
        root = outlook_ctx["root"]
        fp = chunk.get("folderPath", "")
        canonical = normalise_outlook_folder_path(fp)
        canonical = normalise_outlook_folder_path(canonical)
        target = resolve_com_folder_by_path(root, canonical)
        if target is None:
            return 0
        all_items = target.Items
        since = chunk.get("since", "")
        until = chunk.get("until", "")
        if since and until:
            from datetime import timedelta
            since_dt = _parse_date(since)
            until_dt = _parse_date(until) + timedelta(days=1)
            since_str = since_dt.strftime("%m/%d/%Y %H:%M %p")
            until_str = until_dt.strftime("%m/%d/%Y %H:%M %p")
            role = chunk.get("defaultRole", "custom")
            date_field = "SentOn" if role in ("sent",) else "ReceivedTime"
            filter_str = f"[{date_field}] >= '{since_str}' AND [{date_field}] < '{until_str}'"
            restricted = all_items.Restrict(filter_str)
            return restricted.Count
        return all_items.Count
    except Exception:
        return -1


def _get_split_subchunks(
    chunk: dict[str, Any],
    count: int,
    max_items: int,
    min_days: int = 1,
) -> list[dict[str, Any]]:
    """Split a dense chunk into smaller sub-chunks by dividing the date range.

    Each sub-chunk gets its own chunkId (derived from the parent + date window).
    Returns a list of sub-chunk dicts (same shape as plan chunks).
    """
    since_str = chunk.get("since", "")
    until_str = chunk.get("until", "")
    if not since_str or not until_str:
        return [dict(chunk)]  # Can't split without date range

    sd = _parse_date(since_str)
    ud = _parse_date(until_str)
    total_days = (ud - sd).days
    if total_days <= min_days:
        return [dict(chunk)]  # Already at minimum window

    # How many sub-chunks needed?
    n_chunks = max(1, (count // max_items) + (1 if count % max_items else 0))
    # Ensure we don't create more sub-chunks than days
    n_chunks = min(n_chunks, total_days)
    days_per_chunk = max(min_days, total_days // n_chunks)

    subchunks: list[dict[str, Any]] = []
    from datetime import timedelta
    cursor = sd
    while cursor < ud:
        sub_until = min(cursor + timedelta(days=days_per_chunk), ud)
        sub = dict(chunk)
        sub["since"] = cursor.strftime("%Y-%m-%d")
        sub["until"] = sub_until.strftime("%Y-%m-%d") if sub_until < ud else until_str
        sub["chunkId"] = stable_json_hash({
            "parentChunkId": chunk.get("chunkId", ""),
            "since": sub["since"],
            "until": sub["until"],
        })
        sub["_is_split_subchunk"] = True
        sub["_parentChunkId"] = chunk.get("chunkId", "")
        subchunks.append(sub)
        cursor = sub_until

    return subchunks


def _print_item_progress(
    item_index: int,
    total_items: int,
    sub_chunk_label: str,
    exported: int,
    duplicates: int,
    attachments: int,
    elapsed: float,
) -> None:
    """Print item-level progress within a dense chunk."""
    pct = (item_index / total_items * 100) if total_items else 0
    print(f"  [{sub_chunk_label}] item {item_index}/{total_items} ({pct:.1f}%) — "
          f"{elapsed:.1f}s — exported:{exported} dup:{duplicates} att:{attachments}")


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
    parse_extracts: bool = False,
    reparse_duplicate_attachments: bool = False,
    attachment_timeout_seconds: int = 30,
    max_items_per_chunk: int = 500,
    min_chunk_days: int = 1,
    item_progress_every: int = 25,
) -> dict[str, Any]:
    """Run a limited canonical record ingest.

    Returns the ingest run manifest.
    Per-chunk checkpointing: state is saved atomically after every chunk.
    Outlook COM context: opened once per command, reused across chunks.
    Progress: per-chunk status block printed to stdout.
    Dense chunks (>max_items_per_chunk) are split into sub-chunks dynamically.
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
        # Read from BACKFILL STATE's chunk status, not the plan's static status
        state_chunks = state.get("chunks", {})
        chunks_to_process = []
        for c in plan["chunks"]:
            sc = state_chunks.get(c["chunkId"], {})
            status = sc.get("status", "pending")
            if status == "pending":
                chunks_to_process.append(c)
        # Also include runtime sub-chunks (from dense splitting) that are pending
        for scid, sc in state_chunks.items():
            if sc.get("parentChunkId") and sc.get("status") == "pending":
                # Build a minimal chunk dict from state info
                parent_id = sc.get("parentChunkId", "")
                parent_chunk = next((c for c in plan["chunks"] if c["chunkId"] == parent_id), None)
                if parent_chunk:
                    sub_chunk = dict(parent_chunk)
                    sub_chunk["chunkId"] = scid
                    sub_chunk["since"] = sc.get("since", parent_chunk.get("since", ""))
                    sub_chunk["until"] = sc.get("until", parent_chunk.get("until", ""))
                    sub_chunk["_is_split_subchunk"] = True
                    sub_chunk["_parentChunkId"] = parent_id
                    chunks_to_process.append(sub_chunk)
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

    # Open Outlook context ONCE (reused across all chunks in this command)
    outlook_ctx = None
    if not use_fixture:
        outlook_ctx = open_outlook_context(store_display_name=store_display_name)

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
    total_start = time.time()

    # ── Expand dense chunks into sub-chunks ───────────────────────────
    expanded_chunks: list[dict[str, Any]] = []
    for c in chunks_to_process:
        if use_fixture or outlook_ctx is None:
            expanded_chunks.append(c)
            continue
        fk = c.get("folderKey", "")
        folder = plan_folders_by_key.get(fk, {})
        count = _get_restricted_count(folder, c, outlook_ctx)
        if count > max_items_per_chunk:
            print(f"  [dense] {c.get('displayName', '?')} {c.get('since', '?')}..{c.get('until', '?')} "
                  f"has {count} items — splitting into sub-chunks...")
            subs = _get_split_subchunks(c, count, max_items_per_chunk, min_chunk_days)
            cid = c["chunkId"]
            if cid in state.get("chunks", {}):
                child_ids = [s["chunkId"] for s in subs]
                state["chunks"][cid]["childChunkIds"] = child_ids
                state["chunks"][cid]["status"] = "splitting"
            # Register sub-chunks in state
            for s in subs:
                scid = s["chunkId"]
                if scid not in state.get("chunks", {}):
                    state.setdefault("chunks", {})[scid] = {
                        "parentChunkId": cid,
                        "status": "pending",
                        "since": s.get("since", ""),
                        "until": s.get("until", ""),
                        "attempts": 0,
                        "lastError": "",
                    }
                expanded_chunks.append(s)
        else:
            expanded_chunks.append(c)

    # Respect max_chunks (applied to expanded count)
    if max_chunks and len(expanded_chunks) > max_chunks:
        expanded_chunks = expanded_chunks[:max_chunks]

    total_chunks = len(expanded_chunks)

    for chunk_index, chunk in enumerate(expanded_chunks, 1):
        if total_limit and exported_count >= total_limit:
            break

        chunk_start = time.time()
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
            records = _enumerate_outlook_items(
                folder, chunk,
                store_display_name, store_id_hash, export_run_id,
                outlook_ctx=outlook_ctx,
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
        chunk_extracts_seen = 0
        chunk_extracts_parsed = 0
        chunk_extracts_metadata = 0
        chunk_extracts_failed = 0
        chunk_temp_deleted = 0
        non_mail_skipped = False

        for rec_idx, rec in enumerate(records, 1):
            manifest["recordsSeen"] += 1

            # Item-level progress for dense chunks
            if not dry_run and item_progress_every and rec_idx % item_progress_every == 0:
                item_elapsed = time.time() - chunk_start
                _print_item_progress(
                    rec_idx, len(records),
                    f"{dn} {chunk_since[:7]}",
                    chunk_records_exported, chunk_records_duplicate,
                    chunk_attachments_seen, item_elapsed,
                )

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

            # Attachment parsing
            if parse_extracts and not dry_run and action in ("exported", "changed") and att_count > 0:
                for att_item in atts.get("items", []):
                    if use_fixture:
                        from .hashing import make_extract_key
                        ek = make_extract_key(rk, att_item.get("originalName", "unknown"))
                        extract = {
                            "_schema": "export.knowledgeExtract.v1",
                            "recordType": "outlookAttachmentExtract",
                            "parentRecordKey": rk,
                            "exportRunId": export_run_id,
                            "extractKey": ek,
                            "source": {
                                "originalName": att_item.get("originalName", ""),
                                "originalNameHash": att_item.get("originalNameHash", ""),
                                "extension": att_item.get("extension", ""),
                                "sizeBytes": att_item.get("sizeBytes", 0),
                                "contentHash": att_item.get("contentHash", ""),
                            },
                            "parse": {"status": "metadata_only", "parser": "fixture",
                                      "parsedAt": datetime.now(timezone.utc).isoformat(),
                                      "failureReason": "fixture_synthetic", "needsReview": False},
                            "content": {"text": "", "textHash": "", "tables": [], "sheets": [], "metadata": {}},
                            "retrieval": {"chunkIds": []},
                            "vault": {"notePaths": [], "canvasPaths": []},
                            "audit": {"rawSourceRetained": False, "tempFileDeleted": True, "parseWarnings": []},
                        }
                        sent = rec.get("headers", {}).get("sentDateTime", "")
                        ey, em = (sent[:4], sent[5:7]) if len(sent) >= 7 else ("unknown", "unknown")
                        extract_dir = os.path.join(resolved_root, "extracts", ey, em)
                        os.makedirs(extract_dir, exist_ok=True)
                        extract_path = os.path.join(extract_dir, f"record_{rk}_extract_1_{ek}.json")
                        with open(extract_path, "w", encoding="utf-8") as f:
                            json.dump(extract, f, indent=2, ensure_ascii=False)

                        chunk_extracts_seen += 1
                        chunk_extracts_metadata += 1
                        chunk_temp_deleted += 1

                        # Update parent record with extract reference
                        rec["attachments"]["parseDeferred"] = False
                        rec_ref = {"extractKey": ek, "extractPath": extract_path,
                                   "status": "metadata_only", "needsReview": False}
                        existing_keys = {x.get("extractKey") for x in rec.get("extracts", [])}
                        if ek not in existing_keys:
                            rec["extracts"].append(rec_ref)
                        sent = rec.get("headers", {}).get("sentDateTime", "")
                        ry, rm = (sent[:4], sent[5:7]) if len(sent) >= 7 else ("unknown", "unknown")
                        rec_path_updated = os.path.join(resolved_root, "records", ry, rm, f"record_{rk}.json")
                        with open(rec_path_updated, "w", encoding="utf-8") as f:
                            json.dump(rec, f, indent=2, ensure_ascii=False)
                    else:
                        try:
                            from .parsers import parse_attachment
                            pass
                        except Exception:
                            pass

        manifest["attachmentsSeen"] += chunk_attachments_seen
        manifest["attachmentMetadataCaptured"] += chunk_attachments_captured
        manifest["extractsSeen"] += chunk_extracts_seen
        manifest["extractsMetadataOnly"] += chunk_extracts_metadata
        manifest["extractsParsed"] += chunk_extracts_parsed
        manifest["extractsFailed"] += chunk_extracts_failed
        manifest["tempFilesDeleted"] += chunk_temp_deleted

        # Update chunk state in backfill state
        chunk_exhausted = chunk_records_seen >= chunk.get("estimatedItems", 0) or not records
        hit_limit = total_limit and exported_count >= total_limit
        item_count_exported = chunk_records_exported + chunk_records_changed
        all_duplicates = (item_count_exported == 0 and chunk_records_seen > 0)

        if dry_run:
            new_status = "pending"
        elif chunk_records_seen == 0 and not records:
            new_status = "complete"  # Empty folder-month, nothing to do
        elif hit_limit and not chunk_exhausted:
            new_status = "partial"
            manifest["chunksPartial"] += 1
        elif chunk_exhausted:
            if all_duplicates and chunk_records_seen > 0:
                new_status = "duplicate_only"
            else:
                new_status = "complete"
                manifest["chunksCompleted"] += 1
        else:
            new_status = "partial"
            manifest["chunksPartial"] += 1

        # Record per-chunk metadata in the state
        chunk_errors = chunk.get("chunk_errors", [])
        chunk_warnings = chunk.get("chunk_warnings", [])
        if chunk_errors:
            new_status = "failed"

        # Update chunk in state with detailed per-attempt metadata
        if cid in state.get("chunks", {}):
            state["chunks"][cid]["status"] = new_status
            state["chunks"][cid]["attempts"] = state["chunks"][cid].get("attempts", 0) + 1
            if new_status == "complete":
                state["chunks"][cid]["completedAt"] = datetime.now(timezone.utc).isoformat()
            state["chunks"][cid]["lastAttemptAt"] = datetime.now(timezone.utc).isoformat()
            state["chunks"][cid]["lastAttemptSeen"] = chunk_records_seen
            state["chunks"][cid]["lastAttemptExported"] = chunk_records_exported
            state["chunks"][cid]["lastAttemptChanged"] = chunk_records_changed
            state["chunks"][cid]["lastAttemptDuplicates"] = chunk_records_duplicate
            state["chunks"][cid]["lastAttemptAttachments"] = chunk_attachments_seen
            state["chunks"][cid]["lastAttemptExtracts"] = chunk_extracts_seen

            if chunk_errors:
                state["chunks"][cid]["lastError"] = "; ".join(chunk_errors)
            if chunk_warnings:
                state["chunks"][cid]["lastWarnings"] = chunk_warnings

        # Recompute summary counts and save state after EVERY chunk
        _recompute_state_counts(state)
        if not dry_run:
            _save_state_atomic(resolved_root, state)

        # Print per-chunk progress
        chunk_elapsed = time.time() - chunk_start
        total_elapsed = time.time() - total_start
        _print_chunk_progress(
            chunk_index, total_chunks, chunk, cid,
            chunk_elapsed, total_elapsed, manifest, state,
        )

        if chunk_errors:
            manifest["errors"].extend(chunk_errors)
        if chunk_warnings:
            manifest["warnings"].extend(chunk_warnings)

        if hit_limit:
            break

    # Finalize manifest
    manifest["finishedAt"] = datetime.now(timezone.utc).isoformat()

    # Final state recompute and save (belt-and-suspenders — already saved per-chunk)
    _recompute_state_counts(state)
    if not dry_run:
        _save_state_atomic(resolved_root, state)

    # Write run manifest
    runs_dir = os.path.join(resolved_root, "runs")
    os.makedirs(runs_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    manifest_path = os.path.join(runs_dir, f"ingest_run_{ts}.json")
    _write_json(manifest_path, manifest)

    latest_path = os.path.join(runs_dir, "ingest_run_latest.json")
    _write_json(latest_path, manifest)

    return manifest
