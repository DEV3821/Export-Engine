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
    store_root = get_store_root()
    repo_path = os.path.abspath(".") if args.check_repo else None
    result = run_verification(store_root=store_root, repo_path=repo_path)
    print(format_verification(result))
    return 0 if result.all_ok else 1


def cmd_store_source_scan(args: argparse.Namespace) -> int:
    from .source_scan import run_source_scan
    store_root = get_store_root()
    if not args.fixture and not outlook_available():
        print("Outlook COM unavailable. Install/use on Windows with Outlook configured, or run with --fixture for fixture source tests.")
        return 1
    if args.include_shared_stores or args.include_archive_store:
        print("Warning: multi-store scanning is reserved for a later explicit safety phase. Only the primary user store will be scanned.")
    try:
        catalog = run_source_scan(store_root, use_fixture=args.fixture, include_deleted=args.include_deleted, include_junk=args.include_junk, include_drafts=args.include_drafts)
    except RuntimeError as e:
        print(str(e))
        return 1
    included = sum(1 for f in catalog["folders"] if f["included"])
    excluded = sum(1 for f in catalog["folders"] if not f["included"])
    print(f"Local Knowledge Store source scan")
    print(f"Source adapter: Outlook COM")
    print(f"Scope: {OUTLOOK_SCOPE}")
    print(f"Mailbox write: disabled\nKanban write: disabled\nCloud/API calls: disabled\nRaw source retention: disabled\n")
    print(f"Store: {catalog['storeDisplayName']}")
    print(f"Folders seen: {len(catalog['folders'])}")
    print(f"Folders included: {included}\nFolders excluded: {excluded}")
    print(f"Excluded stores: {len(catalog['excludedStores'])}\n")
    print(f"Catalog: (written to catalog/source_catalog_latest.json)")
    print(f"Run manifest: (written to runs/source_scan_*.json)")
    return 0


def cmd_store_plan_ingest(args: argparse.Namespace) -> int:
    from .planning import create_backfill_plan
    store_root = args.store_root or get_store_root()
    use_fixture = args.fixture
    if not use_fixture and not args.refresh_source_catalog:
        cat_path = os.path.join(store_root, "catalog", "source_catalog_latest.json")
        if not os.path.isfile(cat_path):
            print("No source catalog found. Run store-source-scan --all-user-folders first, or use --refresh-source-catalog.")
            return 1
    try:
        plan = create_backfill_plan(store_root, use_fixture=use_fixture, since=args.since, until=args.until, refresh_source_catalog=args.refresh_source_catalog)
    except (FileNotFoundError, ValueError) as e:
        print(str(e))
        return 1
    n_folders, n_chunks = len(plan["folders"]), len(plan["chunks"])
    print(f"Local Knowledge Store historic backfill plan")
    print(f"Scope: {plan['scope']}")
    print(f"Since: {plan['since']}  Until: {plan['until']}")
    print(f"Backfill chunks: {plan['chunkMode']}  Backfill chunk purpose: {plan['chunkPurpose']}")
    print(f"Folders planned: {n_folders}  Chunks planned: {n_chunks}")
    print(f"Estimated items: {plan['estimatedItems']}  Estimated extracts: {plan['estimatedExtracts']}\n")
    print(f"Near-live refresh after backfill: {plan['nearLiveAfterBackfill']['mode']}")
    print(f"Default polling interval: {plan['nearLiveAfterBackfill']['defaultPollingIntervalMinutes']} minutes")
    print(f"Minimum polling interval: {plan['nearLiveAfterBackfill']['minimumPollingIntervalMinutes']} minute\n")
    print(f"Mailbox write: disabled\nKanban write: disabled\nCloud/API calls: disabled\nRaw source retention: disabled\n")
    print(f"Plan: (written to runs/ingest_plan_*.json)")
    print(f"Backfill state: (written to state/backfill_state.json)")
    print(f"Refresh state: (written to state/refresh_state.json)")
    if use_fixture: print("Fixture mode: enabled")
    return 0


def cmd_store_ingest(args: argparse.Namespace) -> int:
    """Run limited canonical record ingest."""
    from .ingest import run_ingest

    store_root = args.store_root or get_store_root()

    # Future-flag warnings
    future_flags = []
    for f in ("parse_extracts", "build_retrieval", "build_index", "build_vault", "build_canvas"):
        if getattr(args, f.replace("-", "_"), False):
            future_flags.append(f)
    if future_flags:
        print("Warning: Attachment parsing, retrieval, index, vault, and canvas projection are reserved for later phases. Phase 1.4 writes canonical message records only.\n")

    try:
        manifest = run_ingest(
            store_root,
            use_fixture=args.fixture,
            limit=args.limit,
            resume=args.resume,
            dry_run=args.dry_run,
            plan_path=args.plan,
            max_chunks=args.max_chunks,
            chunk_id=args.chunk_id,
        )
    except (FileNotFoundError, ValueError) as e:
        print(str(e))
        return 1

    print(f"Local Knowledge Store record ingest")
    print(f"Scope: {manifest['scope']}")
    print(f"Mode: historic backfill record ingest")
    print(f"Plan: {manifest['planPath']}")
    print(f"Backfill state: {manifest['backfillStatePath']}")
    print(f"Limit: {manifest['limit'] or 'none'}  Resume: {'enabled' if manifest['resume'] else 'disabled'}  Dry run: {'enabled' if manifest['dryRun'] else 'disabled'}\n")
    print(f"Chunks attempted: {manifest['chunksAttempted']}")
    print(f"Chunks completed: {manifest['chunksCompleted']}")
    print(f"Chunks partial: {manifest['chunksPartial']}")
    print(f"Chunks failed: {manifest['chunksFailed']}")
    print(f"Records seen: {manifest['recordsSeen']}")
    print(f"Records exported: {manifest['recordsExported']}")
    print(f"Records changed: {manifest['recordsChanged']}")
    print(f"Records skipped duplicate: {manifest['recordsSkippedDuplicate']}")
    print(f"Attachments seen: {manifest['attachmentsSeen']}")
    print(f"Attachment metadata captured: {manifest['attachmentMetadataCaptured']}\n")
    print("Future phases not run:")
    print(f"Extract parsing: {manifest['extractsParsed']}")
    print(f"Conversation build: {manifest['conversationsWritten']}")
    print(f"Retrieval chunks: {manifest['retrievalChunksWritten']}")
    print(f"SQLite rows: {manifest['sqliteRowsWritten']}")
    print(f"Vault notes: {manifest['vaultNotesUpdated']}")
    print(f"Canvas files: {manifest['canvasFilesUpdated']}\n")
    print(f"Mailbox write: disabled\nKanban write: disabled\nCloud/API calls: disabled")
    print(f"Raw .msg/.eml stored: {manifest['rawMessagesStored']}")
    print(f"Raw attachments saved: {manifest['rawAttachmentsSaved']}")
    print(f"Raw source retention: disabled\n")
    if manifest["recordsSeen"] == 0 and not args.fixture:
        print("Warning: no records were exported. Check folder path resolution and date filters.\n")
    print(f"Run manifest: (written to runs/ingest_run_*.json)")
    if args.fixture: print("Fixture mode: enabled")
    return 0


def cmd_store_refresh(args: argparse.Namespace) -> int:
    print("store-refresh: not implemented in this phase")
    return 0

def cmd_store_watch(args: argparse.Namespace) -> int:
    print("store-watch: not implemented in this phase")
    return 0

def cmd_store_search(args: argparse.Namespace) -> int:
    print("store-search: not implemented in this phase")
    return 0

def cmd_store_rebuild_index(args: argparse.Namespace) -> int:
    print("store-rebuild-index: not implemented in this phase")
    return 0

def cmd_store_build_vault(args: argparse.Namespace) -> int:
    print("store-build-vault: not implemented in this phase")
    return 0

def cmd_store_refresh_vault(args: argparse.Namespace) -> int:
    print("store-refresh-vault: not implemented in this phase")
    return 0

def cmd_store_build_canvas(args: argparse.Namespace) -> int:
    print("store-build-canvas: not implemented in this phase")
    return 0

def cmd_store_refresh_canvas(args: argparse.Namespace) -> int:
    print("store-refresh-canvas: not implemented in this phase")
    return 0

def cmd_store_protect(args: argparse.Namespace) -> int:
    print("store-protect: not implemented in this phase")
    return 0

def cmd_store_verify_protection(args: argparse.Namespace) -> int:
    print("store-verify-protection: not implemented in this phase")
    return 0


# ── Argument parser ────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="export-engine", description="Local Knowledge Store Export Engine — Phase 1")
    sub = parser.add_subparsers(dest="command", required=True)

    # store-status
    p = sub.add_parser("store-status", help="Show current store configuration")
    p.set_defaults(func=cmd_store_status)

    # store-verify
    p = sub.add_parser("store-verify", help="Verify store safety and layout")
    p.add_argument("--check-repo", action="store_true", default=True)
    p.set_defaults(func=cmd_store_verify)

    # store-source-scan
    p = sub.add_parser("store-source-scan", help="Scan primary Outlook store for source folders")
    p.add_argument("--all-user-folders", action="store_true", default=False)
    p.add_argument("--fixture", action="store_true", default=False)
    p.add_argument("--include-deleted", action="store_true", default=False)
    p.add_argument("--include-junk", action="store_true", default=False)
    p.add_argument("--include-drafts", action="store_true", default=False)
    p.add_argument("--include-shared-stores", action="store_true", default=False)
    p.add_argument("--include-archive-store", action="store_true", default=False)
    p.set_defaults(func=cmd_store_source_scan)

    # store-plan-ingest
    p = sub.add_parser("store-plan-ingest", help="Create a resumable historic backfill plan")
    p.add_argument("--all-user-folders", action="store_true", default=False)
    p.add_argument("--since", type=str, default=None)
    p.add_argument("--until", type=str, default=None)
    p.add_argument("--chunk", type=str, default="monthly", choices=["monthly"])
    p.add_argument("--fixture", action="store_true", default=False)
    p.add_argument("--source-catalog", type=str, default=None)
    p.add_argument("--store-root", type=str, default=None)
    p.add_argument("--refresh-source-catalog", action="store_true", default=False)
    p.set_defaults(func=cmd_store_plan_ingest)

    # store-ingest
    p = sub.add_parser("store-ingest", help="Run limited canonical record ingest")
    p.add_argument("--fixture", action="store_true", default=False)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--resume", action="store_true", default=False)
    p.add_argument("--dry-run", action="store_true", default=False, dest="dry_run")
    p.add_argument("--plan", type=str, default=None)
    p.add_argument("--store-root", type=str, default=None)
    p.add_argument("--max-chunks", type=int, default=None)
    p.add_argument("--chunk-id", type=str, default=None)
    p.add_argument("--parse-extracts", action="store_true", default=False)
    p.add_argument("--build-retrieval", action="store_true", default=False)
    p.add_argument("--build-index", action="store_true", default=False)
    p.add_argument("--build-vault", action="store_true", default=False)
    p.add_argument("--build-canvas", action="store_true", default=False)
    p.set_defaults(func=cmd_store_ingest)

    # Stub commands
    for cmd_name in [
        "store-refresh", "store-watch", "store-search",
        "store-rebuild-index", "store-build-vault", "store-refresh-vault",
        "store-build-canvas", "store-refresh-canvas",
        "store-protect", "store-verify-protection",
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
