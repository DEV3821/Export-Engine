"""CLI entry point for the Engine Exporter — Local Mailbox Export Engine."""

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
    for f in ("build_retrieval", "build_index", "build_vault", "build_canvas"):
        if getattr(args, f.replace("-", "_"), False):
            future_flags.append(f)
    if future_flags:
        print("Warning: Retrieval, index, vault, and canvas projection are reserved for later phases.\n")

    parse_extracts = getattr(args, "parse_extracts", False)
    reparse_dups = getattr(args, "reparse_duplicate_attachments", False)
    att_timeout = getattr(args, "attachment_timeout_seconds", 30)

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
            parse_extracts=parse_extracts,
            reparse_duplicate_attachments=reparse_dups,
            attachment_timeout_seconds=att_timeout,
            max_items_per_chunk=getattr(args, "max_items_per_chunk", 500),
            min_chunk_days=getattr(args, "min_chunk_days", 1),
            item_progress_every=getattr(args, "item_progress_every", 25),
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
    print(f"Extracts:")
    print(f"Extracts seen: {manifest['extractsSeen']}")
    print(f"Extracts parsed: {manifest['extractsParsed']}")
    print(f"Extracts metadata-only: {manifest['extractsMetadataOnly']}")
    print(f"Extracts failed: {manifest['extractsFailed']}")
    print(f"Temp files deleted: {manifest['tempFilesDeleted']}\n")
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


def cmd_store_health(args: argparse.Namespace) -> int:
    """Print comprehensive store health report. Read-only, no Outlook COM."""
    from .health import run_store_health
    import json as _json
    sr = args.store_root or get_store_root()
    try:
        report = run_store_health(store_root=sr)
    except Exception as e:
        print(f"Health report error: {e}")
        return 1
    if args.as_json:
        print(_json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    # Print human-readable summary
    src = report.get("source", {})
    bf = report.get("backfill", {})
    dr = report.get("derived", {})
    sa = report.get("safety", {})
    print("=" * 60)
    print("  Engine Exporter — Health Report")
    print("=" * 60)
    print(f"  Store root: {report.get('storeRoot', '?')}")
    print(f"  NOTE: The repo output folder is not the evidence store.")
    print(f"  The evidence store is under AppData KnowledgeStore.")
    print()
    print(f"  Records path:      {os.path.join(report.get('storeRoot', ''), 'records')}")
    print(f"  Extracts path:     {os.path.join(report.get('storeRoot', ''), 'extracts')}")
    print(f"  Conversations path: {os.path.join(report.get('storeRoot', ''), 'conversations')}")
    print(f"  Retrieval path:    {os.path.join(report.get('storeRoot', ''), 'retrieval')}")
    print(f"  Index path:        {os.path.join(report.get('storeRoot', ''), 'index')}")
    print()
    print("  Source / catalog:")
    print(f"    Source folders seen: {src.get('sourceFoldersSeen', '?')}")
    print(f"    Folders included:    {src.get('foldersIncluded', '?')}")
    print(f"    Folders excluded:    {src.get('foldersExcluded', '?')}")
    print(f"    Excluded stores:     {src.get('excludedStores', '?')}")
    print(f"    Primary store:       {src.get('storeDisplayName', '?')}")
    print(f"    Source scope:        {src.get('sourceScope', '?')}")
    print()
    print("  Backfill / ingest:")
    print(f"    Chunks total:       {bf.get('chunksTotal', '?')}")
    print(f"    Chunks pending:     {bf.get('chunksPending', '?')}")
    print(f"    Chunks complete:    {bf.get('chunksComplete', '?')}")
    print(f"    Chunks partial:     {bf.get('chunksPartial', '?')}")
    print(f"    Chunks failed:      {bf.get('chunksFailed', '?')}")
    print(f"    Records seen:       {bf.get('recordsSeen', '?')}")
    print(f"    Records exported:   {bf.get('recordsExported', '?')}")
    print(f"    Duplicates skipped: {bf.get('recordsSkippedDuplicate', '?')}")
    print(f"    Non-mail skipped:   {bf.get('nonMailItemsSkipped', '?')}")
    print(f"    Attachments seen:   {bf.get('attachmentsSeen', '?')}")
    print(f"    Extracts parsed:    {bf.get('extractsParsed', '?')}")
    print(f"    Extracts metadata:  {bf.get('extractsMetadataOnly', '?')}")
    print(f"    Extracts failed:    {bf.get('extractsFailed', '?')}")
    print(f"    Record JSON files:  {bf.get('recordJsonFilesCount', '?')}")
    print()
    print("  Derived store:")
    print(f"    Extract JSON files:           {dr.get('extractJsonFilesCount', '?')}")
    print(f"    Conversation JSON files:      {dr.get('conversationJsonFilesCount', '?')}")
    print(f"    Conversations latest lines:   {dr.get('conversationsLatestLines', '?')}")
    print(f"    Retrieval chunks latest lines: {dr.get('retrievalChunksLatestLines', '?')}")
    print(f"    recall.sqlite exists:         {dr.get('recallSqliteExists', '?')}")
    print(f"    Records indexed:              {dr.get('recordsIndexed', '?')}")
    print(f"    Conversations indexed:        {dr.get('conversationsIndexed', '?')}")
    print(f"    Chunks indexed:               {dr.get('chunksIndexed', '?')}")
    print()
    print("  Safety:")
    print(f"    Mailbox writes:     {sa.get('mailboxWrites', '?')}")
    print(f"    Kanban writes:      {sa.get('kanbanWrites', '?')}")
    print(f"    Cloud/API calls:    {sa.get('cloudApiCalls', '?')}")
    print(f"    Raw messages:       {sa.get('rawMessagesStored', '?')}")
    print(f"    Raw attachments:    {sa.get('rawAttachmentsSaved', '?')}")
    print(f"    Raw sources:        {sa.get('rawSourcesRetained', '?')}")
    print(f"    .msg files found:   {sa.get('msgFilesFound', '?')}")
    print(f"    .eml files found:   {sa.get('emlFilesFound', '?')}")
    print(f"    Temp/parsing files: {sa.get('tempParsingFiles', '?')}")
    print(f"    Suspicious binaries:{sa.get('suspiciousBinaryFiles', '?')}")
    print(f"    All checks pass:    {sa.get('allSafetyChecksPass', '?')}")
    print("=" * 60)
    for w in report.get("warnings", []):
        print(f"  Warning: {w}")
    for e in report.get("errors", []):
        print(f"  Error: {e}")
    return 0


def cmd_store_export_run(args: argparse.Namespace) -> int:
    """Run the chunked export pipeline with visible terminal progress.

    Runs store-ingest in batches until chunksPending is 0,
    or until a real error occurs, or --once is set.
    """
    from .ingest import run_ingest
    import json as _json
    sr = args.store_root or get_store_root()
    batch_size = getattr(args, "batch_size", 25)
    stop_on_error = getattr(args, "stop_on_error", False)
    once = getattr(args, "once", False)
    refresh_source = getattr(args, "refresh_source", False)
    parse_extracts = getattr(args, "parse_extracts", True)
    reparse_dups = getattr(args, "reparse_duplicate_attachments", False)
    att_timeout = getattr(args, "attachment_timeout_seconds", 30)
    until = getattr(args, "until", None)
    since = getattr(args, "since", None)
    resume = getattr(args, "resume", False)

    # If --refresh-source or no plan, run source scan and plan
    if refresh_source:
        from .source_scan import run_source_scan
        from .outlook_com_source import outlook_available
        print()
        print("=" * 60)
        print("  [store-export-run] Running source scan...")
        print("=" * 60)
        if not outlook_available():
            print("Outlook COM unavailable.")
            return 1
        catalog = run_source_scan(sr)
        included = sum(1 for f in catalog["folders"] if f.get("included"))
        print(f"  Source scan: {len(catalog['folders'])} folders seen, {included} included")
        print(f"  Store: {catalog.get('storeDisplayName', '?')}")

    # Check if plan exists
    plan_path = os.path.join(sr, "runs", "ingest_plan_latest.json")
    if not os.path.isfile(plan_path) or refresh_source:
        from .planning import create_backfill_plan
        print()
        print("=" * 60)
        print("  [store-export-run] Creating ingest plan...")
        print("=" * 60)
        plan = create_backfill_plan(
            sr,
            since=since or "2025-07-05",
            until=until or "2026-07-05",
        )
        print(f"  Plan: {len(plan['folders'])} folders, {len(plan['chunks'])} chunks")
        if args.since or args.until:
            print(f"  Date range: {plan.get('since', '?')} to {plan.get('until', '?')}")

    batch_num = 0
    total_pending_before = None

    while True:
        batch_num += 1
        print()
        print("=" * 60)
        print(f"  [store-export-run] Batch {batch_num} — max {batch_size} chunks")
        print("=" * 60)

        try:
            manifest = run_ingest(
                sr,
                resume=resume or True,
                max_chunks=batch_size,
                parse_extracts=parse_extracts,
                reparse_duplicate_attachments=reparse_dups,
                attachment_timeout_seconds=att_timeout,
                max_items_per_chunk=getattr(args, "max_items_per_chunk", 500),
                min_chunk_days=getattr(args, "min_chunk_days", 1),
                item_progress_every=getattr(args, "item_progress_every", 25),
            )
        except (FileNotFoundError, ValueError) as e:
            print(f"  ERROR: {e}")
            if stop_on_error:
                return 1
            break
        except Exception as e:
            print(f"  UNEXPECTED ERROR: {e}")
            if stop_on_error:
                return 1
            break

        # Print batch summary
        print()
        print("-" * 60)
        print(f"  Batch {batch_num} complete:")
        print(f"    Chunks attempted: {manifest.get('chunksAttempted', 0)}")
        print(f"    Chunks completed: {manifest.get('chunksCompleted', 0)}")
        print(f"    Chunks partial:   {manifest.get('chunksPartial', 0)}")
        print(f"    Chunks failed:    {manifest.get('chunksFailed', 0)}")
        print(f"    Records seen:     {manifest.get('recordsSeen', 0)}")
        print(f"    Records exported: {manifest.get('recordsExported', 0)}")
        print(f"    Duplicates skipped: {manifest.get('recordsSkippedDuplicate', 0)}")
        print(f"    Extracts seen:    {manifest.get('extractsSeen', 0)}")
        if manifest.get("errors"):
            for e in manifest["errors"]:
                print(f"    Error: {e}")
        print("-" * 60)

        # Check if more chunks remain
        try:
            from .health import run_store_health
            health = run_store_health(store_root=sr)
            pending = health.get("backfill", {}).get("chunksPending", 0)
            complete = health.get("backfill", {}).get("chunksComplete", 0)
            failed = health.get("backfill", {}).get("chunksFailed", 0)
            partial = health.get("backfill", {}).get("chunksPartial", 0)
            total = health.get("backfill", {}).get("chunksTotal", 0)
            print(f"  State: {pending} pending / {complete} complete / {partial} partial / {failed} failed / {total} total")

            if total_pending_before is not None and pending == total_pending_before:
                print()
                print("  WARNING: chunksPending has not changed — possible issue or no new chunks to process.")
                if stop_on_error:
                    return 1
                break

            total_pending_before = pending

            if pending == 0:
                print()
                print("=" * 60)
                print("  All backfill chunks complete!")
                print("=" * 60)
                break

            if once:
                print()
                print("  --once: stopping after this batch.")
                break

        except Exception as he:
            print(f"  Health check error: {he}")
            if stop_on_error:
                return 1
            break

        # Print run manifest path
        print()
        print(f"  Run manifest: runs/ingest_run_*.json")
        print(f"  Backfill state: state/backfill_state.json")
        print()

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

# ── Phase 1.6 — Build commands ────────────────────────────────────────


def cmd_store_build_conversations(args: argparse.Namespace) -> int:
    from .conversations import build_conversations
    store_root = args.store_root or get_store_root()
    try:
        manifest = build_conversations(store_root, export_run_id=args.export_run_id or "")
    except Exception as e:
        print(f"Error building conversations: {e}")
        return 1
    print(f"Engine Exporter — conversations")
    print(f"Conversations found: {manifest['conversationsFound']}")
    print(f"Records grouped: {manifest['recordsGrouped']}")
    print(f"Mailbox writes: {manifest['mailboxWrites']}")
    print(f"Kanban writes: {manifest['kanbanWrites']}")
    print(f"Cloud/API calls: {manifest['cloudApiCalls']}")
    print(f"Raw source retention: disabled")
    return 0


def cmd_store_build_retrieval(args: argparse.Namespace) -> int:
    from .retrieval import build_retrieval_chunks
    store_root = args.store_root or get_store_root()
    try:
        manifest = build_retrieval_chunks(store_root, export_run_id=args.export_run_id or "")
    except Exception as e:
        print(f"Error building retrieval chunks: {e}")
        return 1
    print(f"Engine Exporter — retrieval chunks")
    print(f"Records loaded: {manifest['recordsLoaded']}")
    print(f"Extracts loaded: {manifest['extractsLoaded']}")
    print(f"Conversations loaded: {manifest['conversationsLoaded']}")
    print(f"Chunks written: {manifest['chunksWritten']}")
    print(f"Mailbox writes: {manifest['mailboxWrites']}")
    print(f"Kanban writes: {manifest['kanbanWrites']}")
    print(f"Cloud/API calls: {manifest['cloudApiCalls']}")
    print(f"Raw source retention: disabled")
    return 0


def cmd_store_build_index(args: argparse.Namespace) -> int:
    from .index import build_index
    store_root = args.store_root or get_store_root()
    try:
        manifest = build_index(store_root, export_run_id=args.export_run_id or "")
    except Exception as e:
        print(f"Error building index: {e}")
        return 1
    print(f"Engine Exporter — SQLite recall index")
    print(f"Records indexed: {manifest['recordsIndexed']}")
    print(f"Conversations indexed: {manifest['conversationsIndexed']}")
    print(f"Chunks indexed: {manifest['chunksIndexed']}")
    print(f"Extracts indexed: {manifest['extractsIndexed']}")
    print(f"Mailbox writes: {manifest['mailboxWrites']}")
    print(f"Kanban writes: {manifest['kanbanWrites']}")
    print(f"Cloud/API calls: {manifest['cloudApiCalls']}")
    print(f"Raw source retention: disabled")
    if manifest.get("warnings"):
        for w in manifest["warnings"]:
            print(f"Warning: {w}")
    return 0


def cmd_store_search(args: argparse.Namespace) -> int:
    """Search the local evidence store via the public retrieval API."""
    from .retrieval import search as retrieval_search
    store_root = args.store_root or get_store_root()
    # Support both --limit (store-search) and --max-results (retrieval-search)
    limit = getattr(args, "limit", None) or getattr(args, "max_results", 10)
    try:
        response = retrieval_search(
            query=args.query,
            max_results=limit,
            since_days=getattr(args, "since_days", None),
            store_root=store_root,
        )
    except Exception as e:
        print(f"Search error: {e}")
        return 1

    if getattr(args, "as_json", False):
        import json
        print(json.dumps({
            "query": response.query,
            "max_results": response.max_results,
            "since_days": response.since_days,
            "status": response.status,
            "result_count": response.result_count,
            "results": [
                {
                    "record_id": r.record_id,
                    "source_type": r.source_type,
                    "title": r.title,
                    "subject": r.subject,
                    "folder_path": r.folder_path,
                    "received_at": r.received_at,
                    "sent_at": r.sent_at,
                    "conversation_id": r.conversation_id,
                    "snippet": r.snippet,
                    "score": r.score,
                }
                for r in response.results
            ],
            "warnings": response.warnings,
        }, indent=2, ensure_ascii=False))
        return 0

    print(f"Engine Exporter — search")
    print(f"Query: {response.query}")
    print(f"Results: {response.result_count}  Status: {response.status}")
    if response.since_days is not None:
        print(f"Recency: last {response.since_days} days")
    print()
    print("Local store search. No Outlook COM, no LLM, no cloud/API calls.")
    print()

    for i, r in enumerate(response.results[:limit], 1):
        print(f"{i}. {r.title or '(no title)'}")
        fp = r.folder_path or "N/A"
        dt = r.received_at or r.sent_at or "N/A"
        print(f"   Path: {fp}  Date: {dt}")
        print(f"   Type: {r.source_type}  Score: {r.score:.1f}")
        print(f"   {r.snippet[:200]}")
        print()

    for w in response.warnings:
        print(f"Warning: {w}")

    if not response.results and not response.warnings:
        print("No results found.")
    return 0


def cmd_store_query(args: argparse.Namespace) -> int:
    from .query_adapter import run_local_query
    store_root = args.store_root or get_store_root()
    parent_types = args.parent_type if args.parent_type else None
    source_kinds = args.source_kind if args.source_kind else None
    try:
        qr = run_local_query(
            args.query, store_root,
            limit=args.limit,
            date_from=args.date_from,
            date_to=args.date_to,
            folder_path=args.folder_path,
            folder_key=args.folder_key,
            parent_types=parent_types,
            source_kinds=source_kinds,
            include_extracts=not args.no_extracts,
            include_conversations=not args.no_conversations,
            include_chunk_text=args.include_text,
            max_chunk_chars=args.max_chunk_chars,
            min_score=args.min_score,
        )
    except Exception as e:
        print(f"Query error: {e}")
        return 1

    if args.as_json:
        import json
        print(json.dumps(qr, indent=2, ensure_ascii=False))
        return 0

    print(f"Engine Exporter — query")
    print(f"Query: {qr['queryText']}")
    print(f"Results: {qr['resultCount']}  Evidence: {qr['evidenceCount']}")
    print()
    print("Local query only. No Outlook COM, no LLM, no mailbox write, no Kanban write.")
    print()
    for r in qr.get("results", []):
        print(f"  {r['rank']}. {r['title']}")
        dt = r.get("date", "") or "N/A"
        fp = r.get("folderPath", "") or "N/A"
        sk = r.get("sourceKind", r.get("parentType", ""))
        print(f"     Date: {dt}  Path: {fp}  Kind: {sk}")
        print(f"     Chunk: {r['chunkKey'][:24]}...")
        print(f"     {r['textPreview'][:150]}...")
        print()
    if qr.get("warnings"):
        for w in qr["warnings"]:
            print(f"Warning: {w}")
    return 0

def cmd_store_bridge_query(args: argparse.Namespace) -> int:
    from .bridge import run_bridge_retrieval
    import json as _json
    sr = args.store_root or get_store_root()
    ctx = None
    if args.card_json_inline:
        try: ctx = _json.loads(args.card_json_inline)
        except Exception as e: print(f"JSON error: {e}"); return 1
    elif args.card_json:
        try:
            with open(args.card_json, encoding="utf-8") as f: ctx = _json.load(f)
        except Exception as e: print(f"File error: {e}"); return 1
    elif any([args.card_title, args.card_status, args.card_risk,
              args.card_lead, args.card_owner, args.card_current_state,
              args.card_next_action, args.card_last_updated]):
        ctx = {"cardTitle": args.card_title or "", "cardStatus": args.card_status or "",
               "cardRisk": args.card_risk or "", "cardLead": args.card_lead or "",
               "cardOwner": args.card_owner or "", "currentState": args.card_current_state or "",
               "nextAction": args.card_next_action or "", "lastUpdated": args.card_last_updated or "",
               "sourceCardHash": args.source_card_hash or ""}
    try:
        pack = run_bridge_retrieval(card_context=ctx, question=args.question,
            query_text=args.query, store_root=sr, caller="cli", limit=args.limit,
            include_chunk_text=args.include_text, max_chunk_chars=args.max_chunk_chars,
            min_score=args.min_score)
    except Exception as e: print(f"Bridge error: {e}"); return 1
    if args.as_json: print(_json.dumps(pack, indent=2, ensure_ascii=False)); return 0
    print(f"Bridge evidence retrieval")
    print(f"Caller: {pack['caller']}  Mode: {pack['mode']}")
    print(f"Query: {pack['queryText']}  Evidence: {pack['evidenceCount']}\n")
    print("Local bridge only. No Outlook COM, no LLM, no mailbox write, no Kanban write.\n")
    for i in pack.get("evidenceItems", []):
        dt = i.get("date","") or "N/A"; fp = i.get("folderPath","") or "N/A"; sk = i.get("sourceKind","")
        pv = (i.get("textPreview") or "")[:150]
        print(f"  {i['rank']}. {i['title']}")
        print(f"     Date: {dt}  Path: {fp}  Kind: {sk}")
        print(f"     Chunk: {i['chunkKey'][:24]}...  Score: {i['score']}")
        print(f"     {pv}...\n")
    for w in pack.get("warnings", []): print(f"Warning: {w}")
    return 0

def cmd_store_protect(args: argparse.Namespace) -> int:
    print("store-protect: not implemented in this phase")
    return 0

def cmd_store_verify_protection(args: argparse.Namespace) -> int:
    print("store-verify-protection: not implemented in this phase")
    return 0


# ── Phase 1.8F — Offline commands ───────────────────────────────────────


def cmd_store_audit_offline(args: argparse.Namespace) -> int:
    """Cross-validate records, conversations, chunks, and SQLite index. No Outlook COM."""
    import json as _json
    from .offline import audit_offline
    result = audit_offline()
    print("=" * 60)
    print("  Engine Exporter — Offline Audit")
    print("=" * 60)
    print(f"  Store root: {result.get('storeRoot', '?')}")
    print(f"  Mode: offline (no Outlook COM)")
    print()
    print(f"  Records: {result.get('records', {}).get('count', '?')}")
    print(f"  Records with conversationKey: {result.get('records', {}).get('withConversationKey', '?')}")
    print(f"  Orphan conversation keys: {result.get('records', {}).get('orphanConversationKeys', '?')}")
    print()
    print(f"  Conversations: {result.get('conversations', {}).get('count', '?')}")
    print(f"  Conversations with records: {result.get('conversations', {}).get('withRecords', '?')}")
    print(f"  Orphan conversations: {result.get('conversations', {}).get('orphanConversations', '?')}")
    print()
    print(f"  Chunks: {result.get('chunks', {}).get('count', '?')}")
    print(f"  Orphan chunks: {result.get('chunks', {}).get('orphanChunks', '?')}")
    print()
    print("  SQLite:")
    sqlite = result.get("sqlite", {})
    print(f"    records:       {sqlite.get('recordsCount', '?')}")
    print(f"    conversations: {sqlite.get('conversationsCount', '?')}")
    print(f"    chunks:        {sqlite.get('chunksCount', '?')}")
    print(f"    chunk_text:    {sqlite.get('chunk_textCount', '?')}")
    print()
    print(f"  Conversation join:     {'PASS' if result.get('conversationJoin', {}).get('pass') else 'FAIL'}")
    print(f"  Path normalisation:    {'PASS' if result.get('pathNormalisation', {}).get('check') else 'FAIL'}")
    print(f"  Attachment status:     {'explicit (deferred)' if result.get('attachmentStatus', {}).get('explicit') else 'missing'}")
    print(f"  Fixture markers:       {'FOUND: ' + str(result.get('fixtureMarkers', {}).get('fixtureCount', 0)) if result.get('fixtureMarkers', {}).get('found') else 'none'}")
    print()
    print("  Safety:")
    print(f"    Mailbox writes: 0")
    print(f"    Kanban writes:  0")
    print(f"    Cloud/API:      0")
    print(f"    Outlook COM:    not used")
    print(f"    LLM:            not used")
    print("=" * 60)
    for e in result.get("errors", []):
        print(f"  Error: {e}")
    for w in result.get("warnings", []):
        print(f"  Warning: {w}")
    return 0 if result.get("conversationJoin", {}).get("pass") else 1


def cmd_store_analyse_state(args: argparse.Namespace) -> int:
    """Comprehensive state analysis. No Outlook COM."""
    import json as _json
    from .offline import analyse_state
    result = analyse_state(offline=args.offline)
    if "error" in result:
        print(f"Error: {result['error']}")
        return 1
    print("=" * 60)
    print("  Engine Exporter — State Analysis")
    print("=" * 60)
    print(f"  Store root: {result.get('storeRoot', '?')}")
    print(f"  Mode: offline (no Outlook COM)")
    print()
    print(f"  Records on disk:         {result.get('recordsOnDisk', '?')}")
    print(f"  Conversations on disk:   {result.get('conversationsOnDisk', '?')}")
    print(f"  Chunks on disk:          {result.get('chunksOnDisk', '?')}")
    print()
    print("  Backfill state:")
    bf = result.get("backfillState", {})
    print(f"    Complete: {bf.get('complete', '?')}")
    print(f"    Pending:  {bf.get('pending', '?')}")
    print(f"    Partial:  {bf.get('partial', '?')}")
    print(f"    Failed:   {bf.get('failed', '?')}")
    print(f"    Pending=0:     {bf.get('pendingZero', '?')}")
    print(f"    Failed=0:      {bf.get('failedZero', '?')}")
    print(f"    Partials OK:   {bf.get('partialsAreNonBlocking', '?')}")
    print(f"    Can proceed:   {bf.get('canProceedWithPartials', '?')}")
    print()
    print(f"  Conversation join pass: {result.get('conversationJoinPass', '?')}")
    print(f"  Path normalisation pass:{result.get('pathNormalisationPass', '?')}")
    print(f"  Fixture count:          {result.get('fixtureCount', '?')}")
    print(f"  Attachment extract:     {result.get('attachmentExtractMode', '?')}")
    print(f"  Attachment parsing:     {'deferred' if result.get('attachmentParsingDeferred') else 'done'}")
    print(f"  Live mode safe:         {result.get('liveModeSafeToEnable', '?')}")
    print()
    print("  Safety:")
    safety = result.get("safety", {})
    print(f"    Mailbox writes: {safety.get('mailboxWrites', '?')}")
    print(f"    Kanban writes:  {safety.get('kanbanWrites', '?')}")
    print(f"    Cloud/API:      {safety.get('cloudApiCalls', '?')}")
    print(f"    Outlook COM:    not used")
    print(f"    LLM:            not used")
    print("=" * 60)
    for e in result.get("errors", []):
        print(f"  Error: {e}")
    for w in result.get("warnings", []):
        print(f"  Warning: {w}")
    return 0


def cmd_store_rebuild_derived(args: argparse.Namespace) -> int:
    """Deterministic rebuild of derived outputs. No Outlook COM."""
    from .offline import rebuild_derived
    print("=" * 60)
    print("  Engine Exporter — Derived Rebuild")
    print("=" * 60)
    print("  Mode: offline (no Outlook COM)")
    print("  Safeguards: mailbox write=0, kanban write=0, cloud/API=0, LLM=0")
    print()
    result = rebuild_derived(offline=args.offline, export_run_id=getattr(args, "export_run_id", ""))
    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return 1
    print(f"  Store root: {result.get('storeRoot', '?')}")
    print(f"  Backup path: (see .sami_backups)")
    print()
    for step in result.get("steps", []):
        status_sym = "\u2705" if step.get("status") == "ok" else "\u274c"
        print(f"  {status_sym} {step['name']}: {step['status']}")
    print()
    oc = result.get("outputCounts", {})
    print("  Output counts:")
    for k, v in oc.items():
        print(f"    {k}: {v}")
    print()
    print("  Safety checks:")
    print(f"    Mailbox writes: {result.get('mailboxWrites', 0)}")
    print(f"    Kanban writes:  {result.get('kanbanWrites', 0)}")
    print(f"    Cloud/API:      {result.get('cloudApiCalls', 0)}")
    print(f"    Outlook COM:    {'USED' if result.get('outlookComUsed') else 'not used'}")
    print(f"    LLM:            {'USED' if result.get('llmUsed') else 'not used'}")
    print(f"    Full mailbox:   {'YES' if result.get('fullMailboxReprocess') else 'no'}")
    print("=" * 60)
    for e in result.get("errors", []):
        print(f"  Error: {e}")
    return 1 if result.get("errors") else 0


def cmd_store_build_vault(args: argparse.Namespace) -> int:
    """Build deterministic vault Markdown notes. No Outlook COM. No LLM."""
    from .vault import build_vault
    print("=" * 60)
    print("  Engine Exporter — Vault Build")
    print("=" * 60)
    print("  Mode: offline (no Outlook COM)")
    print("  Safeguards: mailbox write=0, kanban write=0, cloud/API=0, LLM=0")
    print()
    result = build_vault()
    print(f"  Conversations loaded: {result.get('conversationsLoaded', 0)}")
    print(f"  Vault notes written:  {result.get('vaultNotesWritten', 0)}")
    print(f"  Dashboards written:   {result.get('vaultDashboardsWritten', 0)}")
    print()
    for folder, count in sorted(result.get("folderNoteCounts", {}).items()):
        print(f"    10_Conversations/{folder}: {count} notes")
    print()
    print("  Safety:")
    print(f"    Mailbox writes: {result.get('mailboxWrites', 0)}")
    print(f"    Kanban writes:  {result.get('kanbanWrites', 0)}")
    print(f"    Cloud/API:      {result.get('cloudApiCalls', 0)}")
    print(f"    Outlook COM:    {'USED' if result.get('outlookComUsed') else 'not used'}")
    print(f"    LLM:            {'USED' if result.get('llmUsed') else 'not used'}")
    print("=" * 60)
    for e in result.get("errors", []):
        print(f"  Error: {e}")
    return 0 if result.get("vaultNotesWritten", 0) > 0 else 1


def cmd_store_validate(args: argparse.Namespace) -> int:
    """Full offline validation. No Outlook COM."""
    from .offline import validate_offline
    print("=" * 60)
    print("  Engine Exporter — Validation")
    print("=" * 60)
    print("  Mode: offline (no Outlook COM)")
    print()
    result = validate_offline(require_sent_items=True, require_vault_notes=True)
    overall = result.get("overallResult", "FAIL")
    print(f"  Overall result: {overall}")
    print()
    print("  Checks:")
    for check_name, passed in result.get("checks", {}).items():
        sym = "\u2705" if passed else "\u274c"
        print(f"    {sym} {check_name}")
    print()
    print(f"  Failures: {len(result.get('failures', []))}")
    for f in result.get("failures", []):
        print(f"    \u274c {f}")
    print()
    print(f"  Warnings: {len(result.get('warnings', []))}")
    for w in result.get("warnings", []):
        print(f"    {w}")
    print()
    print("  Summary:")
    print(f"    Records:         {result.get('recordsOnDisk', '?')}")
    print(f"    Conversations:   {result.get('conversationsCount', '?')}")
    print(f"    Chunks:          {result.get('chunkCount', '?')}")
    print(f"    Chunk text rows: {result.get('chunkTextCount', '?')}")
    print(f"    Vault notes:     {result.get('vaultNoteCount', '?')}")
    print(f"    Sent Items:      {'yes' if result.get('sentItemsIncluded') else 'no'}")
    print(f"    Attachments:     {'deferred' if result.get('attachmentParsingDeferred') else 'parsed'}")
    print(f"    Live ready:      {'yes' if result.get('liveReady') else 'no'}")
    print()
    print("  Safety:")
    sa = result.get("safety", {})
    print(f"    Mailbox writes: {sa.get('mailboxWrites', 0)}")
    print(f"    Kanban writes:  {sa.get('kanbanWrites', 0)}")
    print(f"    Cloud/API:      {sa.get('cloudApiCalls', 0)}")
    print(f"    Outlook COM:    not used")
    print(f"    LLM:            not used")
    print("=" * 60)
    return 0 if overall == "PASS" else 1


# ── Phase 1.8F — Live commands ────────────────────────────────────────────


def cmd_store_live_status(args: argparse.Namespace) -> int:
    """Show current live state."""
    from .live import live_status
    result = live_status()
    print("=" * 60)
    print("  Engine Exporter — Live Status")
    print("=" * 60)
    print(f"  Live enabled:            {result.get('liveEnabled', False)}")
    print(f"  Last refresh started:    {result.get('lastRefreshStartedAt', '(never)')}")
    print(f"  Last refresh finished:   {result.get('lastRefreshFinishedAt', '(never)')}")
    print(f"  Polling interval:        {result.get('pollingIntervalMinutes', '?')} minutes")
    print(f"  Included folders:        {result.get('includedFolderCount', '?')}")
    print(f"  Sent Items included:     {result.get('includeSentItems', '?')}")
    print()
    print(f"  Inbox high-watermark:    {result.get('inboxHighWatermark', '(not set)')}")
    print(f"  Sent Items high-watermark: {result.get('sentItemsHighWatermark', '(not set)')}")
    print()
    print(f"  New records last run:    {result.get('newRecordsLastRun', 0)}")
    print(f"  Changed records last run: {result.get('changedRecordsLastRun', 0)}")
    print(f"  Duplicates skipped:      {result.get('duplicatesSkippedLastRun', 0)}")
    print(f"  Errors last run:         {result.get('errorsLastRun', 0)}")
    print()
    print("  Safety:")
    print(f"    Mailbox writes:         {result.get('mailboxWrites', 0)}")
    print(f"    Kanban writes:          {result.get('kanbanWrites', 0)}")
    print(f"    Cloud/API calls:        {result.get('cloudApiCalls', 0)}")
    print(f"    LLM used:               no")
    print(f"    Outlook COM write:      no (read-only)")
    print(f"    Raw .msg/.eml retention: no")
    print(f"    Raw attachment retention: no")
    print()
    print(f"  Store path:  {result.get('storeRoot', '?')}")
    print(f"  Recall DB:   {result.get('recallDbPath', result.get('storeRoot', '?'))}")
    print(f"  Vault path:  {result.get('vaultPath', result.get('storeRoot', '?'))}")
    print(f"  Quarantine:  {result.get('quarantinePath', result.get('storeRoot', '?'))}")
    print()
    print(f"  Validation status: {result.get('validationStatus', 'not checked')}")
    print("=" * 60)
    return 0


def cmd_store_live_enable(args: argparse.Namespace) -> int:
    """Enable near-live incremental refresh."""
    from .live import live_enable
    print("=" * 60)
    print("  Engine Exporter — Live Enable")
    print("=" * 60)
    print("  Validating offline store first...")
    result = live_enable(polling_interval_minutes=args.polling_interval)
    if result.get("error"):
        print(f"  FAILED: {result['error']}")
        if "validationResult" in result:
            vr = result["validationResult"]
            for f in vr.get("failures", []):
                print(f"    Validation failure: {f}")
        print("=" * 60)
        return 1
    print(f"  Live enabled:    {result.get('enabled', False)}")
    print(f"  Polling interval: {result.get('pollingIntervalMinutes', '?')} minutes")
    print(f"  Sent Items:      {'yes' if result.get('includeSentItems') else 'no'}")
    print(f"  Folders:         {result.get('folderCount', '?')} included")
    print(f"  Inbox HWM:       {result.get('inboxHighWatermark', '?')}")
    print(f"  Sent Items HWM:  {result.get('sentItemsHighWatermark', '?')}")
    print()
    print("  Safety: mailbox write=0, kanban write=0, cloud/API=0, read-only Outlook")
    print("=" * 60)
    return 0


def cmd_store_live_disable(args: argparse.Namespace) -> int:
    """Disable near-live incremental refresh."""
    from .live import live_disable
    result = live_disable()
    print("=" * 60)
    print("  Engine Exporter — Live Disable")
    print("=" * 60)
    print(f"  Live enabled: {result.get('liveEnabled', False)}")
    print("=" * 60)
    return 0


def cmd_store_live_refresh_once(args: argparse.Namespace) -> int:
    """Run one incremental refresh cycle. Only command allowed to read Outlook COM."""
    from .live import live_refresh_once
    print("=" * 60)
    print("  Engine Exporter — Live Refresh (once)")
    print("=" * 60)
    print("  Mode: incremental refresh (high-watermark + overlap)")
    print("  Safety: read-only Outlook COM, no mailbox/kanban/cloud writes")
    print("  Safeguards: high-watermark prevents full mailbox reprocess")
    print()
    result = live_refresh_once()
    if result.get("error"):
        print(f"  ERROR: {result['error']}")
        print("=" * 60)
        return 1
    print(f"  Store root:       {result.get('storeRoot', '?')}")
    print(f"  Folders processed: {result.get('foldersProcessed', 0)}")
    print(f"  Sent Items:       {'yes' if result.get('sentItemsIncluded') else 'no'}")
    print()
    print(f"  New records:       {result.get('newRecords', 0)}")
    print(f"  Changed records:   {result.get('changedRecords', 0)}")
    print(f"  Duplicates skipped: {result.get('duplicatesSkipped', 0)}")
    print(f"  Errors:            {result.get('errors', 0)}")
    print()
    for fld in result.get("refreshedFolders", []):
        print(f"    {fld.get('folderPath', '?')}: {fld.get('newRecords', 0)} new, {fld.get('changedRecords', 0)} changed")
    print()
    print("  Safety:")
    print(f"    Mailbox writes: {result.get('mailboxWrites', 0)}")
    print(f"    Kanban writes:  {result.get('kanbanWrites', 0)}")
    print(f"    Cloud/API:      {result.get('cloudApiCalls', 0)}")
    print(f"    Outlook COM:    used (read-only)")
    print(f"    Full mailbox:   {'YES' if result.get('fullMailboxReprocess') else 'no'}")
    if result.get("derivedRebuildStatus"):
        print(f"    Derived rebuild: {result.get('derivedRebuildStatus')}")
    if result.get("vaultUpdated"):
        print(f"    Vault update:    yes ({result.get('vaultNotesWritten', 0)} notes)")
    print("=" * 60)
    for em in result.get("errorMessages", []):
        print(f"  Error: {em}")
    return 0 if result.get("newRecords", 0) >= 0 else 1


# ── Argument parser ────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="export-engine", description="Engine Exporter — Local Mailbox Export Engine")
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
    p.add_argument("--reparse-duplicate-attachments", action="store_true", default=False)
    p.add_argument("--attachment-timeout-seconds", type=int, default=30)
    p.add_argument("--max-items-per-chunk", type=int, default=500)
    p.add_argument("--min-chunk-days", type=int, default=1)
    p.add_argument("--item-progress-every", type=int, default=25)
    p.add_argument("--build-retrieval", action="store_true", default=False)
    p.add_argument("--build-index", action="store_true", default=False)
    p.add_argument("--build-vault", action="store_true", default=False)
    p.add_argument("--build-canvas", action="store_true", default=False)
    p.set_defaults(func=cmd_store_ingest)

    # store-build-conversations
    p = sub.add_parser("store-build-conversations", help="Build conversation groupings from records")
    p.add_argument("--store-root", type=str, default=None)
    p.add_argument("--export-run-id", type=str, default=None)
    p.set_defaults(func=cmd_store_build_conversations)

    # store-build-retrieval
    p = sub.add_parser("store-build-retrieval", help="Build RAG retrieval chunks from records/extracts/conversations")
    p.add_argument("--store-root", type=str, default=None)
    p.add_argument("--export-run-id", type=str, default=None)
    p.set_defaults(func=cmd_store_build_retrieval)

    # store-build-index
    p = sub.add_parser("store-build-index", help="Build SQLite recall index from chunks")
    p.add_argument("--store-root", type=str, default=None)
    p.add_argument("--export-run-id", type=str, default=None)
    p.set_defaults(func=cmd_store_build_index)

    # store-search
    p = sub.add_parser("store-search", help="Local SQLite search (no LLM, no API)")
    p.add_argument("--query", type=str, required=True)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--since-days", type=int, default=None, dest="since_days")
    p.add_argument("--json", action="store_true", default=False, dest="as_json")
    p.add_argument("--store-root", type=str, default=None)
    p.set_defaults(func=cmd_store_search)

    # retrieval-search (Phase 1.8I — public API CLI)
    p = sub.add_parser("retrieval-search", help="Public retrieval search API (no LLM, no API)")
    p.add_argument("--query", type=str, required=True)
    p.add_argument("--max-results", type=int, default=10, dest="max_results")
    p.add_argument("--since-days", type=int, default=None, dest="since_days")
    p.add_argument("--json", action="store_true", default=False, dest="as_json")
    p.add_argument("--store-root", type=str, default=None)
    p.set_defaults(func=cmd_store_search)
    p = sub.add_parser("store-query", help="Local evidence query (no LLM, no API)")
    p.add_argument("--query", type=str, required=True)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--date-from", type=str, default=None)
    p.add_argument("--date-to", type=str, default=None)
    p.add_argument("--folder-path", type=str, default=None)
    p.add_argument("--folder-key", type=str, default=None)
    p.add_argument("--parent-type", type=str, action="append", default=None)
    p.add_argument("--source-kind", type=str, action="append", default=None)
    p.add_argument("--no-extracts", action="store_true", default=False, dest="no_extracts")
    p.add_argument("--no-conversations", action="store_true", default=False, dest="no_conversations")
    p.add_argument("--include-text", action="store_true", default=False, dest="include_text")
    p.add_argument("--max-chunk-chars", type=int, default=1200)
    p.add_argument("--min-score", type=float, default=0.0)
    p.add_argument("--json", action="store_true", default=False, dest="as_json")
    p.add_argument("--store-root", type=str, default=None)
    p.set_defaults(func=cmd_store_query)

    # store-bridge-query
    p = sub.add_parser("store-bridge-query", help="Bridge evidence retrieval (downstream integration)")
    p.add_argument("--query", type=str, default=None)
    p.add_argument("--question", type=str, default=None)
    p.add_argument("--card-json", type=str, default=None)
    p.add_argument("--card-json-inline", type=str, default=None)
    p.add_argument("--card-title", type=str, default=None)
    p.add_argument("--card-status", type=str, default=None)
    p.add_argument("--card-risk", type=str, default=None)
    p.add_argument("--card-lead", type=str, default=None)
    p.add_argument("--card-owner", type=str, default=None)
    p.add_argument("--card-current-state", type=str, default=None)
    p.add_argument("--card-next-action", type=str, default=None)
    p.add_argument("--card-last-updated", type=str, default=None)
    p.add_argument("--source-card-hash", type=str, default=None)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--include-text", action="store_true", default=False, dest="include_text")
    p.add_argument("--max-chunk-chars", type=int, default=1200)
    p.add_argument("--min-score", type=float, default=0.0)
    p.add_argument("--json", action="store_true", default=False, dest="as_json")
    p.add_argument("--store-root", type=str, default=None)
    p.set_defaults(func=cmd_store_bridge_query)

    # store-health
    p = sub.add_parser("store-health", help="Comprehensive store health report (read-only, no Outlook COM)")
    p.add_argument("--json", action="store_true", default=False, dest="as_json")
    p.add_argument("--store-root", type=str, default=None)
    p.set_defaults(func=cmd_store_health)

    # store-export-run
    p = sub.add_parser("store-export-run", help="Run chunked export pipeline with visible progress")
    p.add_argument("--since", type=str, default=None)
    p.add_argument("--until", type=str, default=None)
    p.add_argument("--resume", action="store_true", default=False)
    p.add_argument("--batch-size", type=int, default=25)
    p.add_argument("--once", action="store_true", default=False)
    p.add_argument("--stop-on-error", action="store_true", default=False)
    p.add_argument("--refresh-source", action="store_true", default=False)
    p.add_argument("--parse-extracts", action="store_true", default=True)
    p.add_argument("--reparse-duplicate-attachments", action="store_true", default=False)
    p.add_argument("--attachment-timeout-seconds", type=int, default=30)
    p.add_argument("--max-items-per-chunk", type=int, default=500)
    p.add_argument("--min-chunk-days", type=int, default=1)
    p.add_argument("--item-progress-every", type=int, default=25)
    p.add_argument("--json-summary", action="store_true", default=False)
    p.add_argument("--store-root", type=str, default=None)
    p.set_defaults(func=cmd_store_export_run)

    # Stub commands
    for cmd_name in [
        "store-refresh", "store-watch",
        "store-refresh-vault", "store-build-canvas", "store-refresh-canvas",
        "store-protect", "store-verify-protection",
    ]:
        p = sub.add_parser(cmd_name, help=f"Run {cmd_name}")
        p.set_defaults(func=_stub_for(cmd_name))

    # ── Phase 1.8F — Offline commands ──────────────────────────────────

    # store-audit-offline
    p = sub.add_parser("store-audit-offline", help="Cross-validate records, conversations, chunks, SQLite (no Outlook COM)")
    p.set_defaults(func=cmd_store_audit_offline)

    # store-analyse-state
    p = sub.add_parser("store-analyse-state", help="Comprehensive KnowledgeStore state analysis (no Outlook COM)")
    p.add_argument("--offline", action="store_true", default=True, dest="offline")
    p.set_defaults(func=cmd_store_analyse_state)

    # store-rebuild-derived
    p = sub.add_parser("store-rebuild-derived", help="Deterministic rebuild of conversations, chunks, SQLite, vault (no Outlook COM)")
    p.add_argument("--offline", action="store_true", default=True, dest="offline")
    p.add_argument("--export-run-id", type=str, default="")
    p.set_defaults(func=cmd_store_rebuild_derived)

    # store-build-vault
    p = sub.add_parser("store-build-vault", help="Build deterministic vault Markdown notes from conversation data (no Outlook COM)")
    p.add_argument("--offline", action="store_true", default=True, dest="offline")
    p.set_defaults(func=cmd_store_build_vault)

    # store-validate
    p = sub.add_parser("store-validate", help="Full offline validation of KnowledgeStore health and invariants (no Outlook COM)")
    p.add_argument("--offline", action="store_true", default=True, dest="offline")
    p.set_defaults(func=cmd_store_validate)

    # ── Phase 1.8F — Live commands ─────────────────────────────────────

    # store-live-status
    p = sub.add_parser("store-live-status", help="Show near-live incremental refresh state")
    p.set_defaults(func=cmd_store_live_status)

    # store-live-enable
    p = sub.add_parser("store-live-enable", help="Enable near-live incremental refresh")
    p.add_argument("--polling-interval", type=int, default=5, dest="polling_interval")
    p.set_defaults(func=cmd_store_live_enable)

    # store-live-disable
    p = sub.add_parser("store-live-disable", help="Disable near-live incremental refresh")
    p.set_defaults(func=cmd_store_live_disable)

    # store-live-refresh-once
    p = sub.add_parser("store-live-refresh-once", help="Run one incremental refresh cycle (only command allowed to read Outlook COM)")
    p.set_defaults(func=cmd_store_live_refresh_once)

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
