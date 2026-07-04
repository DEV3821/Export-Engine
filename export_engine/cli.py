"""CLI entry point for the Local Knowledge Store Export Engine."""

from __future__ import annotations

import argparse
import os
import sys

from .config import (
    MAILBOX_WRITE_DISABLED,
    KANBAN_WRITE_DISABLED,
    CLOUD_API_CALLS_DISABLED,
    RAW_SOURCE_RETENTION_DISABLED,
    OUTLOOK_SCOPE,
    NEAR_LIVE_MODE,
    DEFAULT_POLLING_INTERVAL,
    MINIMUM_POLLING_INTERVAL,
)
from .paths import get_store_root, ensure_store_layout, ensure_vault_layout
from .verify import run_verification, format_verification


# ── Banned phrases that must not appear in output ──────────────────────
# (Checked in tests only — do not inline into status output.)


def cmd_store_status(args: argparse.Namespace) -> int:
    """Print neutral store status."""
    store_root = get_store_root()
    store_root = os.path.abspath(store_root)

    lines = [
        "Local Knowledge Store",
        "",
        f"Source adapter: Outlook COM",
        f"Scope: {OUTLOOK_SCOPE}",
        f"Persistent format: hashed JSON records",
        f"Retrieval folder: {os.path.join(store_root, 'retrieval')}",
        f"Local index: {os.path.join(store_root, 'state', 'recall_index.sqlite')}",
        f"Markdown vault: {os.path.join(store_root, 'vault')}",
        f"Vault projection: enabled",
        f"Canvas projection: enabled",
        f"Canvas folder: {os.path.join(store_root, 'vault', '05_Canvases')}",
        f"Mailbox write: {'disabled' if MAILBOX_WRITE_DISABLED else 'enabled'}",
        f"Kanban write: {'disabled' if KANBAN_WRITE_DISABLED else 'enabled'}",
        f"Cloud/API calls: {'disabled' if CLOUD_API_CALLS_DISABLED else 'enabled'}",
        f"Raw source retention: {'disabled' if RAW_SOURCE_RETENTION_DISABLED else 'enabled'}",
        f"NTFS protection: enabled/disabled/unknown",
        f"Near-live mode: {NEAR_LIVE_MODE}",
        f"Default polling interval: {DEFAULT_POLLING_INTERVAL} minutes",
        f"Minimum polling interval: {MINIMUM_POLLING_INTERVAL} minute",
    ]
    print("\n".join(lines))
    return 0


def cmd_store_verify(args: argparse.Namespace) -> int:
    """Run store verification."""
    store_root = get_store_root()
    repo_path = os.path.abspath(".") if args.check_repo else None
    result = run_verification(store_root=store_root, repo_path=repo_path)
    print(format_verification(result))
    return 0 if result.all_ok else 1


def cmd_store_source_scan(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.1."""
    print("store-source-scan: not implemented in Phase 1.1")
    return 0


def cmd_store_plan_ingest(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.1."""
    print("store-plan-ingest: not implemented in Phase 1.1")
    return 0


def cmd_store_ingest(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.1."""
    print("store-ingest: not implemented in Phase 1.1")
    return 0


def cmd_store_refresh(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.1."""
    print("store-refresh: not implemented in Phase 1.1")
    return 0


def cmd_store_watch(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.1."""
    print("store-watch: not implemented in Phase 1.1")
    return 0


def cmd_store_search(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.1."""
    print("store-search: not implemented in Phase 1.1")
    return 0


def cmd_store_rebuild_index(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.1."""
    print("store-rebuild-index: not implemented in Phase 1.1")
    return 0


def cmd_store_build_vault(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.1."""
    print("store-build-vault: not implemented in Phase 1.1")
    return 0


def cmd_store_refresh_vault(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.1."""
    print("store-refresh-vault: not implemented in Phase 1.1")
    return 0


def cmd_store_build_canvas(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.1."""
    print("store-build-canvas: not implemented in Phase 1.1")
    return 0


def cmd_store_refresh_canvas(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.1."""
    print("store-refresh-canvas: not implemented in Phase 1.1")
    return 0


def cmd_store_protect(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.1."""
    print("store-protect: not implemented in Phase 1.1")
    return 0


def cmd_store_verify_protection(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.1."""
    print("store-verify-protection: not implemented in Phase 1.1")
    return 0


# ── Argument parser ────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="export-engine",
        description="Local Knowledge Store Export Engine — Phase 1",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # store-status
    p = sub.add_parser("store-status", help="Show current store configuration")
    p.set_defaults(func=cmd_store_status)

    # store-verify
    p = sub.add_parser("store-verify", help="Verify store safety and layout")
    p.add_argument(
        "--check-repo",
        action="store_true",
        default=True,
        help="Check that the store path is not inside the repo (default: on)",
    )
    p.set_defaults(func=cmd_store_verify)

    # Stub commands
    for cmd_name in [
        "store-source-scan",
        "store-plan-ingest",
        "store-ingest",
        "store-refresh",
        "store-watch",
        "store-search",
        "store-rebuild-index",
        "store-build-vault",
        "store-refresh-vault",
        "store-build-canvas",
        "store-refresh-canvas",
        "store-protect",
        "store-verify-protection",
    ]:
        p = sub.add_parser(cmd_name, help=f"Run {cmd_name}")
        p.set_defaults(func=_stub_for(cmd_name))

    return parser


def _stub_for(cmd_name: str):
    def stub(args: argparse.Namespace) -> int:
        print(f"{cmd_name}: not implemented in Phase 1.1")
        return 0

    return stub


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
