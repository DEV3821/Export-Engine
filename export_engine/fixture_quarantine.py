"""Fixture data quarantine — scans KnowledgeStore for test/fixture records and
moves them to a quarantine area so they don't appear in vault notes, search
results, or recall queries.

Fixture data includes records with:
- "Fixture message" or "synthetic fixture" in subject
- "\\Inbox\\SubTeam" folder paths
- Source email addresses from example.com
- Other test-only markers
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from typing import Any

from .paths import get_store_root


def quarantine_fixtures(
    store_root: str | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Scan KnowledgeStore for fixture-like records and quarantine them.

    Quarantined records are moved to:
        %LOCALAPPDATA%\\SAMI\\KnowledgeStore\\quarantine\\fixtures_<timestamp>\\

    Returns a manifest of what was found and quarantined.
    """
    resolved = get_store_root(store_root)
    now_iso = datetime.now(timezone.utc).isoformat()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    result: dict[str, Any] = {
        "scannedAt": now_iso,
        "storeRoot": resolved,
        "dryRun": dry_run,
        "recordsScanned": 0,
        "fixtureRecordsFound": 0,
        "fixtureRecordsQuarantined": 0,
        "fixtureRecordKeys": [],
        "quarantinePath": "",
        "error": None,
    }

    # Scan records directory for fixture markers
    records_dir = os.path.join(resolved, "records")
    fixture_records: list[tuple[str, str]] = []  # (filepath, recordKey)

    if not os.path.isdir(records_dir):
        result["error"] = "Records directory not found: " + records_dir
        return result

    for root, dirs, files in os.walk(records_dir):
        for fn in files:
            if not fn.endswith(".json"):
                continue
            fp = os.path.join(root, fn)
            result["recordsScanned"] += 1
            try:
                with open(fp, encoding="utf-8") as f:
                    rec = json.load(f)
            except Exception:
                continue

            if _is_fixture_record(rec):
                rk = rec.get("recordKey", "")
                fixture_records.append((fp, rk))
                result["fixtureRecordsFound"] += 1
                if rk:
                    result["fixtureRecordKeys"].append(rk)

    if dry_run or result["fixtureRecordsFound"] == 0:
        return result

    # Create quarantine directory
    quarantine_dir = os.path.join(resolved, "quarantine", "fixtures_" + ts)
    os.makedirs(quarantine_dir, exist_ok=True)
    result["quarantinePath"] = quarantine_dir

    # Move fixture records to quarantine
    for fp, rk in fixture_records:
        rel_path = os.path.relpath(fp, resolved)
        dest = os.path.join(quarantine_dir, rel_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            shutil.move(fp, dest)
            result["fixtureRecordsQuarantined"] += 1
        except OSError as e:
            pass

    # Write quarantine manifest
    manifest = {
        "schema": "export.fixtureQuarantineManifest.v1",
        "quarantinedAt": now_iso,
        "storeRoot": resolved,
        "quarantinePath": quarantine_dir,
        "recordsScanned": result["recordsScanned"],
        "fixtureRecordsFound": result["fixtureRecordsFound"],
        "fixtureRecordsQuarantined": result["fixtureRecordsQuarantined"],
        "fixtureRecordKeys": result["fixtureRecordKeys"][:500],
    }
    manifest_path = os.path.join(quarantine_dir, "fixture_quarantine_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return result


def _is_fixture_record(rec: dict) -> bool:
    """Check if a record appears to be fixture/test data."""
    subj = (
        rec.get("headers", {}).get("subject", "")
        or rec.get("subject", "")
        or ""
    )
    folder_path = (
        rec.get("source", {}).get("folderPath", "")
        or rec.get("folderPath", "")
        or ""
    )
    email_from = (
        rec.get("headers", {}).get("from", {}).get("emailAddress", "")
        or ""
    )

    subj_lower = subj.lower()
    folder_lower = folder_path.lower()

    # Fixture subject markers
    for marker in ["fixture message", "synthetic fixture"]:
        if marker in subj_lower:
            return True

    # Test-only folder paths
    if "\\inbox\\subteam" in folder_lower:
        return True

    # example.com email addresses (fixture artifact)
    if "example.com" in email_from.lower():
        return True

    # Store display name as prefix in folder path (fixture artifact)
    if folder_path and "\\" in folder_path:
        parts = folder_path.split("\\")
        first_part = parts[0] if parts else ""
        if "@" in first_part and not first_part.startswith("\\"):
            return True

    return False


def scan_for_fixtures(
    store_root: str | None = None,
) -> dict[str, Any]:
    """Scan-only: find fixture records without quarantining them."""
    return quarantine_fixtures(store_root=store_root, dry_run=True)
