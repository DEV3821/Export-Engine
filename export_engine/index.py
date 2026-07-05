"""SQLite recall index — builds a local FTS5 search index from records/chunks/conversations."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .paths import get_store_root, ensure_store_layout
from .hashing import sha256_text


def _detect_fts5(conn: sqlite3.Connection) -> bool:
    """Check if FTS5 is available."""
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts_test USING fts5(content=())")
        conn.execute("DROP TABLE IF EXISTS _fts_test")
        return True
    except Exception:
        return False


def build_index(
    store_root: str | None = None,
    *,
    export_run_id: str = "",
) -> dict[str, Any]:
    """Build SQLite recall index from retrieval chunks, records, conversations.

    Returns a manifest dict.
    """
    resolved = get_store_root(store_root)
    ensure_store_layout(resolved)
    index_dir = os.path.join(resolved, "index")
    os.makedirs(index_dir, exist_ok=True)
    db_path = os.path.join(index_dir, "recall.sqlite")

    conn = sqlite3.connect(db_path)
    has_fts5 = _detect_fts5(conn)
    warnings = []
    if not has_fts5:
        warnings.append("FTS5 not available — using LIKE fallback")

    # Load retrieval chunks
    chunks_latest = os.path.join(resolved, "retrieval", "chunks_latest.jsonl")
    chunks_list: list[dict] = []
    if os.path.isfile(chunks_latest):
        with open(chunks_latest, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        chunks_list.append(json.loads(line))
                    except Exception:
                        pass

    # Load records for record index
    records_dir = os.path.join(resolved, "records")
    records_list: list[dict] = []
    for root, dirs, files in os.walk(records_dir):
        for fn in files:
            if fn.endswith(".json") and fn.startswith("record_"):
                try:
                    with open(os.path.join(root, fn), encoding="utf-8") as f:
                        records_list.append(json.load(f))
                except Exception:
                    pass

    # Load conversations
    conv_dir = os.path.join(resolved, "conversations")
    conv_list: list[dict] = []
    for root, dirs, files in os.walk(conv_dir):
        for fn in files:
            if fn.endswith(".json") and fn.startswith("conversation_"):
                try:
                    with open(os.path.join(root, fn), encoding="utf-8") as f:
                        conv_list.append(json.load(f))
                except Exception:
                    pass

    # Create tables
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS records (
            recordKey TEXT PRIMARY KEY,
            subject TEXT,
            subjectHash TEXT,
            sentDateTime TEXT,
            receivedDateTime TEXT,
            folderPath TEXT,
            folderKey TEXT,
            conversationKey TEXT,
            hasAttachments INTEGER,
            attachmentCount INTEGER,
            extractCount INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            conversationKey TEXT PRIMARY KEY,
            subjectCanonical TEXT,
            messageCount INTEGER,
            attachmentCount INTEGER,
            extractCount INTEGER,
            firstDateTime TEXT,
            lastDateTime TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunkKey TEXT PRIMARY KEY,
            parentType TEXT,
            parentKey TEXT,
            conversationKey TEXT,
            textHash TEXT,
            title TEXT,
            date TEXT,
            folderPath TEXT,
            folderKey TEXT,
            sourceKind TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunk_text (
            chunkKey TEXT PRIMARY KEY,
            text TEXT
        )
    """)

    # FTS5 table
    if has_fts5:
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
                USING fts5(title, text, folderPath, content='chunk_text', content_rowid='rowid')
            """)
        except Exception:
            warnings.append("FTS5 table creation failed — using LIKE fallback")
            has_fts5 = False

    # Insert records
    records_indexed = 0
    for rec in records_list:
        rk = rec.get("recordKey", "")
        if not rk:
            continue
        subj = rec.get("headers", {}).get("subject", "")
        sent = rec.get("headers", {}).get("sentDateTime", "")
        recv = rec.get("headers", {}).get("receivedDateTime", "")
        fp = rec.get("source", {}).get("folderPath", "")
        fk = rec.get("source", {}).get("folderKey", "")
        ck = rec.get("identity", {}).get("conversationKey", "")
        has_att = 1 if rec.get("attachments", {}).get("count", 0) > 0 else 0
        att_cnt = rec.get("attachments", {}).get("count", 0)
        ext_cnt = len(rec.get("extracts", []))
        try:
            conn.execute(
                "INSERT OR REPLACE INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (rk, subj, sha256_text(subj), sent, recv, fp, fk, ck, has_att, att_cnt, ext_cnt),
            )
            records_indexed += 1
        except Exception:
            pass

    # Insert conversations
    convs_indexed = 0
    for cv in conv_list:
        cvk = cv.get("conversationKey", "")
        if not cvk:
            continue
        subj = cv.get("subjectCanonical", "")
        msg_c = cv.get("messageCount", 0)
        att_c = cv.get("attachmentCount", 0)
        ext_c = cv.get("extractCount", 0)
        fd = cv.get("dateRange", {}).get("first", "")
        ld = cv.get("dateRange", {}).get("last", "")
        try:
            conn.execute(
                "INSERT OR REPLACE INTO conversations VALUES (?,?,?,?,?,?,?)",
                (cvk, subj, msg_c, att_c, ext_c, fd, ld),
            )
            convs_indexed += 1
        except Exception:
            pass

    # Insert chunks
    chunks_indexed = 0
    for ch in chunks_list:
        ck = ch.get("chunkKey", "")
        if not ck:
            continue
        pt = ch.get("parentType", "")
        pk = ch.get("parentKey", "")
        cvk = ch.get("conversationKey", "")
        th = ch.get("textHash", "")
        title = ch.get("title", "")
        dt = ch.get("date", "")
        fp = ch.get("folderPath", "")
        fk = ch.get("folderKey", "")
        sk = ch.get("evidence", {}).get("sourceKind", "")
        text = ch.get("text", "")
        try:
            conn.execute(
                "INSERT OR REPLACE INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?)",
                (ck, pt, pk, cvk, th, title, dt, fp, fk, sk),
            )
            conn.execute(
                "INSERT OR REPLACE INTO chunk_text VALUES (?,?)",
                (ck, text),
            )
            chunks_indexed += 1
        except Exception:
            pass

    conn.commit()

    # Build FTS index
    if has_fts5:
        try:
            conn.execute("INSERT INTO chunks_fts (rowid, title, text, folderPath) "
                         "SELECT ct.rowid, c.title, ct.text, c.folderPath "
                         "FROM chunk_text ct JOIN chunks c ON ct.chunkKey = c.chunkKey")
            conn.commit()
        except Exception:
            warnings.append("FTS5 population failed")

    conn.close()

    now_iso = datetime.now(timezone.utc).isoformat()
    manifest = {
        "_schema": "export.sqliteIndexRun.v1",
        "indexRunId": sha256_text(f"index:{export_run_id}:{now_iso}"),
        "exportRunId": export_run_id,
        "startedAt": now_iso,
        "finishedAt": now_iso,
        "sqlitePath": db_path,
        "recordsIndexed": records_indexed,
        "conversationsIndexed": convs_indexed,
        "chunksIndexed": chunks_indexed,
        "extractsIndexed": 0,
        "mailboxWrites": 0,
        "kanbanWrites": 0,
        "cloudApiCalls": 0,
        "rawSourcesRetained": 0,
        "warnings": warnings,
        "errors": [],
    }

    return manifest


def search_index(
    query: str,
    store_root: str | None = None,
    *,
    limit: int = 10,
    as_json: bool = False,
) -> list[dict[str, Any]]:
    """Search the SQLite recall index.

    Returns a list of result dicts with evidence pointers.
    """
    resolved = get_store_root(store_root)
    db_path = os.path.join(resolved, "index", "recall.sqlite")
    if not os.path.isfile(db_path):
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    results: list[dict[str, Any]] = []

    # Try FTS5 first
    try:
        cur = conn.execute(
            "SELECT c.chunkKey, c.title, c.date, c.folderPath, c.parentType, c.parentKey, "
            "c.sourceKind, c.conversationKey, ct.text, "
            "rank FROM chunks_fts JOIN chunks c ON chunks_fts.rowid = c.rowid "
            "JOIN chunk_text ct ON c.chunkKey = ct.chunkKey "
            "WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
            (query, limit),
        )
        for row in cur:
            results.append(dict(row))
        conn.close()
        return results
    except Exception:
        pass

    # Fallback: LIKE search
    try:
        like = f"%{query}%"
        cur = conn.execute(
            "SELECT c.chunkKey, c.title, c.date, c.folderPath, c.parentType, c.parentKey, "
            "c.sourceKind, c.conversationKey, ct.text "
            "FROM chunks c JOIN chunk_text ct ON c.chunkKey = ct.chunkKey "
            "WHERE ct.text LIKE ? OR c.title LIKE ? OR c.folderPath LIKE ? "
            "LIMIT ?",
            (like, like, like, limit),
        )
        for row in cur:
            results.append(dict(row))
    except Exception:
        pass

    conn.close()
    return results
