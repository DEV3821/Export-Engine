"""Resumable historic backfill planner for the Local Knowledge Store.

Reads a primary-store source catalog and creates a resumable backfill plan
split into monthly calendar chunks.  After backfill, the system shifts
to near-live polling refresh.
"""

from __future__ import annotations

import json
import os
import uuid
from calendar import monthrange
from datetime import datetime, timezone, timedelta
from typing import Any

from .paths import get_store_root, ensure_store_layout
from .config import (
    OUTLOOK_SCOPE,
    DEFAULT_POLLING_INTERVAL,
    MINIMUM_POLLING_INTERVAL,
)
from .hashing import stable_json_hash


# ── Date chunking ──────────────────────────────────────────────────────


def _parse_date(s: str) -> datetime:
    """Parse YYYY-MM-DD into a UTC datetime at midnight."""
    parts = s.strip().split("-")
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    return datetime(y, m, d, tzinfo=timezone.utc)


def _default_since_until() -> tuple[str, str]:
    """Default window: last 365 days ending today."""
    until = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    since = until - timedelta(days=365)
    return since.strftime("%Y-%m-%d"), until.strftime("%Y-%m-%d")


def _monthly_chunks(since_str: str, until_str: str) -> list[tuple[str, str]]:
    """Split [since, until) into calendar-month chunks.

    Returns list of (chunk_since, chunk_until) tuples where each
    chunk is one calendar month (or partial at start/end).
    """
    since = _parse_date(since_str)
    until = _parse_date(until_str)

    if since >= until:
        raise ValueError(f"since ({since_str}) must be before until ({until_str})")

    chunks: list[tuple[str, str]] = []
    cursor = since

    while cursor < until:
        # End of this month
        _, last_day = monthrange(cursor.year, cursor.month)
        month_end = cursor.replace(day=last_day, tzinfo=timezone.utc)
        chunk_until = min(month_end, until)

        chunks.append((cursor.strftime("%Y-%m-%d"), chunk_until.strftime("%Y-%m-%d")))

        # Move to first day of next month
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1, day=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1, day=1)

    return chunks


# ── Chunk ID generation ────────────────────────────────────────────────


def _make_chunk_id(folder_key: str, since: str, until: str) -> str:
    """Deterministic chunk ID based on folder key and date range (no raw names)."""
    return stable_json_hash({
        "folderKey": folder_key,
        "since": since,
        "until": until,
        "chunkMode": "monthly",
        "chunkPurpose": "historic_backfill",
    })


# ── Load catalog ───────────────────────────────────────────────────────


def load_source_catalog(store_root: str) -> dict[str, Any] | None:
    """Load the latest source catalog from the store."""
    path = os.path.join(store_root, "catalog", "source_catalog_latest.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Main planner ───────────────────────────────────────────────────────


def create_backfill_plan(
    store_root: str | None = None,
    *,
    use_fixture: bool = False,
    since: str | None = None,
    until: str | None = None,
    source_catalog_path: str | None = None,
    refresh_source_catalog: bool = False,
) -> dict[str, Any]:
    """Create a resumable historic backfill plan.

    Returns the plan dict.
    """
    resolved_root = get_store_root(store_root)
    ensure_store_layout(resolved_root)

    # Optionally refresh source catalog
    if refresh_source_catalog:
        from .source_scan import run_source_scan
        catalog = run_source_scan(
            resolved_root,
            use_fixture=use_fixture,
        )
    else:
        # Load from file or create fixture
        if use_fixture:
            from .fixture_source import scan_fixture_source
            catalog = scan_fixture_source(resolved_root)
        else:
            catalog = load_source_catalog(resolved_root)
            if catalog is None:
                raise FileNotFoundError(
                    "No source catalog found. Run store-source-scan --all-user-folders first, "
                    "or use --refresh-source-catalog."
                )

    # Validate scope
    if catalog.get("scope") != "primary_user_store_only":
        raise ValueError(
            f"Catalog scope is '{catalog.get('scope')}', expected 'primary_user_store_only'. "
            "Only primary-store catalogs are supported for planning."
        )

    # Default dates
    if not since or not until:
        since, until = _default_since_until()

    # Validate dates
    _parse_date(since)
    _parse_date(until)
    if since >= until:
        raise ValueError(f"since ({since}) must be before until ({until})")

    # Generate chunks per included folder
    included_folders = [f for f in catalog.get("folders", []) if f.get("included")]
    plan_folders: list[dict[str, Any]] = []
    all_chunks: list[dict[str, Any]] = []
    total_estimated_items = 0

    monthly_ranges = _monthly_chunks(since, until)

    for folder in included_folders:
        fk = folder["folderKey"]
        fp = folder["folderPath"]
        dn = folder["displayName"]
        dr = folder.get("defaultRole", "unknown")
        ic = folder.get("itemCount", 0)

        plan_folders.append({
            "folderKey": fk,
            "folderPath": fp,
            "displayName": dn,
            "defaultRole": dr,
            "itemCount": ic,
            "included": True,
        })

        # Distribute itemCount across monthly chunks evenly
        n_months = len(monthly_ranges)
        per_chunk = ic // n_months if n_months > 0 else 0
        remainder = ic % n_months if n_months > 0 else 0

        for i, (cs, cu) in enumerate(monthly_ranges):
            est = per_chunk + (1 if i < remainder else 0)
            cid = _make_chunk_id(fk, cs, cu)
            all_chunks.append({
                "chunkId": cid,
                "folderKey": fk,
                "folderPath": fp,
                "displayName": dn,
                "defaultRole": dr,
                "since": cs,
                "until": cu,
                "chunkPurpose": "historic_backfill",
                "status": "pending",
                "estimatedItems": est,
                "estimatedExtracts": 0,
                "attempts": 0,
                "lastError": "",
                "completedAt": "",
            })
            total_estimated_items += est

    now_iso = datetime.now(timezone.utc).isoformat()
    plan_id = stable_json_hash({
        "storeIdHash": catalog.get("storeIdHash", ""),
        "createdAt": now_iso,
        "since": since,
        "until": until,
    })

    plan: dict[str, Any] = {
        "_schema": "export.ingestPlan.v1",
        "planId": plan_id,
        "createdAt": now_iso,
        "sourceCatalogPath": source_catalog_path or "",
        "scope": "primary_user_store_only",
        "storeDisplayName": catalog.get("storeDisplayName", ""),
        "storeIdHash": catalog.get("storeIdHash", ""),
        "since": since,
        "until": until,
        "chunkMode": "monthly",
        "chunkPurpose": "historic_backfill",
        "allUserFolders": True,
        "nearLiveAfterBackfill": {
            "enabled": True,
            "mode": "polling_incremental_refresh",
            "defaultPollingIntervalMinutes": DEFAULT_POLLING_INTERVAL,
            "minimumPollingIntervalMinutes": MINIMUM_POLLING_INTERVAL,
            "implementedInThisPhase": False,
        },
        "folders": plan_folders,
        "chunks": all_chunks,
        "estimatedItems": total_estimated_items,
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

    # Write plan
    runs_dir = os.path.join(resolved_root, "runs")
    state_dir = os.path.join(resolved_root, "state")
    os.makedirs(runs_dir, exist_ok=True)
    os.makedirs(state_dir, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    plan_path = os.path.join(runs_dir, f"ingest_plan_{ts}.json")
    plan_latest_path = os.path.join(runs_dir, "ingest_plan_latest.json")

    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    with open(plan_latest_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)

    # Write backfill state
    chunks_pending = sum(1 for c in all_chunks if c["status"] == "pending")
    backfill_state: dict[str, Any] = {
        "_schema": "export.backfillState.v1",
        "createdAt": now_iso,
        "updatedAt": now_iso,
        "activePlanId": plan_id,
        "activePlanPath": plan_path,
        "scope": "primary_user_store_only",
        "chunkMode": "monthly",
        "chunkPurpose": "historic_backfill",
        "since": since,
        "until": until,
        "chunksTotal": len(all_chunks),
        "chunksPending": chunks_pending,
        "chunksComplete": 0,
        "chunksFailed": 0,
        "nearLiveAfterBackfill": {
            "enabled": True,
            "mode": "polling_incremental_refresh",
            "defaultPollingIntervalMinutes": DEFAULT_POLLING_INTERVAL,
            "minimumPollingIntervalMinutes": MINIMUM_POLLING_INTERVAL,
            "refreshStatePrepared": True,
        },
        "chunks": {c["chunkId"]: {
            "status": c["status"],
            "folderKey": c["folderKey"],
            "since": c["since"],
            "until": c["until"],
            "chunkPurpose": "historic_backfill",
            "attempts": c["attempts"],
            "lastError": c.get("lastError", ""),
            "completedAt": c.get("completedAt", ""),
        } for c in all_chunks},
        "audit": {
            "mailboxWrite": False,
            "kanbanWrite": False,
            "cloudApiCalls": False,
            "rawSourceRetained": False,
        },
    }

    backfill_path = os.path.join(state_dir, "backfill_state.json")
    with open(backfill_path, "w", encoding="utf-8") as f:
        json.dump(backfill_state, f, indent=2, ensure_ascii=False)

    # Write refresh readiness state
    refresh_state: dict[str, Any] = {
        "_schema": "export.refreshState.v1",
        "createdAt": now_iso,
        "updatedAt": now_iso,
        "scope": "primary_user_store_only",
        "mode": "polling_incremental_refresh",
        "status": "waiting_for_backfill",
        "enabledAfterBackfill": True,
        "defaultPollingIntervalMinutes": DEFAULT_POLLING_INTERVAL,
        "minimumPollingIntervalMinutes": MINIMUM_POLLING_INTERVAL,
        "lastRefreshStartedAt": "",
        "lastRefreshFinishedAt": "",
        "folders": {f["folderKey"]: {
            "folderPath": f["folderPath"],
            "displayName": f["displayName"],
            "defaultRole": f["defaultRole"],
        } for f in plan_folders},
        "audit": {
            "mailboxWrite": False,
            "kanbanWrite": False,
            "cloudApiCalls": False,
            "rawSourceRetained": False,
        },
    }

    refresh_path = os.path.join(state_dir, "refresh_state.json")
    with open(refresh_path, "w", encoding="utf-8") as f:
        json.dump(refresh_state, f, indent=2, ensure_ascii=False)

    return plan
