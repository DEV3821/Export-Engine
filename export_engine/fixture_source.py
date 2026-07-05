"""Synthetic source adapter for testing — no Outlook dependency.

The fixture source simulates a primary Outlook store with folders and items
so that future source-scan logic can be tested without live Outlook.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import EXCLUDED_FOLDER_ROLES, EXCLUDED_STORE_TYPES


# ── Fixture data types ─────────────────────────────────────────────────


@dataclass
class FixtureFolder:
    """A synthetic mailbox folder."""

    name: str
    path: str  # e.g. "Inbox/SubTeam"
    folder_type: str  # "inbox", "sent", "deleted", "junk", etc.
    item_count: int = 0
    is_excluded: bool = False  # True for shared/archive stores or excluded-by-default folders


@dataclass
class FixtureItem:
    """A synthetic mail item."""

    subject: str
    sent_at: str
    folder_path: str
    body_preview: str = ""
    is_read: bool = True
    has_attachments: bool = False


@dataclass
class FixtureStore:
    """A synthetic Outlook store (primary, shared, or archive)."""

    name: str
    store_type: str  # "primary", "shared", "archive"
    folders: list[FixtureFolder] = field(default_factory=list)
    is_default: bool = False  # only the primary store is default


# ── Factory ────────────────────────────────────────────────────────────


def build_default_fixtures() -> dict[str, Any]:
    """Build a synthetic environment simulating a user's mailboxes.

    Returns a dict with:
        - stores: dict of FixtureStore dicts keyed by type
        - primary_store: the primary store
        - items: sample FixtureItems scoped to primary store
    """
    # ── Primary store ──────────────────────────────────────────────
    inbox = FixtureFolder("Inbox", "Inbox", "inbox", item_count=12)
    sent = FixtureFolder("Sent Items", "Sent Items", "sent", item_count=8)
    subteam = FixtureFolder("SubTeam", "Inbox/SubTeam", "inbox", item_count=3)
    projects = FixtureFolder("Projects", "Inbox/Projects", "custom", item_count=5)

    # Default-excluded folders under primary store
    deleted = FixtureFolder("Deleted Items", "Deleted Items", "deleted", item_count=0, is_excluded=True)
    junk = FixtureFolder("Junk Email", "Junk Email", "junk", item_count=0, is_excluded=True)
    drafts = FixtureFolder("Drafts", "Drafts", "drafts", item_count=0, is_excluded=True)
    outbox = FixtureFolder("Outbox", "Outbox", "outbox", item_count=0, is_excluded=True)
    sync_issues = FixtureFolder("Sync Issues", "Sync Issues", "sync_issues", item_count=0, is_excluded=True)
    calendar = FixtureFolder("Calendar", "Calendar", "calendar", item_count=0, is_excluded=True)
    contacts = FixtureFolder("Contacts", "Contacts", "contacts", item_count=0, is_excluded=True)

    primary = FixtureStore(
        name="mailbox@example.com",
        store_type="primary",
        folders=[inbox, sent, subteam, projects, deleted, junk, drafts, outbox, sync_issues, calendar, contacts],
        is_default=True,
    )

    # ── Excluded stores ────────────────────────────────────────────
    shared = FixtureStore(
        name="Shared Team Mailbox",
        store_type="shared",
        folders=[
            FixtureFolder("Inbox", "Inbox", "inbox", item_count=20, is_excluded=True),
            FixtureFolder("Sent Items", "Sent Items", "sent", item_count=5, is_excluded=True),
        ],
        is_default=False,
    )

    archive = FixtureStore(
        name="Online Archive",
        store_type="archive",
        folders=[
            FixtureFolder("Inbox", "Inbox", "inbox", item_count=100, is_excluded=True),
            FixtureFolder("Sent Items", "Sent Items", "sent", item_count=50, is_excluded=True),
        ],
        is_default=False,
    )

    # ── Sample items (primary store only) ──────────────────────────
    items = [
        FixtureItem(
            subject="Project update — Q3 planning",
            sent_at="2025-09-15T10:30:00",
            folder_path="Inbox",
            body_preview="Here is the latest on Q3…",
        ),
        FixtureItem(
            subject="Re: Sprint review notes",
            sent_at="2025-09-14T14:00:00",
            folder_path="Inbox",
            body_preview="Thanks for sharing the notes…",
        ),
        FixtureItem(
            subject="Meeting agenda — Architecture review",
            sent_at="2025-09-13T09:15:00",
            folder_path="Inbox/SubTeam",
            body_preview="Topics for today: API design, data model…",
        ),
        FixtureItem(
            subject="Out of office — back next week",
            sent_at="2025-09-10T08:00:00",
            folder_path="Sent Items",
            body_preview="I will be out of the office…",
        ),
    ]

    return {
        "stores": {
            "primary": _store_asdict(primary),
            "shared": _store_asdict(shared),
            "archive": _store_asdict(archive),
        },
        "items": [_item_asdict(it) for it in items],
    }


# ── Fixture-based scan (simulates a live scan for testing) ─────────────


def scan_fixture_source(
    store_root: str,
    *,
    include_deleted: bool = False,
    include_junk: bool = False,
    include_drafts: bool = False,
) -> dict[str, Any]:
    """Run a source scan over fixture data, writing catalog & run manifest.

    Returns the catalog dict.
    """
    fixtures = build_default_fixtures()
    primary: dict = fixtures["stores"]["primary"]
    now_iso = datetime.now(timezone.utc).isoformat()

    from .hashing import make_folder_key, make_store_id_hash

    # Build folder entries
    folder_entries: list[dict[str, Any]] = []
    for f in primary["folders"]:
        role = f["folderType"]
        name_lower = f["name"].lower()

        # Determine inclusion
        if role in EXCLUDED_FOLDER_ROLES:
            if role == "deleted" and include_deleted:
                included = True
                reason = ""
            elif role == "junk" and include_junk:
                included = True
                reason = ""
            elif role == "drafts" and include_drafts:
                included = True
                reason = ""
            else:
                included = False
                reason = f"excluded_by_default_role_{role}"
        else:
            included = True
            reason = ""

        entry = {
            "folderKey": make_folder_key(f["path"]),
            "folderPath": "\\" + f["path"].replace("/", "\\"),
            "displayName": f["name"],
            "defaultRole": role,
            "itemCount": f["itemCount"],
            "included": included,
            "excludedReason": reason,
        }
        folder_entries.append(entry)

    # Build excluded stores
    excluded_entries: list[dict[str, Any]] = []
    for stype, sdata in fixtures["stores"].items():
        if stype == "primary":
            continue
        excluded_entries.append({
            "displayName": sdata["name"],
            "storeIdHash": make_store_id_hash(sdata["name"]),
            "reason": f"additional_store_excluded_by_default",
        })

    included_count = sum(1 for f in folder_entries if f["included"])
    excluded_count = sum(1 for f in folder_entries if not f["included"])

    catalog: dict[str, Any] = {
        "_schema": "export.sourceCatalog.v1",
        "sourceAdapter": "OutlookComPrimaryStoreSource",
        "scope": "primary_user_store_only",
        "storeDisplayName": primary["name"],
        "storeIdHash": make_store_id_hash(primary["name"]),
        "scannedAt": now_iso,
        "folders": folder_entries,
        "excludedStores": excluded_entries,
        "audit": {
            "mailboxWrite": False,
            "kanbanWrite": False,
            "cloudApiCalls": False,
            "rawSourceRetained": False,
        },
        "warnings": [],
        "errors": [],
    }

    run_manifest: dict[str, Any] = {
        "_schema": "export.sourceScanRun.v1",
        "sourceAdapter": "OutlookComPrimaryStoreSource",
        "scope": "primary_user_store_only",
        "startedAt": now_iso,
        "finishedAt": now_iso,
        "storeDisplayName": primary["name"],
        "storeIdHash": make_store_id_hash(primary["name"]),
        "foldersSeen": len(folder_entries),
        "foldersIncluded": included_count,
        "foldersExcluded": excluded_count,
        "excludedStoresSeen": len(excluded_entries),
        "mailboxWrites": 0,
        "kanbanWrites": 0,
        "cloudApiCalls": 0,
        "rawMessagesStored": 0,
        "rawSourcesRetained": 0,
        "catalogPath": "",
        "warnings": [],
        "errors": [],
    }

    # Write catalog
    catalog_dir = os.path.join(store_root, "catalog")
    runs_dir = os.path.join(store_root, "runs")
    os.makedirs(catalog_dir, exist_ok=True)
    os.makedirs(runs_dir, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_path = os.path.join(runs_dir, f"source_scan_{ts}.json")
    catalog_path = os.path.join(catalog_dir, "source_catalog_latest.json")

    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    run_manifest["catalogPath"] = catalog_path
    with open(run_path, "w", encoding="utf-8") as f:
        json.dump(run_manifest, f, indent=2, ensure_ascii=False)

    return catalog


# ── Serialisation helpers ──────────────────────────────────────────────


def _store_asdict(store: FixtureStore) -> dict[str, Any]:
    return {
        "name": store.name,
        "storeType": store.store_type,
        "isDefault": store.is_default,
        "folders": [
            {
                "name": f.name,
                "path": f.path,
                "folderType": f.folder_type,
                "itemCount": f.item_count,
                "isExcluded": f.is_excluded,
            }
            for f in store.folders
        ],
    }


def _item_asdict(item: FixtureItem) -> dict[str, Any]:
    return {
        "subject": item.subject,
        "sentAt": item.sent_at,
        "folderPath": item.folder_path,
        "bodyPreview": item.body_preview,
        "isRead": item.is_read,
        "hasAttachments": item.has_attachments,
    }


def get_excluded_store_types() -> list[str]:
    """Return the store types that should be excluded by default."""
    return list(EXCLUDED_STORE_TYPES)
