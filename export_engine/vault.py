"""Vault Markdown builder — deterministic, no LLM, no Outlook COM.

Builds Obsidian-compatible Markdown notes from canonical conversation data.
Only uses already-exported records, conversations, and retrieval chunks.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from .hashing import sha256_text
from .paths import get_store_root, ensure_store_layout, ensure_vault_layout


def _make_frontmatter_field(key: str, value: Any) -> str:
    """Format a single YAML frontmatter field."""
    if isinstance(value, bool):
        return f"{key}: {'true' if value else 'false'}"
    elif isinstance(value, str):
        return f"{key}: {value}"
    elif isinstance(value, list):
        items = ", ".join(f'"{v}"' for v in value)
        return f"{key}: [{items}]"
    return f"{key}: {value}"


def build_vault(
    store_root: str | None = None,
    *,
    export_run_id: str = "",
) -> dict[str, Any]:
    """Build vault Markdown notes from existing conversation data.

    No Outlook COM. No LLM. No writes to mailbox/kanban/cloud.
    Returns a manifest dict.
    """
    resolved = get_store_root(store_root)
    ensure_store_layout(resolved)
    vault_root = os.path.join(resolved, "vault")
    ensure_vault_layout(resolved)

    now_iso = datetime.now(timezone.utc).isoformat()
    conv_dir = os.path.join(resolved, "conversations")
    retrieval_dir = os.path.join(resolved, "retrieval")
    conv_jsonl = os.path.join(conv_dir, "conversations_latest.jsonl")
    chunks_jsonl = os.path.join(retrieval_dir, "chunks_latest.jsonl")

    manifest: dict[str, Any] = {
        "conversationsLoaded": 0,
        "vaultNotesWritten": 0,
        "vaultDashboardsWritten": 0,
        "folderNoteCounts": {},
        "mailboxWrites": 0,
        "kanbanWrites": 0,
        "cloudApiCalls": 0,
        "llmUsed": False,
        "outlookComUsed": False,
        "rawSourcesRetained": 0,
        "warnings": [],
        "errors": [],
    }

    # Load conversations
    conversations: list[dict] = []
    if os.path.isfile(conv_jsonl):
        with open(conv_jsonl, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        conversations.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    manifest["conversationsLoaded"] = len(conversations)

    # Load chunks index by conversationKey
    chunk_by_conv: dict[str, list[dict]] = {}
    if os.path.isfile(chunks_jsonl):
        with open(chunks_jsonl, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        chunk = json.loads(line)
                        ck = chunk.get("conversationKey", "")
                        if ck:
                            chunk_by_conv.setdefault(ck, []).append(chunk)
                    except json.JSONDecodeError:
                        pass

    # Track note counts per vault folder
    folder_counts: dict[str, int] = {}
    conversations_dir = os.path.join(vault_root, "10_Conversations")
    os.makedirs(conversations_dir, exist_ok=True)

    # Write conversation notes
    for conv in conversations:
        ck = conv.get("conversationKey", "")
        if not ck:
            continue
        subj = conv.get("subjectCanonical", "(No Subject)")
        date_first = conv.get("dateRange", {}).get("first", "")
        date_last = conv.get("dateRange", {}).get("last", "")
        msg_count = conv.get("messageCount", 0)
        folder_keys = conv.get("folderKeys", [])
        record_keys = conv.get("messageRecordKeys", [])
        has_sent = any("sent" in str(fk).lower() for fk in folder_keys)

        # Collect evidence chunk text snippets (safe previews)
        conv_chunks = chunk_by_conv.get(ck, [])
        previews: list[str] = []
        for ch in conv_chunks[:5]:
            text = ch.get("text", "")
            if text:
                previews.append(text[:300].replace("\n", " ").strip())
        evidence_chunk_count = len(conv_chunks)

        # Build deterministic YAML frontmatter
        safe_title = subj[:120].replace('"', "'").replace("\n", " ")
        fm_lines = [
            "---",
            'schema: "export.vaultNote.v1"',
            "noteType: conversation",
            "conversationKey: " + ck,
            "sourceRecordKeys: [" + ", ".join('"' + rk + '"' for rk in record_keys[:20]) + "]",
            "dateFirst: " + date_first,
            "dateLast: " + date_last,
            "folderPaths: [" + ", ".join('"' + fp + '"' for fp in folder_keys[:10]) + "]",
            "source: outlook_primary_store_export",
            "offlineRefineOnly: true",
            "mailboxWrite: false",
            "kanbanWrite: false",
            "cloudApiCalls: false",
            "llmUsed: false",
            "attachmentStatus: deferred",
            "---",
        ]

        body_lines = [
            "# " + safe_title,
            "",
            "**Date range:** " + date_first + " -> " + date_last,
            "",
            "**Message count:** " + str(msg_count),
            "",
            "**Evidence chunk count:** " + str(evidence_chunk_count),
            "",
            "**Folders:** " + (", ".join(folder_keys[:10]) if folder_keys else "(none)"),
            "**Sent Items included:** " + ("yes" if has_sent else "no"),
            "",
            "**Attachment status:** deferred (attachment parsing not yet implemented)",
            "",
            "**Source record keys (" + str(len(record_keys)) + " total):**",
        ]
        for rk in record_keys[:20]:
            body_lines.append("- `" + rk + "`")
        if len(record_keys) > 20:
            body_lines.append("- ... and " + str(len(record_keys) - 20) + " more")

        body_lines.append("")
        body_lines.append("**Evidence previews:**")
        for i, pv in enumerate(previews, 1):
            body_lines.append("")
            body_lines.append(str(i) + ". " + pv + "...")

        if len(conv_chunks) > 5:
            body_lines.append("")
            body_lines.append("... and " + str(len(conv_chunks) - 5) + " more chunks")

        body_lines.append("")
        body_lines.append("---")
        body_lines.append(
            "*This note was generated deterministically from exported KnowledgeStore data.*"
        )
        body_lines.append(
            "*No LLM, no Outlook COM, no mailbox write, no Kanban write, no cloud/API.*"
        )

        full_note = "\n".join(fm_lines) + "\n" + "\n".join(body_lines) + "\n"

        # Write note by date prefix
        prefix = date_first[:7] if date_first and len(date_first) >= 7 else "unknown"
        note_dir = os.path.join(conversations_dir, prefix)
        os.makedirs(note_dir, exist_ok=True)
        note_path = os.path.join(note_dir, ck + ".md")

        try:
            with open(note_path, "w", encoding="utf-8") as f:
                f.write(full_note)
            manifest["vaultNotesWritten"] += 1
            folder_counts[prefix] = folder_counts.get(prefix, 0) + 1
        except OSError as e:
            manifest["errors"].append("Cannot write " + note_path + ": " + str(e))

    manifest["folderNoteCounts"] = folder_counts

    # Build dashboard
    dashboard_path = os.path.join(
        vault_root, "00_Dashboards", "Knowledge Store Status.md"
    )
    try:
        dashboard_content = _build_dashboard(resolved, manifest, now_iso)
        with open(dashboard_path, "w", encoding="utf-8") as f:
            f.write(dashboard_content)
        manifest["vaultDashboardsWritten"] = 1
    except OSError as e:
        manifest["errors"].append("Cannot write dashboard: " + str(e))

    return manifest


def _build_dashboard(
    store_root: str, vault_manifest: dict, now_iso: str
) -> str:
    """Build a deterministic status dashboard Markdown file."""
    from .health import run_store_health

    health = run_store_health(store_root=store_root)
    bf = health.get("backfill", {})
    dr = health.get("derived", {})
    sa = health.get("safety", {})
    src = health.get("source", {})

    sent_included = False
    cat_path = os.path.join(store_root, "catalog", "source_catalog_latest.json")
    if os.path.isfile(cat_path):
        try:
            with open(cat_path) as f:
                cat = json.load(f)
            for fld in cat.get("folders", []):
                role = fld.get("defaultRole", "").lower()
                if "sent" in role and fld.get("included"):
                    sent_included = True
                    break
        except Exception:
            pass

    live_path = os.path.join(store_root, "live_state.json")
    live_enabled = False
    live_interval = 5
    if os.path.isfile(live_path):
        try:
            with open(live_path) as f:
                live = json.load(f)
            live_enabled = live.get("liveEnabled", False)
            live_interval = live.get("pollingIntervalMinutes", 5)
        except Exception:
            pass

    note_counts = vault_manifest.get("folderNoteCounts", {})
    total_notes = sum(note_counts.values())

    lines = [
        "---",
        'schema: "export.vaultNote.v1"',
        "noteType: dashboard",
        "generatedAt: " + now_iso,
        "source: outlook_primary_store_export",
        "mailboxWrite: false",
        "kanbanWrite: false",
        "cloudApiCalls: false",
        "llmUsed: false",
        "---",
        "",
        "# Knowledge Store Status",
        "",
        "**Generated:** " + now_iso,
        "",
        "## Summary",
        "",
        "- **Repo root:** `C:\\Tools\\Export engine`",
        "- **Store root:** `" + store_root + "`",
        "- **Source store:** " + str(src.get("storeDisplayName", "(no catalog)")),
        "- **Source folders seen:** " + str(src.get("sourceFoldersSeen", "?")),
        "- **Source folders included:** " + str(src.get("foldersIncluded", "?")),
        "",
        "## Records & Content",
        "",
        "- **Canonical record files:** " + str(bf.get("recordJsonFilesCount", "?")),
        "- **Conversations:** " + str(dr.get("conversationsLatestLines", "?")),
        "- **Retrieval chunks:** " + str(dr.get("retrievalChunksLatestLines", "?")),
        "- **Chunk text rows:** " + str(dr.get("chunk_textIndexed", "?")),
        "- **Records indexed in SQLite:** " + str(dr.get("recordsIndexed", "?")),
        "- **Conversations indexed:** " + str(dr.get("conversationsIndexed", "?")),
        "- **Extract JSON files:** " + str(dr.get("extractJsonFilesCount", "?")),
        "",
        "## Backfill State",
        "",
        "- **Chunks total:** " + str(bf.get("chunksTotal", "?")),
        "- **Chunks pending:** " + str(bf.get("chunksPending", "?")),
        "- **Chunks complete:** " + str(bf.get("chunksComplete", "?")),
        "- **Chunks partial:** " + str(bf.get("chunksPartial", "?")),
        "- **Chunks failed:** " + str(bf.get("chunksFailed", "?")),
        "- **Records seen:** " + str(bf.get("recordsSeen", "?")),
        "- **Records exported:** " + str(bf.get("recordsExported", "?")),
        "- **Duplicates skipped:** " + str(bf.get("recordsSkippedDuplicate", "?")),
        "- **Attachments seen:** " + str(bf.get("attachmentsSeen", "?")),
        "- **Extracts parsed:** " + str(bf.get("extractsParsed", "?")),
        "",
        "## Sent Items",
        "",
        "- **Sent Items included:** " + ("yes" if sent_included else "no"),
        "",
        "## Live Incremental Refresh",
        "",
        "- **Live enabled:** " + ("yes" if live_enabled else "no"),
        "- **Polling interval:** " + str(live_interval) + " minutes",
        "",
        "## Attachment & Extract Status",
        "",
        "- **Attachment extraction mode:** deferred",
        "- **Extract files created:** " + str(dr.get("extractJsonFilesCount", "?")),
        "- **Attachment parsing deferred:** yes",
        "",
        "## Vault Notes",
        "",
        "- **Total Markdown notes:** " + str(total_notes),
        "- **Notes by top-level folder:**",
    ]
    for folder, count in sorted(note_counts.items()):
        lines.append("  - `10_Conversations/" + folder + "`: " + str(count) + " notes")

    lines.extend([
        "",
        "## Validation Status",
        "",
        "- **Conversation join:** not yet validated in dashboard",
        "- **Fixture quarantine:** not yet applied",
        "- **Path normalisation:** not yet validated in dashboard",
        "- **Attachment status explicit:** yes (deferred)",
        "",
        "## Safety",
        "",
        "- **Mailbox writes:** " + str(sa.get("mailboxWrites", "?")),
        "- **Kanban writes:** " + str(sa.get("kanbanWrites", "?")),
        "- **Cloud/API calls:** " + str(sa.get("cloudApiCalls", "?")),
        "- **Raw .msg/.eml files:** " + str(sa.get("msgFilesFound", "?")) + " / " + str(sa.get("emlFilesFound", "?")),
        "- **All safety checks pass:** " + str(sa.get("allSafetyChecksPass", "?")),
        "- **Outlook COM used:** no (offline build)",
        "- **LLM used:** no",
        "- **Full mailbox reprocess:** no",
        "",
        "---",
        "*This dashboard was generated deterministically from exported KnowledgeStore data.*",
        "*No LLM, no Outlook COM, no mailbox write, no Kanban write, no cloud/API calls.*",
        "",
    ])

    return "\n".join(lines)
