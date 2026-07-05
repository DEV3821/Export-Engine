"""Retrieval chunk builder — creates RAG-ready JSONL chunks from records/extracts/conversations."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from .hashing import sha256_text, stable_json_hash
from .paths import get_store_root, ensure_store_layout


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
