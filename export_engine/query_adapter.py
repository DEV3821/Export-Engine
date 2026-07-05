"""Evidence-bound local query adapter for the Local Knowledge Store.

Provides a deterministic, local-only query layer that returns structured
evidence packs from the SQLite recall index and retrieval chunks.
No Outlook COM, no LLM, no Hermes, no cloud/API calls.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from .paths import get_store_root
from .hashing import sha256_text


# ── Deterministic scoring helpers ──────────────────────────────────────


def _score_row(
    row: dict[str, Any],
    query_lower: str,
    terms: list[str],
) -> float:
    """Simple deterministic relevance score.

    Boosts: exact phrase match, title match, term density.
    """
    score = 1.0
    title = (row.get("title") or "").lower()
    text = (row.get("text") or "").lower()
    folder = (row.get("folderPath") or "").lower()

    # Exact phrase match in title
    if query_lower in title:
        score += 10.0
    # Exact phrase match in text
    if query_lower in text:
        score += 5.0
    # Term density in title
    for t in terms:
        if t in title:
            score += 2.0
    # Term density in text
    title_in_text = sum(1 for t in terms if t in text)
    score += title_in_text * 1.0
    # Folder match
    if query_lower in folder:
        score += 3.0

    return score


# ── Filter matching ────────────────────────────────────────────────────


def _matches_filters(
    row: dict[str, Any],
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    folder_path: str | None = None,
    folder_key: str | None = None,
    parent_types: list[str] | None = None,
    source_kinds: list[str] | None = None,
    include_extracts: bool = True,
    include_conversations: bool = True,
) -> bool:
    """Check if a result row matches all active filters."""
    # Parent type filter
    pt = row.get("parentType", "")
    if not include_extracts and pt == "attachmentExtract":
        return False
    if not include_conversations and pt == "conversation":
        return False
    if parent_types and pt not in parent_types:
        return False

    # Source kind filter
    sk = row.get("sourceKind", "")
    if source_kinds and sk not in source_kinds:
        return False

    # Date filter
    dt = row.get("date", "") or ""
    if date_from and dt and dt < date_from:
        return False
    if date_to and dt and dt > date_to:
        return False

    # Folder path filter
    if folder_path and folder_path.lower() not in (row.get("folderPath") or "").lower():
        return False

    # Folder key filter
    if folder_key and folder_key != row.get("folderKey", ""):
        return False

    return True


# ── Main query function ────────────────────────────────────────────────


def run_local_query(
    query_text: str,
    store_root: str | None = None,
    *,
    limit: int = 10,
    date_from: str | None = None,
    date_to: str | None = None,
    folder_path: str | None = None,
    folder_key: str | None = None,
    parent_types: list[str] | None = None,
    source_kinds: list[str] | None = None,
    include_extracts: bool = True,
    include_conversations: bool = True,
    include_chunk_text: bool = False,
    max_chunk_chars: int = 1200,
    min_score: float = 0.0,
) -> dict[str, Any]:
    """Run a local evidence query against the SQLite recall index.

    Returns a structured query result dict (export.queryResult.v1).
    """
    resolved = get_store_root(store_root)
    db_path = os.path.join(resolved, "index", "recall.sqlite")
    now_iso = datetime.now(timezone.utc).isoformat()
    query_id = sha256_text(f"query:{query_text}:{now_iso}:{uuid.uuid4().hex}")

    result: dict[str, Any] = {
        "_schema": "export.queryResult.v1",
        "queryId": query_id,
        "queryText": query_text,
        "createdAt": now_iso,
        "storeRoot": resolved,
        "sqlitePath": db_path,
        "resultCount": 0,
        "evidenceCount": 0,
        "results": [],
        "warnings": [],
        "errors": [],
        "audit": {
            "mailboxWrites": 0,
            "kanbanWrites": 0,
            "cloudApiCalls": 0,
            "outlookComUsed": False,
            "hermesUsed": False,
            "llmUsed": False,
            "rawSourcesRetained": 0,
        },
    }

    if not os.path.isfile(db_path):
        result["warnings"].append(
            "SQLite recall index not found. Run store-build-index first."
        )
        return result

    query_lower = query_text.lower().strip()
    terms = [t for t in re.split(r"\W+", query_lower) if len(t) > 1]

    if not terms and not query_lower:
        result["warnings"].append("Empty query.")
        return result

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    raw_results: list[dict[str, Any]] = []

    # Try FTS5 first
    fts_used = False
    try:
        # Build FTS5 query: terms joined by AND for phrase, terms OR for individual
        fts_query = query_lower
        cur = conn.execute(
            "SELECT c.chunkKey, c.title, c.date, c.folderPath, "
            "c.parentType, c.parentKey, c.sourceKind, c.conversationKey, "
            "ct.text, c.chunkKey as rank "
            "FROM chunks_fts JOIN chunks c ON chunks_fts.rowid = c.rowid "
            "JOIN chunk_text ct ON c.chunkKey = ct.chunkKey "
            "WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
            (fts_query, limit * 3),  # fetch extra for filtering
        )
        for row in cur:
            d = dict(row)
            d["_matchSource"] = "fts5"
            # FTS5 rank: lower = better, convert to score
            d["_score"] = max(1.0, 100.0 - float(d.get("rank", 50)))
            raw_results.append(d)
        fts_used = True
    except Exception:
        pass

    # Fallback or additional LIKE search
    if not fts_used:
        try:
            like = f"%{query_lower}%"
            cur = conn.execute(
                "SELECT c.chunkKey, c.title, c.date, c.folderPath, "
                "c.parentType, c.parentKey, c.sourceKind, c.conversationKey, "
                "ct.text, 0 as rank "
                "FROM chunks c JOIN chunk_text ct ON c.chunkKey = ct.chunkKey "
                "WHERE ct.text LIKE ? OR c.title LIKE ? OR c.folderPath LIKE ? "
                "LIMIT ?",
                (like, like, like, limit * 3),
            )
            for row in cur:
                d = dict(row)
                d["_matchSource"] = "like"
                d["_score"] = _score_row(d, query_lower, terms)
                raw_results.append(d)
        except Exception as e:
            result["errors"].append(f"Search query failed: {e}")

    conn.close()

    # Dedupe by chunkKey
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for r in raw_results:
        ck = r.get("chunkKey", "")
        if ck and ck not in seen:
            seen.add(ck)
            deduped.append(r)

    # Apply filters
    filtered = [
        r for r in deduped
        if _matches_filters(
            r,
            date_from=date_from,
            date_to=date_to,
            folder_path=folder_path,
            folder_key=folder_key,
            parent_types=parent_types,
            source_kinds=source_kinds,
            include_extracts=include_extracts,
            include_conversations=include_conversations,
        )
    ]

    # Sort by score descending
    filtered.sort(key=lambda r: -r.get("_score", 0))

    # Apply min_score and limit
    scored = [r for r in filtered if r.get("_score", 0) >= min_score][:limit]

    # Build result entries
    for rank, r in enumerate(scored, 1):
        text = r.get("text", "") or ""
        text_preview = text[:max_chunk_chars] if include_chunk_text else text[:200]

        entry = {
            "rank": rank,
            "score": round(r.get("_score", 0), 2),
            "chunkKey": r.get("chunkKey", ""),
            "parentType": r.get("parentType", ""),
            "parentKey": r.get("parentKey", ""),
            "conversationKey": r.get("conversationKey", "") or None,
            "title": r.get("title", ""),
            "date": r.get("date", "") or "",
            "folderPath": r.get("folderPath", "") or "",
            "folderKey": r.get("folderKey", "") or "",
            "sourceKind": r.get("sourceKind", "") or "",
            "textPreview": text_preview,
            "textHash": sha256_text(text),
            "evidence": {
                "recordKey": r.get("parentKey", "") if r.get("parentType") in ("message",) else "",
                "extractKey": r.get("parentKey", "") if r.get("parentType") in ("attachmentExtract",) else None,
                "conversationKey": r.get("conversationKey", "") or None,
                "sourcePath": r.get("folderPath", "") or "",
                "sourceKind": r.get("sourceKind", "") or "",
            },
        }
        result["results"].append(entry)

    result["resultCount"] = len(result["results"])
    result["evidenceCount"] = sum(1 for r in result["results"] if r.get("evidence", {}).get("recordKey") or r.get("evidence", {}).get("extractKey"))

    if not result["results"]:
        result["warnings"].append("No matching evidence found.")

    return result


# ── Evidence pack builder ──────────────────────────────────────────────


def build_evidence_pack(
    query_result: dict[str, Any],
    query_text: str = "",
    limit: int = 10,
) -> dict[str, Any]:
    """Build a compact evidence pack suitable for Hermes/Mr Kanban.

    Self-contained payload with proof-of-provenance for every claim.
    """
    pack = {
        "_schema": "export.evidencePack.v1",
        "queryText": query_text or query_result.get("queryText", ""),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "evidenceCount": query_result.get("evidenceCount", 0),
        "resultCount": query_result.get("resultCount", 0),
        "evidence": [],
        "warnings": query_result.get("warnings", []),
        "audit": {
            "outlookComUsed": False,
            "hermesUsed": False,
            "llmUsed": False,
            "mailboxWrites": 0,
            "kanbanWrites": 0,
            "cloudApiCalls": 0,
            "rawSourcesRetained": 0,
        },
    }

    for r in query_result.get("results", [])[:limit]:
        item = {
            "rank": r.get("rank", 0),
            "title": r.get("title", ""),
            "date": r.get("date", ""),
            "folderPath": r.get("folderPath", ""),
            "sourceKind": r.get("sourceKind", ""),
            "textPreview": r.get("textPreview", ""),
            "chunkKey": r.get("chunkKey", ""),
            "evidence": r.get("evidence", {}),
        }
        pack["evidence"].append(item)

    return pack
