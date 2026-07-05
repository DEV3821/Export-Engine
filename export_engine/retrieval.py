"""Retrieval chunk builder and public search API — local evidence store.

Phase 1.8I: adds a stable generic public search() function with structured
SearchResponse/SearchResult dataclasses.

The search() function wraps the SQLite recall index (FTS5 or LIKE fallback)
and returns deterministic, read-only results. No LLM, no cloud, no mutations.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from .hashing import sha256_text, stable_json_hash
from .paths import get_store_root, ensure_store_layout


# ── Phase 1.8I — Public search schema ─────────────────────────────────


@dataclass
class SearchResult:
    """A single search result from the local evidence store.

    All fields are read-only representations of stored data.
    Generic — no adapter-specific references.
    """

    record_id: str
    """Unique chunk or record identifier."""

    source_type: str
    """Type of source (message, attachmentExtract, conversation, etc.)."""

    title: Optional[str] = None
    """Human-readable title or subject line."""

    subject: Optional[str] = None
    """Subject line (may duplicate title for message chunks)."""

    sender: Optional[str] = None
    """Sender/from address if available."""

    recipients: list[str] = field(default_factory=list)
    """Recipient email addresses."""

    folder_path: Optional[str] = None
    """Source folder path from the mailbox."""

    received_at: Optional[str] = None
    """ISO-8601 received date string."""

    sent_at: Optional[str] = None
    """ISO-8601 sent date string."""

    conversation_id: Optional[str] = None
    """Conversation grouping key if available."""

    snippet: str = ""
    """Short text preview of the chunk/record content."""

    score: float = 0.0
    """Deterministic relevance score (higher = better match)."""

    content_hash: Optional[str] = None
    """Content hash for dedup tracking if available."""

    record_path: Optional[str] = None
    """Path to the parent record or chunk on disk."""

    extract_paths: list[str] = field(default_factory=list)
    """Paths to related attachment extract files."""


@dataclass
class SearchResponse:
    """Structured response from the public retrieval search API.

    Read-only, deterministic, local-only.
    """

    query: str
    """The original search query."""

    max_results: int
    """Maximum number of results requested."""

    since_days: Optional[int] = None
    """Recency window in days (None = no filter)."""

    store_root: str = ""
    """Resolved store root path used for the search."""

    status: str = "ok"
    """Status of the search (ok, empty, warning, error)."""

    results: list[SearchResult] = field(default_factory=list)
    """Ordered list of search results."""

    warnings: list[str] = field(default_factory=list)
    """Non-fatal warnings about store state or search quality."""

    result_count: int = 0
    """Number of results returned (convenience field)."""


# ── Existing chunk builder (unchanged) ─────────────────────────────────


def _make_chunk_key(parent_key: str, ordinal: int) -> str:
    return sha256_text(f"chunk:{parent_key}:{ordinal}")


def _chunk_text(text: str, max_chars: int = 2000) -> list[str]:
    """Split text into chunks of at most max_chars characters."""
    if not text:
        return [""]
    if len(text) <= max_chars:
        return [text]
    chunks = []
    for i in range(0, len(text), max_chars):
        chunks.append(text[i:i + max_chars])
    return chunks


def build_retrieval_chunks(
    store_root: str | None = None,
    *,
    export_run_id: str = "",
) -> dict[str, Any]:
    """Read records/extracts/conversations and write retrieval chunks.

    Returns a manifest dict.
    """
    resolved = get_store_root(store_root)
    ensure_store_layout(resolved)
    now_iso = datetime.now(timezone.utc).isoformat()

    # Load records
    records_dir = os.path.join(resolved, "records")
    records: list[dict] = []
    for root, dirs, files in os.walk(records_dir):
        for fn in files:
            if fn.endswith(".json") and fn.startswith("record_"):
                try:
                    with open(os.path.join(root, fn), encoding="utf-8") as f:
                        records.append(json.load(f))
                except Exception:
                    pass

    # Load extracts
    extracts_dir = os.path.join(resolved, "extracts")
    extracts: list[dict] = []
    for root, dirs, files in os.walk(extracts_dir):
        for fn in files:
            if fn.endswith(".json"):
                try:
                    with open(os.path.join(root, fn), encoding="utf-8") as f:
                        extracts.append(json.load(f))
                except Exception:
                    pass

    # Load conversations
    conv_dir = os.path.join(resolved, "conversations")
    conversations: list[dict] = []
    for root, dirs, files in os.walk(conv_dir):
        for fn in files:
            if fn.endswith(".json") and fn.startswith("conversation_"):
                try:
                    with open(os.path.join(root, fn), encoding="utf-8") as f:
                        conversations.append(json.load(f))
                except Exception:
                    pass

    chunks_dir = os.path.join(resolved, "retrieval", "chunks")
    all_chunks: list[dict] = []
    manifest = {
        "recordsLoaded": len(records),
        "extractsLoaded": len(extracts),
        "conversationsLoaded": len(conversations),
        "chunksWritten": 0,
        "mailboxWrites": 0,
        "kanbanWrites": 0,
        "cloudApiCalls": 0,
        "rawSourcesRetained": 0,
    }

    # Chunks from message records
    for rec in records:
        rk = rec.get("recordKey", "")
        subj = rec.get("headers", {}).get("subject", "No subject")
        body = rec.get("content", {}).get("bodyText", "")
        dt = rec.get("headers", {}).get("receivedDateTime", "") or rec.get("headers", {}).get("sentDateTime", "")
        fp = rec.get("source", {}).get("folderPath", "")
        fk = rec.get("source", {}).get("folderKey", "")
        part_hash = sha256_text(rec.get("headers", {}).get("from", {}).get("emailAddress", ""))
        conv_key = rec.get("identity", {}).get("conversationKey", "")

        texts = _chunk_text(body)
        for i, t in enumerate(texts):
            ck = _make_chunk_key(rk, i)
            chunk_text = f"Subject: {subj}\n\n{t}" if t else f"Subject: {subj} (no body text)"
            chunk = {
                "_schema": "export.retrievalChunk.v1",
                "chunkKey": ck,
                "exportRunId": export_run_id,
                "parentType": "message",
                "parentKey": rk,
                "conversationKey": conv_key or "",
                "sourceRecordKeys": [rk],
                "sourceExtractKeys": [],
                "chunkOrdinal": i,
                "text": chunk_text,
                "textHash": sha256_text(chunk_text),
                "title": subj,
                "date": dt,
                "folderPath": fp,
                "folderKey": fk,
                "participantsHash": part_hash,
                "evidence": {
                    "recordKey": rk,
                    "extractKey": None,
                    "conversationKey": conv_key or None,
                    "sourcePath": fp,
                    "sourceKind": "outlookMessage",
                },
                "audit": {
                    "mailboxWrite": False, "kanbanWrite": False,
                    "cloudApiCalls": False, "rawSourceRetained": False,
                },
            }
            all_chunks.append(chunk)

    # Chunks from extracts
    for ex in extracts:
        ek = ex.get("extractKey", "")
        prk = ex.get("parentRecordKey", "")
        text = ex.get("content", {}).get("text", "")
        orig_name = ex.get("source", {}).get("originalName", "attachment")
        parse_status = ex.get("parse", {}).get("status", "unknown")

        if not text:
            text = f"[Attachment: {orig_name} — parse status: {parse_status}]"

        texts = _chunk_text(text)
        for i, t in enumerate(texts):
            ck = _make_chunk_key(ek, i)
            chunk = {
                "_schema": "export.retrievalChunk.v1",
                "chunkKey": ck,
                "exportRunId": export_run_id,
                "parentType": "attachmentExtract",
                "parentKey": ek,
                "conversationKey": "",
                "sourceRecordKeys": [prk] if prk else [],
                "sourceExtractKeys": [ek],
                "chunkOrdinal": i,
                "text": t,
                "textHash": sha256_text(t),
                "title": f"Attachment: {orig_name}",
                "date": "",
                "folderPath": "",
                "folderKey": "",
                "participantsHash": "",
                "evidence": {
                    "recordKey": prk or "",
                    "extractKey": ek,
                    "conversationKey": None,
                    "sourcePath": orig_name,
                    "sourceKind": "attachmentExtract",
                },
                "audit": {
                    "mailboxWrite": False, "kanbanWrite": False,
                    "cloudApiCalls": False, "rawSourceRetained": False,
                },
            }
            all_chunks.append(chunk)

    # Chunks from conversation summaries
    for cv in conversations:
        cvk = cv.get("conversationKey", "")
        subj = cv.get("subjectCanonical", "Conversation")
        msg_keys = cv.get("messageRecordKeys", [])
        msg_count = cv.get("messageCount", 0)
        summary = f"Conversation: {subj} ({msg_count} messages)"
        ck = _make_chunk_key(cvk, 0)
        chunk = {
            "_schema": "export.retrievalChunk.v1",
            "chunkKey": ck,
            "exportRunId": export_run_id,
            "parentType": "conversation",
            "parentKey": cvk,
            "conversationKey": cvk,
            "sourceRecordKeys": msg_keys,
            "sourceExtractKeys": [],
            "chunkOrdinal": 0,
            "text": summary,
            "textHash": sha256_text(summary),
            "title": f"Conversation: {subj}",
            "date": cv.get("dateRange", {}).get("first", ""),
            "folderPath": "",
            "folderKey": "",
            "participantsHash": "",
            "evidence": {
                "recordKey": "",
                "extractKey": None,
                "conversationKey": cvk,
                "sourcePath": f"conversations/{cvk[:8]}...",
                "sourceKind": "conversation",
            },
            "audit": {
                "mailboxWrite": False, "kanbanWrite": False,
                "cloudApiCalls": False, "rawSourceRetained": False,
            },
        }
        all_chunks.append(chunk)

    # Write per-month JSONL files
    month_groups: dict[str, list[dict]] = {}
    for c in all_chunks:
        dt = c.get("date", "") or now_iso
        ym = dt[:7] if len(dt) >= 7 else "unknown"
        month_groups.setdefault(ym, []).append(c)

    for ym, chunks in month_groups.items():
        cdir = os.path.join(chunks_dir, ym.replace("-", "/"))
        os.makedirs(cdir, exist_ok=True)
        jsonl_path = os.path.join(cdir, "chunks.jsonl")
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for c in chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")

    # Write chunks_latest.jsonl (deduplicated by chunkKey)
    seen_keys: set[str] = set()
    deduped_chunks: list[dict] = []
    for c in all_chunks:
        k = c.get("chunkKey", "")
        if k and k not in seen_keys:
            seen_keys.add(k)
            deduped_chunks.append(c)
        elif not k:
            deduped_chunks.append(c)

    latest_path = os.path.join(resolved, "retrieval", "chunks_latest.jsonl")
    with open(latest_path, "w", encoding="utf-8") as f:
        for c in deduped_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    manifest["chunksWritten"] = len(deduped_chunks)
    return manifest


# ── Phase 1.8I — Public search API ────────────────────────────────────


def search(
    query: str,
    max_results: int = 10,
    since_days: int | None = None,
    store_root: str | Path | None = None,
) -> SearchResponse:
    """Search the local evidence store.

    This is the stable public retrieval API for the engine.
    It wraps the SQLite recall index (FTS5 with LIKE fallback).

    Read-only, deterministic, local-only. No LLM, no cloud, no mutations.

    Args:
        query: Keyword search query (passed to FTS5 or LIKE).
        max_results: Maximum results to return (default 10).
        since_days: Only return results newer than this many days (None = no filter).
        store_root: Override the store root path (None = auto-detect).

    Returns:
        A SearchResponse with status, results, and warnings.

    Raises:
        No exceptions for normal operation — degraded states surface
        via warnings and status field.
    """
    resolved = str(get_store_root(str(store_root) if store_root else None))
    warnings: list[str] = []

    if not query or not query.strip():
        return SearchResponse(
            query=query or "",
            max_results=max_results,
            since_days=since_days,
            store_root=resolved,
            status="warning",
            results=[],
            warnings=["Empty query — no results returned."],
        )

    # Check if index exists
    index_dir = os.path.join(resolved, "index")
    db_path = os.path.join(index_dir, "recall.sqlite")
    if not os.path.isfile(db_path):
        warnings.append(
            f"SQLite recall index not found at {db_path}. "
            f"Run 'store-build-index' first."
        )
        # Fallback: search JSONL chunks directly
        return _search_jsonl_fallback(
            query=query.strip(),
            max_results=max_results,
            since_days=since_days,
            store_root=resolved,
            warnings=warnings,
        )

    # Search via SQLite index
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        fts_used = False
        raw_rows: list[dict[str, Any]] = []

        # Try FTS5 first
        try:
            cur = conn.execute(
                "SELECT c.chunkKey, c.title, c.date, c.folderPath, c.parentType, "
                "c.parentKey, c.sourceKind, c.conversationKey, ct.text, rank "
                "FROM chunks_fts "
                "JOIN chunks c ON chunks_fts.rowid = c.rowid "
                "JOIN chunk_text ct ON c.chunkKey = ct.chunkKey "
                "WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
                (query.strip(), max_results * 2),
            )
            for row in cur:
                raw_rows.append(dict(row))
            fts_used = True
        except Exception:
            pass

        # Fallback: LIKE search
        if not raw_rows:
            try:
                like = f"%{query.strip()}%"
                cur = conn.execute(
                    "SELECT c.chunkKey, c.title, c.date, c.folderPath, c.parentType, "
                    "c.parentKey, c.sourceKind, c.conversationKey, ct.text "
                    "FROM chunks c JOIN chunk_text ct ON c.chunkKey = ct.chunkKey "
                    "WHERE ct.text LIKE ? OR c.title LIKE ? OR c.folderPath LIKE ? "
                    "ORDER BY c.chunkKey LIMIT ?",
                    (like, like, like, max_results * 2),
                )
                for row in cur:
                    raw_rows.append(dict(row))
            except Exception:
                pass

        conn.close()

        if not raw_rows:
            if fts_used:
                warnings.append("FTS5 query returned no results. Try different keywords.")
            return SearchResponse(
                query=query.strip(),
                max_results=max_results,
                since_days=since_days,
                store_root=resolved,
                status="empty",
                results=[],
                warnings=warnings,
                result_count=0,
            )

        # Filter by since_days if specified
        if since_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
            filtered: list[dict[str, Any]] = []
            for row in raw_rows:
                dt_str = row.get("date", "")
                if dt_str:
                    try:
                        # Parse ISO-8601 date (may be partial like YYYY-MM-DD)
                        if len(dt_str) >= 10:
                            row_dt = datetime.fromisoformat(dt_str)
                            if row_dt.tzinfo is None:
                                row_dt = row_dt.replace(tzinfo=timezone.utc)
                            if row_dt >= cutoff:
                                filtered.append(row)
                        else:
                            filtered.append(row)
                    except (ValueError, TypeError):
                        filtered.append(row)
                else:
                    # No date — include (can't filter)
                    filtered.append(row)
            raw_rows = filtered

        # Limit and shape results
        raw_rows = raw_rows[:max_results]
        results = [_row_to_search_result(r) for r in raw_rows]
        # Sort by descending score
        results.sort(key=lambda r: r.score, reverse=True)

        status = "ok" if results else "empty"
        return SearchResponse(
            query=query.strip(),
            max_results=max_results,
            since_days=since_days,
            store_root=resolved,
            status=status,
            results=results,
            warnings=warnings,
            result_count=len(results),
        )

    except Exception as exc:
        warnings.append(f"SQLite index search failed: {exc}")
        return _search_jsonl_fallback(
            query=query.strip(),
            max_results=max_results,
            since_days=since_days,
            store_root=resolved,
            warnings=warnings,
        )


def _row_to_search_result(row: dict[str, Any]) -> SearchResult:
    """Convert a raw SQLite row dict to a SearchResult."""
    text = row.get("text", "") or ""
    rank = row.get("rank", 0.0)
    # Normalise rank for display (FTS5 rank is negative for good matches)
    score = -rank if rank < 0 else float(rank) if rank > 0 else 1.0

    return SearchResult(
        record_id=row.get("chunkKey", ""),
        source_type=row.get("sourceKind", row.get("parentType", "unknown")),
        title=row.get("title"),
        subject=row.get("title"),
        folder_path=row.get("folderPath"),
        received_at=row.get("date"),
        sent_at=row.get("date"),
        conversation_id=row.get("conversationKey"),
        snippet=text[:300].replace("\n", " ") if text else "",
        score=score,
        record_path=row.get("parentKey"),
    )


def _search_jsonl_fallback(
    query: str,
    max_results: int,
    since_days: int | None,
    store_root: str,
    warnings: list[str],
) -> SearchResponse:
    """Fallback search: scan JSONL retrieval chunks directly.

    Used when the SQLite index is missing or corrupted.
    """
    chunks_latest = os.path.join(store_root, "retrieval", "chunks_latest.jsonl")
    if not os.path.isfile(chunks_latest):
        warnings.append(
            f"No retrieval chunks found at {chunks_latest}. "
            f"Run 'store-build-retrieval' then 'store-build-index'."
        )
        return SearchResponse(
            query=query,
            max_results=max_results,
            since_days=since_days,
            store_root=store_root,
            status="error",
            results=[],
            warnings=warnings,
        )

    query_lower = query.lower()
    terms = query_lower.split()
    results: list[SearchResult] = []
    cutoff: datetime | None = None

    if since_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)

    try:
        with open(chunks_latest, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except Exception:
                    continue

                # Check date filter
                if cutoff is not None:
                    dt_str = chunk.get("date", "")
                    if dt_str and len(dt_str) >= 10:
                        try:
                            row_dt = datetime.fromisoformat(dt_str)
                            if row_dt.tzinfo is None:
                                row_dt = row_dt.replace(tzinfo=timezone.utc)
                            if row_dt < cutoff:
                                continue
                        except (ValueError, TypeError):
                            pass

                # Score match
                score = _compute_jsonl_score(chunk, query_lower, terms)
                if score <= 0:
                    continue

                title = chunk.get("title", "")
                text = chunk.get("text", "")
                ev = chunk.get("evidence", {})

                result = SearchResult(
                    record_id=chunk.get("chunkKey", ""),
                    source_type=ev.get("sourceKind", chunk.get("parentType", "unknown")),
                    title=title,
                    subject=title,
                    folder_path=chunk.get("folderPath"),
                    received_at=chunk.get("date"),
                    sent_at=chunk.get("date"),
                    conversation_id=chunk.get("conversationKey"),
                    snippet=text[:300].replace("\n", " ") if text else "",
                    score=score,
                    record_path=chunk.get("parentKey"),
                )
                results.append(result)

                if len(results) >= max_results:
                    break

        # Sort by descending score
        results.sort(key=lambda r: r.score, reverse=True)
    except Exception as exc:
        warnings.append(f"JSONL chunk search failed: {exc}")

    status = "ok" if results else "empty"
    return SearchResponse(
        query=query,
        max_results=max_results,
        since_days=since_days,
        store_root=store_root,
        status=status,
        results=results,
        warnings=warnings,
        result_count=len(results),
    )


def _compute_jsonl_score(
    chunk: dict[str, Any],
    query_lower: str,
    terms: list[str],
) -> float:
    """Simple deterministic relevance score for JSONL chunks."""
    title = (chunk.get("title") or "").lower()
    text = (chunk.get("text") or "").lower()
    folder = (chunk.get("folderPath") or "").lower()

    score = 0.0

    # Exact phrase match in title
    if query_lower and query_lower in title:
        score += 10.0
    # Exact phrase in text
    if query_lower and query_lower in text:
        score += 5.0
    # Term hits in title
    for t in terms:
        if t in title:
            score += 2.0
    # Term hits in text
    title_in_text = sum(1 for t in terms if t in text)
    score += title_in_text * 1.0
    # Folder path match
    if query_lower and query_lower in folder:
        score += 3.0

    return score
