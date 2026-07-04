"""Synthetic source adapter for testing — no Outlook dependency.

The fixture source simulates a primary Outlook store with folders and items
so that future source-scan logic can be tested without live Outlook.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


# ── Fixture data types ─────────────────────────────────────────────────


@dataclass
class FixtureFolder:
    """A synthetic mailbox folder."""

    name: str
    path: str  # e.g. "Inbox/SubTeam"
    folder_type: str  # "inbox", "sent", "custom"
    item_count: int = 0
    is_excluded: bool = False  # True for shared/archive stores


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
        - stores: list of FixtureStore dicts
        - primary_store: the primary store
        - items: sample FixtureItems scoped to primary store
    """
    # ── Primary store ──────────────────────────────────────────────
    inbox = FixtureFolder("Inbox", "Inbox", "inbox", item_count=12)
    sent = FixtureFolder("Sent Items", "Sent Items", "sent", item_count=8)
    subteam = FixtureFolder("SubTeam", "Inbox/SubTeam", "inbox", item_count=3)
    projects = FixtureFolder("Projects", "Inbox/Projects", "custom", item_count=5)

    primary = FixtureStore(
        name="mailbox@example.com",
        store_type="primary",
        folders=[inbox, sent, subteam, projects],
        is_default=True,
    )

    # ── Excluded stores ────────────────────────────────────────────
    shared = FixtureStore(
        name="Shared Team Mailbox",
        store_type="shared",
        folders=[
            FixtureFolder("Inbox", "Inbox", "inbox", item_count=20, is_excluded=True),
        ],
        is_default=False,
    )

    archive = FixtureStore(
        name="Archive",
        store_type="archive",
        folders=[
            FixtureFolder(
                "Archive", "Archive", "custom", item_count=200, is_excluded=True
            ),
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
    return ["shared", "archive"]
