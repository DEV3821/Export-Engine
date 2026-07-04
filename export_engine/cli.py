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
from .paths import get_store_root
from .verify import run_verification, format_verification
from .outlook_com_source import outlook_available


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
    """Run source scan against primary Outlook store (or fixture)."""
    from .source_scan import run_source_scan

    store_root = get_store_root()

    if not args.fixture and not outlook_available():
        print(
            "Outlook COM unavailable. Install/use on Windows with Outlook configured, "
            "or run with --fixture for fixture source tests."
        )
        return 1

    if args.include_shared_stores or args.include_archive_store:
        print(
            "Warning: multi-store scanning is reserved for a later explicit safety phase. "
            "Only the primary user store will be scanned."
        )

    try:
        catalog = run_source_scan(
            store_root,
            use_fixture=args.fixture,
            include_deleted=args.include_deleted,
            include_junk=args.include_junk,
            include_drafts=args.include_drafts,
        )
    except RuntimeError as e:
        print(str(e))
        return 1

    included = sum(1 for f in catalog["folders"] if f["included"])
    excluded = sum(1 for f in catalog["folders"] if not f["included"])

    print(f"Local Knowledge Store source scan")
    print(f"Source adapter: Outlook COM")
    print(f"Scope: {OUTLOOK_SCOPE}")
    print(f"Mailbox write: disabled")
    print(f"Kanban write: disabled")
    print(f"Cloud/API calls: disabled")
    print(f"Raw source retention: disabled")
    print()
    print(f"Store: {catalog['storeDisplayName']}")
    print(f"Folders seen: {len(catalog['folders'])}")
    print(f"Folders included: {included}")
    print(f"Folders excluded: {excluded}")
    print(f"Excluded stores: {len(catalog['excludedStores'])}")
    print()
    print(f"Catalog: (written to catalog/source_catalog_latest.json)")
    print(f"Run manifest: (written to runs/source_scan_*.json)")
    return 0


def cmd_store_plan_ingest(args: argparse.Namespace) -> int:
    """Create a resumable historic backfill plan from the latest source catalog."""
    from .planning import create_backfill_plan

    store_root = args.store_root or get_store_root()
    use_fixture = args.fixture

    # Check source catalog exists (unless fixture or refresh)
    if not use_fixture and not args.refresh_source_catalog:
        cat_path = os.path.join(store_root, "catalog", "source_catalog_latest.json")
        if not os.path.isfile(cat_path):
            print(
                "No source catalog found. Run store-source-scan --all-user-folders first, "
                "or use --refresh-source-catalog."
            )
            return 1

    try:
        plan = create_backfill_plan(
            store_root,
            use_fixture=use_fixture,
            since=args.since,
            until=args.until,
            refresh_source_catalog=args.refresh_source_catalog,
        )
    except (FileNotFoundError, ValueError) as e:
        print(str(e))
        return 1

    n_folders = len(plan["folders"])
    n_chunks = len(plan["chunks"])

    print(f"Local Knowledge Store historic backfill plan")
    print(f"Scope: {plan['scope']}")
    print(f"Source catalog: {plan.get('sourceCatalogPath', '(created by planner)')}")
    print(f"Since: {plan['since']}")
    print(f"Until: {plan['until']}")
    print(f"Backfill chunks: {plan['chunkMode']}")
    print(f"Backfill chunk purpose: {plan['chunkPurpose']}")
    print(f"Folders planned: {n_folders}")
    print(f"Chunks planned: {n_chunks}")
    print(f"Estimated items: {plan['estimatedItems']}")
    print(f"Estimated extracts: {plan['estimatedExtracts']}")
    print()
    print(f"Near-live refresh after backfill: {plan['nearLiveAfterBackfill']['mode']}")
    print(f"Default polling interval: {plan['nearLiveAfterBackfill']['defaultPollingIntervalMinutes']} minutes")
    print(f"Minimum polling interval: {plan['nearLiveAfterBackfill']['minimumPollingIntervalMinutes']} minute")
    print()
    print(f"Mailbox write: disabled")
    print(f"Kanban write: disabled")
    print(f"Cloud/API calls: disabled")
    print(f"Raw source retention: disabled")
    print()
    print(f"Plan: (written to runs/ingest_plan_*.json)")
    print(f"Backfill state: (written to state/backfill_state.json)")
    print(f"Refresh state: (written to state/refresh_state.json)")
    if use_fixture:
        print(f"Fixture mode: enabled")
    return 0


def cmd_store_ingest(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.3."""
    print("store-ingest: not implemented in this phase")
    return 0


def cmd_store_refresh(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.3."""
    print("store-refresh: not implemented in this phase")
    return 0


def cmd_store_watch(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.3."""
    print("store-watch: not implemented in this phase")
    return 0


def cmd_store_search(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.3."""
    print("store-search: not implemented in this phase")
    return 0


def cmd_store_rebuild_index(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.3."""
    print("store-rebuild-index: not implemented in this phase")
    return 0


def cmd_store_build_vault(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.3."""
    print("store-build-vault: not implemented in this phase")
    return 0


def cmd_store_refresh_vault(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.3."""
    print("store-refresh-vault: not implemented in this phase")
    return 0


def cmd_store_build_canvas(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.3."""
    print("store-build-canvas: not implemented in this phase")
    return 0


def cmd_store_refresh_canvas(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.3."""
    print("store-refresh-canvas: not implemented in this phase")
    return 0


def cmd_store_protect(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.3."""
    print("store-protect: not implemented in this phase")
    return 0


def cmd_store_verify_protection(args: argparse.Namespace) -> int:
    """Stub — not implemented in Phase 1.3."""
    print("store-verify-protection: not implemented in this phase")
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

    # store-source-scan
    p = sub.add_parser("store-source-scan", help="Scan primary Outlook store for source folders")
    p.add_argument("--all-user-folders", action="store_true", default=False,
                   help="Scan all user folders (inbox + subfolders)")
    p.add_argument("--fixture", action="store_true", default=False,
                   help="Use fixture source instead of live Outlook (for testing)")
    p.add_argument("--include-deleted", action="store_true", default=False,
                   help="Include Deleted Items folder")
    p.add_argument("--include-junk", action="store_true", default=False,
                   help="Include Junk Email folder")
    p.add_argument("--include-drafts", action="store_true", default=False,
                   help="Include Drafts folder")
    p.add_argument("--include-shared-stores", action="store_true", default=False,
                   help="Include shared mailbox stores (reserved for later)")
    p.add_argument("--include-archive-store", action="store_true", default=False,
                   help="Include archive store (reserved for later)")
    p.set_defaults(func=cmd_store_source_scan)

    # store-plan-ingest
    p = sub.add_parser("store-plan-ingest", help="Create a resumable historic backfill plan")
    p.add_argument("--all-user-folders", action="store_true", default=False,
                   help="Include all user folders (default behaviour)")
    p.add_argument("--since", type=str, default=None,
                   help="Start date YYYY-MM-DD (default: 365 days ago)")
    p.add_argument("--until", type=str, default=None,
                   help="End date YYYY-MM-DD (default: today)")
    p.add_argument("--chunk", type=str, default="monthly", choices=["monthly"],
                   help="Historic backfill chunk mode (default: monthly)")
    p.add_argument("--fixture", action="store_true", default=False,
                   help="Use fixture source catalog (for testing)")
    p.add_argument("--source-catalog", type=str, default=None,
                   help="Path to source catalog (optional)")
    p.add_argument("--store-root", type=str, default=None,
                   help="Override store root path")
    p.add_argument("--refresh-source-catalog", action="store_true", default=False,
                   help="Re-run source scan before planning")
    p.set_defaults(func=cmd_store_plan_ingest)

    # Stub commands
    for cmd_name in [
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
        print(f"{cmd_name}: not implemented in this phase")
        return 0

    return stub


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
