"""Read-only Outlook COM source adapter for the current user's primary store.

Resolves the primary Outlook store from the default Inbox folder,
recursively scans folders under that one store, and excludes all
other stores by default.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from .config import EXCLUDED_FOLDER_ROLES, EXCLUDED_FOLDER_NAMES
from .hashing import make_folder_key, make_store_id_hash


# ── Lazy win32com import ───────────────────────────────────────────────

_OUTLOOK_AVAILABLE = False
_win32com = None

try:
    import win32com.client as _win32com  # type: ignore[import-untyped]
    _OUTLOOK_AVAILABLE = True
except ImportError:
    pass


def outlook_available() -> bool:
    """Return True if win32com / Outlook COM is importable."""
    return _OUTLOOK_AVAILABLE


# ── Folder path normalisation ──────────────────────────────────────────


def normalise_outlook_folder_path(
    path: str,
    store_display_name: str | None = None,
) -> str:
    """Normalise an Outlook folder path to canonical root-relative form.

    Canonical form: starts with \\, no trailing \\, no store display name prefix.
    """
    if not path:
        return "\\"

    # Normalise all slashes to backslash
    norm = path.replace("/", "\\")

    # Collapse multiple backslashes FIRST
    while "\\\\" in norm:
        norm = norm.replace("\\\\", "\\")

    # Strip store display name prefix (case-insensitive)
    if store_display_name:
        prefix = store_display_name.replace("/", "\\")
        # Try matching with leading backslash
        pfx = f"\\{prefix}"
        if norm.lower().startswith(pfx.lower()):
            norm = norm[len(pfx):]
        # Try matching without leading backslash
        elif norm.lower().startswith(prefix.lower()):
            norm = norm[len(prefix):]

    # Strip trailing backslash
    norm = norm.rstrip("\\")

    # Ensure leading backslash
    if not norm.startswith("\\"):
        norm = "\\" + norm

    return norm


def folder_path_to_parts(path: str) -> list[str]:
    """Split a canonical folder path into parts, skipping the leading \\."""
    p = normalise_outlook_folder_path(path)
    return [part for part in p.split("\\") if part]


# ── Role inference ─────────────────────────────────────────────────────


def _infer_default_role(display_name: str, folder_path: str) -> str:
    """Map a folder's display name/path to a default role."""
    name_lower = display_name.lower().strip()
    path_lower = normalise_outlook_folder_path(folder_path).lower()

    if name_lower == "inbox" or path_lower == "\\inbox":
        return "inbox"
    if name_lower in ("sent items", "sent") or "\\sent items" in path_lower:
        return "sent"
    if name_lower in ("deleted items", "deleted") or "\\deleted items" in path_lower:
        return "deleted"
    if name_lower in ("junk email", "junk", "spam") or "\\junk email" in path_lower:
        return "junk"
    if name_lower == "drafts" or "\\drafts" in path_lower:
        return "drafts"
    if name_lower == "outbox" or "\\outbox" in path_lower:
        return "outbox"
    if name_lower == "sync issues" or "\\sync issues" in path_lower:
        return "sync_issues"
    if name_lower in ("rss feeds", "rss") or "\\rss feeds" in path_lower:
        return "rss"
    if name_lower == "conversation history" or "\\conversation history" in path_lower:
        return "conversation_history"
    if name_lower == "calendar" or "\\calendar" in path_lower:
        return "calendar"
    if name_lower == "contacts" or "\\contacts" in path_lower:
        return "contacts"
    if name_lower == "tasks" or "\\tasks" in path_lower:
        return "tasks"
    if name_lower == "notes" or "\\notes" in path_lower:
        return "notes"
    if name_lower in ("search folders", "search") or "\\search folders" in path_lower:
        return "search"

    return "custom"


def _is_folder_excluded(
    role: str,
    display_name: str,
    *,
    include_deleted: bool = False,
    include_junk: bool = False,
    include_drafts: bool = False,
) -> tuple[bool, str]:
    """Check if a folder should be excluded by default.

    Returns (is_excluded, reason).
    """
    if role in EXCLUDED_FOLDER_ROLES:
        if role == "deleted" and include_deleted:
            return False, ""
        if role == "junk" and include_junk:
            return False, ""
        if role == "drafts" and include_drafts:
            return False, ""
        return True, f"excluded_by_default_role_{role}"

    # Name-based fallback for unknown roles
    if display_name.lower().strip() in EXCLUDED_FOLDER_NAMES:
        return True, f"excluded_by_default_name_{display_name.lower().replace(' ', '_')}"

    return False, ""


# ── Folder enumeration ─────────────────────────────────────────────────


def _enumerate_folders(
    com_folder: Any,
    parent_path: str = "",
    *,
    include_deleted: bool = False,
    include_junk: bool = False,
    include_drafts: bool = False,
) -> list[dict[str, Any]]:
    """Recursively enumerate Outlook folders under *com_folder*.

    Returns a list of folder entry dicts with root-relative canonical paths.
    """
    results: list[dict[str, Any]] = []
    try:
        name = str(com_folder.Name)
    except Exception:
        name = "Unknown"

    # Build path: root folder gets "\\<name>", children get "\\parent\\child"
    display_path = f"{parent_path}\\{name}" if parent_path else f"\\{name}"

    role = _infer_default_role(name, display_path)
    excluded, reason = _is_folder_excluded(
        role, name,
        include_deleted=include_deleted,
        include_junk=include_junk,
        include_drafts=include_drafts,
    )

    item_count = 0
    if not excluded:
        try:
            item_count = int(com_folder.Items.Count)
        except Exception:
            item_count = 0

    entry = {
        "folderKey": make_folder_key(display_path),
        "folderPath": display_path,
        "displayName": name,
        "defaultRole": role,
        "itemCount": item_count,
        "included": not excluded,
        "excludedReason": reason,
    }
    results.append(entry)

    # Recurse into subfolders
    try:
        subfolders = com_folder.Folders
        for sub in subfolders:
            try:
                results.extend(
                    _enumerate_folders(
                        sub,
                        parent_path=display_path,
                        include_deleted=include_deleted,
                        include_junk=include_junk,
                        include_drafts=include_drafts,
                    )
                )
            except Exception:
                pass
    except Exception:
        pass

    return results


# ── Folder index for ingest ────────────────────────────────────────────


def build_folder_index(
    root_folder: Any,
    *,
    store_display_name: str | None = None,
    include_deleted: bool = False,
    include_junk: bool = False,
    include_drafts: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build a folder index from a COM root folder.

    Returns (index_by_canonical_path, folder_entries).
    Index keys are lower-cased canonical paths for case-insensitive lookup.
    Paths are stripped of the store display name prefix if provided.
    """
    entries = _enumerate_folders(
        root_folder,
        include_deleted=include_deleted,
        include_junk=include_junk,
        include_drafts=include_drafts,
    )
    idx: dict[str, Any] = {}
    for e in entries:
        canonical = normalise_outlook_folder_path(e["folderPath"], store_display_name=store_display_name)
        idx[canonical.casefold()] = e
    return idx, entries


def resolve_com_folder_by_path(root_folder: Any, canonical_path: str) -> Any | None:
    """Walk the COM folder tree to find a folder by canonical path."""
    parts = folder_path_to_parts(canonical_path)
    target = root_folder
    for part in parts:
        found = False
        try:
            for sub in target.Folders:
                try:
                    if str(sub.Name).lower() == part.lower():
                        target = sub
                        found = True
                        break
                except Exception:
                    continue
        except Exception:
            return None
        if not found:
            return None
    return target


# ── List non-primary stores ────────────────────────────────────────────


def _list_excluded_stores(namespace: Any, primary_store_id: str) -> list[dict[str, Any]]:
    """List all stores in the namespace that are NOT the primary store."""
    excluded: list[dict[str, Any]] = []
    try:
        stores = namespace.Stores
        for store in stores:
            try:
                sid = str(store.StoreID) if hasattr(store, "StoreID") else ""
                name = str(store.DisplayName) if hasattr(store, "DisplayName") else ""
                if sid and sid == primary_store_id:
                    continue
                excluded.append({
                    "displayName": name,
                    "storeIdHash": make_store_id_hash(sid or name),
                    "reason": "additional_store_excluded_by_default",
                })
            except Exception:
                pass
    except Exception:
        pass
    return excluded


# ── Main scan ──────────────────────────────────────────────────────────


def scan_primary_store(
    store_root: str,
    *,
    include_deleted: bool = False,
    include_junk: bool = False,
    include_drafts: bool = False,
) -> dict[str, Any]:
    """Run a live Outlook COM source scan against the current user's primary store.

    Returns the source catalog dict with canonical root-relative folder paths.
    """
    if not _OUTLOOK_AVAILABLE:
        raise RuntimeError(
            "Outlook COM unavailable. Install/use on Windows with Outlook configured, "
            "or run fixture source tests."
        )

    outlook = _win32com.Dispatch("Outlook.Application")  # type: ignore[union-attr]
    namespace = outlook.GetNamespace("MAPI")

    # Step 1: get the current user's default Inbox
    inbox = namespace.GetDefaultFolder(6)  # olFolderInbox = 6
    store = inbox.Store
    store_name = str(store.DisplayName) if store else "Unknown"
    store_id = str(store.StoreID) if store else ""

    # Step 2: get root folder and build index
    root_folder = store.GetRootFolder()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Strip the root folder's name from paths to make them root-relative
    root_name = str(root_folder.Name) if root_folder else ""
    # Rebuild index with stripped paths
    idx, all_entries = build_folder_index(
        root_folder,
        store_display_name=root_name,
        include_deleted=include_deleted,
        include_junk=include_junk,
        include_drafts=include_drafts,
    )
    folder_entries = []
    for e in all_entries:
        stripped = normalise_outlook_folder_path(e["folderPath"], store_display_name=root_name)
        # Skip the root folder itself (it's a container, not a mail folder)
        if stripped == "\\":
            continue
        e["folderPath"] = stripped
        e["folderKey"] = make_folder_key(stripped)
        folder_entries.append(e)

    included_count = sum(1 for f in folder_entries if f["included"])
    excluded_count = sum(1 for f in folder_entries if not f["included"])

    # Step 3: list excluded stores (metadata only)
    excluded_stores = _list_excluded_stores(namespace, store_id)

    # Build catalog
    catalog: dict[str, Any] = {
        "_schema": "export.sourceCatalog.v1",
        "sourceAdapter": "OutlookComPrimaryStoreSource",
        "scope": "primary_user_store_only",
        "storeDisplayName": store_name,
        "storeIdHash": make_store_id_hash(store_id or store_name),
        "scannedAt": now_iso,
        "folders": folder_entries,
        "excludedStores": excluded_stores,
        "audit": {
            "mailboxWrite": False,
            "kanbanWrite": False,
            "cloudApiCalls": False,
            "rawSourceRetained": False,
        },
        "warnings": [],
        "errors": [],
    }

    # Write catalog + run manifest
    catalog_dir = os.path.join(store_root, "catalog")
    runs_dir = os.path.join(store_root, "runs")
    os.makedirs(catalog_dir, exist_ok=True)
    os.makedirs(runs_dir, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    catalog_path = os.path.join(catalog_dir, "source_catalog_latest.json")
    run_path = os.path.join(runs_dir, f"source_scan_{ts}.json")

    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    run_manifest: dict[str, Any] = {
        "_schema": "export.sourceScanRun.v1",
        "sourceAdapter": "OutlookComPrimaryStoreSource",
        "scope": "primary_user_store_only",
        "startedAt": now_iso,
        "finishedAt": now_iso,
        "storeDisplayName": store_name,
        "storeIdHash": make_store_id_hash(store_id or store_name),
        "foldersSeen": len(folder_entries),
        "foldersIncluded": included_count,
        "foldersExcluded": excluded_count,
        "excludedStoresSeen": len(excluded_stores),
        "mailboxWrites": 0,
        "kanbanWrites": 0,
        "cloudApiCalls": 0,
        "rawMessagesStored": 0,
        "rawSourcesRetained": 0,
        "catalogPath": catalog_path,
        "warnings": [],
        "errors": [],
    }

    with open(run_path, "w", encoding="utf-8") as f:
        json.dump(run_manifest, f, indent=2, ensure_ascii=False)

    return catalog
