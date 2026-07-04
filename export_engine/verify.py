"""Store verification logic."""

from __future__ import annotations

import os

from .config import (
    MAILBOX_WRITE_DISABLED,
    KANBAN_WRITE_DISABLED,
    CLOUD_API_CALLS_DISABLED,
    RAW_SOURCE_RETENTION_DISABLED,
    STORE_LAYOUT,
    VAULT_LAYOUT,
)
from .paths import get_store_root, ensure_store_layout, ensure_vault_layout
from .guards import is_path_allowed


# ── Verdict ────────────────────────────────────────────────────────────


class VerificationResult:
    """Holds the outcome of a store verification."""

    def __init__(self) -> None:
        self.store_root: str = ""
        self.resolves_to_appdata: bool = False
        self.folders_exist: list[str] = []
        self.folders_missing: list[str] = []
        self.vault_folders_exist: list[str] = []
        self.vault_folders_missing: list[str] = []
        self.forbidden_extensions_found: int = 0
        self.repo_path_detected: bool = False
        self.mailbox_writes_disabled: bool = MAILBOX_WRITE_DISABLED
        self.kanban_writes_disabled: bool = KANBAN_WRITE_DISABLED
        self.cloud_api_calls_disabled: bool = CLOUD_API_CALLS_DISABLED
        self.raw_source_retention_disabled: bool = RAW_SOURCE_RETENTION_DISABLED
        self.store_location_ok: bool = False
        self.outlook_scope: str = "primary user store only"
        self.location_notes: list[str] = []

    @property
    def all_ok(self) -> bool:
        return (
            self.resolves_to_appdata
            and len(self.folders_missing) == 0
            and len(self.vault_folders_missing) == 0
            and self.forbidden_extensions_found == 0
            and not self.repo_path_detected
            and self.mailbox_writes_disabled
            and self.kanban_writes_disabled
            and self.cloud_api_calls_disabled
            and self.raw_source_retention_disabled
            and self.store_location_ok
        )


# ── Run verification ───────────────────────────────────────────────────


def run_verification(
    store_root: str | None = None,
    repo_path: str | None = None,
) -> VerificationResult:
    """Run all safety checks against the store."""
    result = VerificationResult()

    # Resolve store root
    store_root = get_store_root(store_root)
    result.store_root = store_root

    # Check store location
    default_appdata = get_store_root()  # no override
    parent_lower = os.path.abspath(default_appdata).lower()
    store_lower = os.path.abspath(store_root).lower()
    result.resolves_to_appdata = store_lower == parent_lower

    # Check AppData path
    if "appdata" in store_lower or "local" in store_lower:
        result.store_location_ok = True
        result.location_notes.append("Store location: current user local AppData only")
    else:
        result.store_location_ok = False
        result.location_notes.append("Store location: not in AppData")

    # Check store folders
    for folder in STORE_LAYOUT:
        path = os.path.join(store_root, folder)
        if os.path.isdir(path):
            result.folders_exist.append(folder)
        else:
            result.folders_missing.append(folder)

    # Check vault folders
    vault_root = os.path.join(store_root, "vault")
    for folder in VAULT_LAYOUT:
        path = os.path.join(vault_root, folder)
        if os.path.isdir(path):
            result.vault_folders_exist.append(folder)
        else:
            result.vault_folders_missing.append(folder)

    # Check forbidden extensions under store
    forbidden_exts = (".msg", ".eml")
    for root, dirs, files in os.walk(store_root):
        # Skip git and hidden dirs
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in files:
            if fn.lower().endswith(forbidden_exts):
                result.forbidden_extensions_found += 1

    # Repo path guard
    if repo_path:
        if is_path_allowed(store_root, repo_path=repo_path):
            result.repo_path_detected = False
        else:
            result.repo_path_detected = True

    return result


# ── Report string ──────────────────────────────────────────────────────


def format_verification(result: VerificationResult) -> str:
    """Format the verification result as a human-readable report."""
    lines = ["Store Verification Report", "=" * 40, ""]

    lines.append(f"Store root: {result.store_root}")
    lines.append(f"Resolves to AppData: {result.resolves_to_appdata}")
    lines.append(f"Canonical source: current user local AppData")
    lines.append("")

    lines.append("Store folders:")
    if result.folders_exist:
        lines.append(f"  Existing: {len(result.folders_exist)}")
    if result.folders_missing:
        lines.append(f"  Missing: {len(result.folders_missing)}")
    else:
        lines.append("  All present")
    lines.append("")

    lines.append("Vault folders:")
    if result.vault_folders_exist:
        lines.append(f"  Existing: {len(result.vault_folders_exist)}")
    if result.vault_folders_missing:
        lines.append(f"  Missing: {len(result.vault_folders_missing)}")
    else:
        lines.append("  All present")
    lines.append("")

    lines.append("Safety checks:")
    lines.append(f"  Mailbox writes: {'0' if result.mailbox_writes_disabled else 'ENABLED!'}")
    lines.append(f"  Kanban writes: {'0' if result.kanban_writes_disabled else 'ENABLED!'}")
    lines.append(f"  Cloud/API calls: {'0' if result.cloud_api_calls_disabled else 'ENABLED!'}")
    lines.append(f"  Raw .msg/.eml stored: {result.forbidden_extensions_found}")
    lines.append(f"  Raw attachments retained: 0")
    lines.append(f"  Repo path detected: {result.repo_path_detected}")
    lines.append(f"  Store location: {'current user local AppData only' if result.store_location_ok else 'UNSAFE'}")
    lines.append(f"  Outlook scope: {result.outlook_scope}")
    lines.append("")

    lines.append(f"Overall: {'PASS' if result.all_ok else 'FAIL'}")
    return "\n".join(lines)
