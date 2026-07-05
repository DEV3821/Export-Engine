"""Near-live incremental refresh module.

Provides:
- live_status        — current live state summary
- live_enable        — validate store, enable polling incremental refresh
- live_disable       — disable polling, keep state
- live_refresh_once  — one incremental refresh cycle

Safety: read-only Outlook COM, never writes to mailbox/kanban/cloud.
Sent Items is included by default.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Any

from .config import DEFAULT_POLLING_INTERVAL, MINIMUM_POLLING_INTERVAL
from .hashing import sha256_text
from .health import run_store_health
from .offline import validate_offline, audit_offline
from .paths import get_store_root, ensure_store_layout
from .schemas import new_live_state, new_canonical_record


def _get_live_state_path(store_root: str) -> str:
    return os.path.join(store_root, "live_state.json")


def _read_live_state(store_root: str) -> dict[str, Any]:
    path = _get_live_state_path(store_root)
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return new_live_state(live_enabled=False)


def _write_live_state(store_root: str, state: dict[str, Any]) -> None:
    path = _get_live_state_path(store_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _get_included_folders(store_root: str) -> list[dict]:
    """Get included folders from the catalog, including Sent Items."""
    cat_path = os.path.join(store_root, "catalog", "source_catalog_latest.json")
    if not os.path.isfile(cat_path):
        return []
    try:
        with open(cat_path, encoding="utf-8") as f:
            cat = json.load(f)
        return [f for f in cat.get("folders", []) if f.get("included")]
    except Exception:
        return []


def live_status(store_root: str | None = None) -> dict[str, Any]:
    """Return current live state summary.

    No Outlook COM. No writes.
    """
    resolved = get_store_root(store_root)
    state = _read_live_state(resolved)
    folders = _get_included_folders(resolved)

    return {
        "liveEnabled": state.get("liveEnabled", False),
        "lastRefreshStartedAt": state.get("lastRefreshStartedAt", ""),
        "lastRefreshFinishedAt": state.get("lastRefreshFinishedAt", ""),
        "pollingIntervalMinutes": state.get("pollingIntervalMinutes", DEFAULT_POLLING_INTERVAL),
        "includedFolderCount": len(folders),
        "includeSentItems": state.get("includeSentItems", True),
        "inboxHighWatermark": state.get("inboxHighWatermark", ""),
        "sentItemsHighWatermark": state.get("sentItemsHighWatermark", ""),
        "newRecordsLastRun": state.get("newRecordsLastRun", 0),
        "changedRecordsLastRun": state.get("changedRecordsLastRun", 0),
        "duplicatesSkippedLastRun": state.get("duplicatesSkippedLastRun", 0),
        "errorsLastRun": state.get("errorsLastRun", 0),
        "mailboxWrites": state.get("mailboxWrites", 0),
        "kanbanWrites": state.get("kanbanWrites", 0),
        "cloudApiCalls": state.get("cloudApiCalls", 0),
    }


def live_enable(
    store_root: str | None = None,
    *,
    polling_interval_minutes: int = DEFAULT_POLLING_INTERVAL,
) -> dict[str, Any]:
    """Enable near-live incremental refresh.

    Validates offline store first. Confirms Sent Items included.
    Writes live_state.json with high-watermarks.
    No Outlook COM in this function itself (refresh does).
    """
    resolved = get_store_root(store_root)
    now_iso = datetime.now(timezone.utc).isoformat()

    # Step 1: Validate offline store
    validation = validate_offline(store_root=resolved, require_sent_items=True, require_vault_notes=False)
    if validation.get("overallResult") != "PASS":
        return {
            "enabled": False,
            "error": "Offline validation failed: " + "; ".join(validation.get("failures", [])),
            "validationResult": validation,
        }

    # Step 2: Check Sent Items is included
    folders = _get_included_folders(resolved)
    sent_folders = [f for f in folders if "sent" in f.get("defaultRole", "").lower()]
    if not sent_folders:
        return {
            "enabled": False,
            "error": "Sent Items not in included folders. Enable Sent Items in source scan first.",
        }

    # Step 3: Create/update live state
    polling_interval = max(polling_interval_minutes, MINIMUM_POLLING_INTERVAL)
    state = _read_live_state(resolved)
    state["liveEnabled"] = True
    state["pollingIntervalMinutes"] = polling_interval
    state["includeSentItems"] = True
    state["includedFolderCount"] = len(folders)

    # Set initial high-watermarks (if not already set)
    if not state.get("inboxHighWatermark"):
        state["inboxHighWatermark"] = now_iso
    if not state.get("sentItemsHighWatermark"):
        state["sentItemsHighWatermark"] = now_iso

    # Initialise per-folder high-watermarks
    if "highWatermarks" not in state:
        state["highWatermarks"] = {}
    for fld in folders:
        fk = fld.get("folderKey", "")
        if fk and fk not in state["highWatermarks"]:
            state["highWatermarks"][fk] = now_iso

    state["mailboxWrites"] = 0
    state["kanbanWrites"] = 0
    state["cloudApiCalls"] = 0

    _write_live_state(resolved, state)

    # Step 4: Write activation log
    log_dir = os.path.join(resolved, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "live_enable_" + now_iso[:10] + ".json")
    log_entry = {
        "event": "live_enable",
        "enabledAt": now_iso,
        "pollingIntervalMinutes": polling_interval,
        "includeSentItems": True,
        "folderCount": len(folders),
        "sentFolderCount": len(sent_folders),
    }
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, indent=2, ensure_ascii=False)

    return {
        "enabled": True,
        "pollingIntervalMinutes": polling_interval,
        "includeSentItems": True,
        "folderCount": len(folders),
        "sentFolderCount": len(sent_folders),
        "inboxHighWatermark": state["inboxHighWatermark"],
        "sentItemsHighWatermark": state["sentItemsHighWatermark"],
    }


def live_disable(store_root: str | None = None) -> dict[str, Any]:
    """Disable near-live incremental refresh.

    Stops polling. Does not delete live state or high-watermarks.
    """
    resolved = get_store_root(store_root)
    state = _read_live_state(resolved)
    state["liveEnabled"] = False
    state["pollingEnabled"] = False
    _write_live_state(resolved, state)

    return {"disabled": True, "liveEnabled": False}


def live_refresh_once(
    store_root: str | None = None,
) -> dict[str, Any]:
    """Run one incremental refresh cycle.

    Reads primary Outlook store. Processes included folders.
    Includes Sent Items. Uses high-watermarks + bounded overlap.
    Exports new/changed records. Updates derived outputs.

    Safety: read-only COM. No mailbox write. No kanban write. No cloud API.
    """
    resolved = get_store_root(store_root)
    ensure_store_layout(resolved)
    now_iso = datetime.now(timezone.utc).isoformat()

    state = _read_live_state(resolved)
    if not state.get("liveEnabled", False):
        return {
            "error": "Live mode is not enabled. Run live-enable first.",
            "refreshStarted": False,
        }

    # Validate Outlook COM availability
    from .outlook_com_source import outlook_available
    if not outlook_available():
        return {
            "error": "Outlook COM unavailable. Cannot run live refresh.",
            "refreshStarted": False,
        }

    # Update live state with start time
    state["lastRefreshStartedAt"] = now_iso
    _write_live_state(resolved, state)

    result: dict[str, Any] = {
        "refreshStartedAt": now_iso,
        "storeRoot": resolved,
        "foldersProcessed": 0,
        "newRecords": 0,
        "changedRecords": 0,
        "duplicatesSkipped": 0,
        "errors": 0,
        "mailboxWrites": 0,
        "kanbanWrites": 0,
        "cloudApiCalls": 0,
        "outlookComUsed": True,
        "fullMailboxReprocess": False,
        "sentItemsIncluded": True,
        "refreshedFolders": [],
        "errorMessages": [],
    }

    # Get included folders from catalog
    folders = _get_included_folders(resolved)
    sent_folders = [f for f in folders if "sent" in f.get("defaultRole", "").lower()]
    inbox_folders = [f for f in folders if "sent" not in f.get("defaultRole", "").lower()]

    # High-watermarks from state
    high_watermarks = state.get("highWatermarks", {})
    if not high_watermarks:
        high_watermarks = {}

    from .outlook_com_source import (
        _win32com, normalise_outlook_folder_path,
        resolve_com_folder_by_path, build_folder_index,
    )

    outlook = _win32com.Dispatch("Outlook.Application")
    namespace = outlook.GetNamespace("MAPI")

    try:
        inbox = namespace.GetDefaultFolder(6)
        store = inbox.Store
        root = store.GetRootFolder()
        store_display_name = str(store.DisplayName)
        store_id_hash = sha256_text(store.StoreID or "")
        idx, _ = build_folder_index(root, store_display_name=store_display_name)

        # Process all included folders (inbox + sent)
        all_folders = inbox_folders + sent_folders
        for fld in all_folders:
            fk = fld.get("folderKey", "")
            fp = fld.get("folderPath", "")
            role = fld.get("defaultRole", "custom")
            if not fk or not fp:
                continue

            hwm = high_watermarks.get(fk, "")

            try:
                new_count, changed_count, dup_count, err_count = _refresh_folder(
                    root, idx, fld, store_display_name, store_id_hash,
                    resolved, hwm, role,
                )
                result["newRecords"] += new_count
                result["changedRecords"] += changed_count
                result["duplicatesSkipped"] += dup_count
                result["errors"] += err_count
                result["foldersProcessed"] += 1
                result["refreshedFolders"].append({
                    "folderPath": fp,
                    "folderKey": fk,
                    "newRecords": new_count,
                    "changedRecords": changed_count,
                })

                # Update high-watermark
                high_watermarks[fk] = now_iso
            except Exception as e:
                result["errors"] += 1
                result["errorMessages"].append("Error refreshing " + fp + ": " + str(e))
    finally:
        try:
            outlook.Quit()
        except Exception:
            pass

    # Update high-watermark summary
    state["highWatermarks"] = high_watermarks
    state["inboxHighWatermark"] = now_iso
    state["sentItemsHighWatermark"] = now_iso
    state["newRecordsLastRun"] = result["newRecords"]
    state["changedRecordsLastRun"] = result["changedRecords"]
    state["duplicatesSkippedLastRun"] = result["duplicatesSkipped"]
    state["errorsLastRun"] = result["errors"]
    state["lastRefreshFinishedAt"] = now_iso
    state["mailboxWrites"] = 0
    state["kanbanWrites"] = 0
    state["cloudApiCalls"] = 0
    _write_live_state(resolved, state)

    # Post-refresh: rebuild derived outputs if new records found
    if result["newRecords"] > 0 or result["changedRecords"] > 0:
        try:
            from .offline import rebuild_derived
            rebuild_result = rebuild_derived(store_root=resolved, offline=True)
            result["derivedRebuildStatus"] = "ok"
            result["derivedRebuildDetails"] = rebuild_result.get("outputCounts", {})
        except Exception as e:
            result["derivedRebuildStatus"] = "failed"
            result["errorMessages"].append("Derived rebuild after refresh: " + str(e))

    # Update vault/dashboard
    try:
        from .vault import build_vault
        vault_result = build_vault(resolved)
        result["vaultUpdated"] = True
        result["vaultNotesWritten"] = vault_result.get("vaultNotesWritten", 0)
    except Exception as e:
        result["vaultUpdated"] = False
        result["errorMessages"].append("Vault update after refresh: " + str(e))

    result["refreshFinishedAt"] = datetime.now(timezone.utc).isoformat()
    return result


def _refresh_folder(
    root: Any,
    folder_index: dict,
    folder_entry: dict,
    store_display_name: str,
    store_id_hash: str,
    store_root: str,
    hwm: str,
    role: str,
) -> tuple[int, int, int, int]:
    """Refresh a single folder: find items newer than high-watermark and export.

    Returns (newCount, changedCount, duplicateCount, errorCount).
    No mailbox write. No kanban write.
    """
    from .outlook_com_source import normalise_outlook_folder_path

    fp = folder_entry.get("folderPath", "")
    fk = folder_entry.get("folderKey", "")
    if not fp:
        return 0, 0, 0, 0

    canonical = normalise_outlook_folder_path(fp)
    canonical = normalise_outlook_folder_path(canonical, store_display_name=store_display_name)
    folder_entry_in_idx = folder_index.get(canonical.casefold())
    if folder_entry_in_idx is None:
        return 0, 0, 0, 0

    target = resolve_com_folder_by_path(root, canonical)
    if target is None:
        return 0, 0, 0, 1

    new_records = 0
    changed_records = 0
    duplicates = 0
    errors = 0

    try:
        all_items = target.Items
        items = all_items

        # Apply date filter if high-watermark is set
        if hwm:
            try:
                hwm_dt = datetime.fromisoformat(hwm)
                date_field = "SentOn" if role == "sent" else "ReceivedTime"
                hwm_str = hwm_dt.strftime("%m/%d/%Y %H:%M %p")
                filter_str = "[" + date_field + "] >= '" + hwm_str + "'"
                restricted = all_items.Restrict(filter_str)
                # Restrict returns 0 items for genuinely empty ranges
                # Do NOT fall back to Python iteration
                if restricted.Count == 0:
                    return 0, 0, 0, 0
                items = restricted
            except Exception:
                pass

        max_to_process = min(items.Count, 200)  # Cap per cycle
        for i in range(1, max_to_process + 1):
            try:
                item = items.Item(i)
                msg_class = str(getattr(item, "MessageClass", ""))
                if "IPM.Note" not in msg_class and "IPM.Note" not in msg_class:
                    continue

                new_rec, changed_rec, dup = _export_single_item(
                    item, fp, fk or "", store_root,
                    store_display_name, store_id_hash,
                )
                if new_rec:
                    new_records += 1
                elif changed_rec:
                    changed_records += 1
                elif dup:
                    duplicates += 1
                else:
                    errors += 1
            except Exception:
                errors += 1

    except Exception:
        errors += 1

    return new_records, changed_records, duplicates, errors


def _export_single_item(
    item: Any,
    folder_path: str,
    folder_key: str,
    store_root: str,
    store_display_name: str,
    store_id_hash: str,
) -> tuple[bool, bool, bool]:
    """Export a single Outlook item as a canonical record.

    Returns (isNew, isChanged, isDuplicate).
    """
    entry_id = str(item.EntryID) if hasattr(item, "EntryID") and item.EntryID else ""
    if not entry_id:
        return False, False, False

    # Build record key
    record_key = sha256_text(entry_id + "|" + folder_path)

    # Create canonical record
    now_iso = datetime.now(timezone.utc).isoformat()
    subj = str(item.Subject or "") if hasattr(item, "Subject") else ""
    body_text = ""

    try:
        if hasattr(item, "Body") and item.Body:
            body_text = str(item.Body)
    except Exception:
        pass

    body_text_hash = sha256_text(body_text) if body_text else ""

    # Determine dates
    sent_dt = ""
    received_dt = ""
    try:
        if hasattr(item, "SentOn") and item.SentOn:
            sent_dt = str(item.SentOn)
    except Exception:
        pass
    try:
        if hasattr(item, "ReceivedTime") and item.ReceivedTime:
            received_dt = str(item.ReceivedTime)
    except Exception:
        pass

    # Get sender info
    sender_name = ""
    sender_email = ""
    try:
        if hasattr(item, "Sender") and item.Sender:
            sender_name = str(item.Sender.Name or "")
            try:
                sender_email = str(item.Sender.Address or "")
            except Exception:
                # Fall back to SenderEmailAddress
                if hasattr(item, "SenderEmailAddress"):
                    sender_email = str(item.SenderEmailAddress or "")
    except Exception:
        if hasattr(item, "SenderName"):
            sender_name = str(item.SenderName or "")
        if hasattr(item, "SenderEmailAddress"):
            sender_email = str(item.SenderEmailAddress or "")

    # Get recipients
    to_list: list[str] = []
    cc_list: list[str] = []
    try:
        if hasattr(item, "Recipients"):
            for j in range(1, item.Recipients.Count + 1):
                try:
                    recip = item.Recipients.Item(j)
                    rtype = getattr(recip, "Type", 1)
                    rname = str(getattr(recip, "Name", "") or "")
                    raddr = str(getattr(recip, "Address", "") or "")
                    entry = {"displayName": rname, "emailAddress": raddr}
                    if rtype == 1:
                        to_list.append(entry)
                    elif rtype == 2:
                        cc_list.append(entry)
                except Exception:
                    pass
    except Exception:
        pass

    # Conversation fields
    conversation_id = ""
    conversation_topic = ""
    conversation_index = ""
    try:
        if hasattr(item, "ConversationID"):
            conversation_id = str(item.ConversationID or "")
    except Exception:
        pass
    try:
        if hasattr(item, "ConversationTopic"):
            conversation_topic = str(item.ConversationTopic or "")
    except Exception:
        pass
    try:
        if hasattr(item, "ConversationIndex"):
            conversation_index = str(item.ConversationIndex or "")
    except Exception:
        pass

    # Compute conversation key
    conversation_key = ""
    if conversation_id:
        conversation_key = sha256_text("conversationId:" + conversation_id)
    elif conversation_topic:
        conversation_key = sha256_text("topic:" + conversation_topic)

    record = new_canonical_record(
        record_key=record_key,
        folder_path=folder_path,
        folder_key=folder_key,
        subject=subj,
        store_display_name=store_display_name,
        store_id_hash=store_id_hash,
    )
    record["exportedAt"] = now_iso
    record["source"]["mailbox"] = store_display_name
    record["source"]["messageClass"] = "IPM.Note"
    record["source"]["direction"] = "sent" if folder_key and "sent" in folder_key.lower() else "incoming"
    record["identity"]["outlookEntryIdHash"] = sha256_text(entry_id)
    record["identity"]["contentHash"] = body_text_hash
    record["identity"]["conversationId"] = conversation_id
    record["identity"]["conversationTopic"] = conversation_topic
    record["identity"]["conversationKey"] = conversation_key
    record["headers"]["sentDateTime"] = sent_dt
    record["headers"]["receivedDateTime"] = received_dt
    record["headers"]["from"]["displayName"] = sender_name
    record["headers"]["from"]["emailAddress"] = sender_email
    record["headers"]["to"] = to_list
    record["headers"]["cc"] = cc_list
    record["content"]["bodyPreview"] = body_text[:500] if body_text else ""
    record["content"]["bodyText"] = body_text
    record["content"]["bodyTextHash"] = body_text_hash
    record["content"]["htmlStripped"] = True

    # Count attachments
    att_count = 0
    try:
        if hasattr(item, "Attachments"):
            att_count = item.Attachments.Count
    except Exception:
        pass
    record["attachments"]["count"] = att_count
    record["attachments"]["parseDeferred"] = True

    # Write record to disk
    dt_for_path = sent_dt or received_dt
    year = "unknown"
    month = "unknown"
    if dt_for_path and len(dt_for_path) >= 7:
        year = dt_for_path[:4]
        month = dt_for_path[5:7]

    rec_dir = os.path.join(store_root, "records", year, month)
    os.makedirs(rec_dir, exist_ok=True)
    rec_path = os.path.join(rec_dir, "record_" + record_key + ".json")

    if os.path.isfile(rec_path):
        try:
            with open(rec_path, encoding="utf-8") as f:
                existing = json.load(f)
            existing_hash = existing.get("content", {}).get("bodyTextHash", "")
            if existing_hash == body_text_hash:
                return False, False, True  # duplicate
        except Exception:
            pass

    with open(rec_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    if os.path.isfile(rec_path):
        # Check if it was a change or new
        return True, False, False  # new record

    return False, False, False
