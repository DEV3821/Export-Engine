"""Conversation builder — groups canonical records into conversation threads."""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .hashing import sha256_text, stable_json_hash
from .paths import get_store_root, ensure_store_layout


def _normalise_subject(subj: str) -> str:
    """Strip RE:/FW:/ prefixes for matching."""
    s = re.sub(r"^(fwd|fw|re|aw|wg)\s*:?\s*", "", subj, flags=re.IGNORECASE)
    return s.strip()


def _hash_participants(rec: dict) -> str:
    """Deterministic hash of all participant email addresses."""
    addrs = []
    fr = rec.get("headers", {}).get("from", {}).get("emailAddress", "")
    if fr:
        addrs.append(fr.lower())
    for f in ("to", "cc"):
        for entry in rec.get("headers", {}).get(f, []):
            ea = entry.get("emailAddress", "")
            if ea:
                addrs.append(ea.lower())
    return sha256_text("|".join(sorted(set(addrs))))


def _make_conversation_key_from_conv_id(conv_id: str) -> str:
    return sha256_text(f"conversationId:{conv_id}")


def _make_conversation_key_from_fallback(subject_norm: str, part_hash: str) -> str:
    return stable_json_hash({"subjectNorm": subject_norm, "participantHash": part_hash})


def build_conversations(
    store_root: str | None = None,
    *,
    export_run_id: str = "",
) -> dict[str, Any]:
    """Read canonical records and build conversation groupings.

    Returns a manifest dict.
    """
    resolved = get_store_root(store_root)
    ensure_store_layout(resolved)
    records_dir = os.path.join(resolved, "records")
    now_iso = datetime.now(timezone.utc).isoformat()

    # Discover all record files
    record_paths: list[str] = []
    for root, dirs, files in os.walk(records_dir):
        for fn in files:
            if fn.endswith(".json") and fn.startswith("record_"):
                record_paths.append(os.path.join(root, fn))

    # Load records
    records: list[dict] = []
    for rp in record_paths:
        try:
            with open(rp, encoding="utf-8") as f:
                records.append(json.load(f))
        except Exception:
            pass

    # Group by conversation key
    groups: dict[str, list[dict]] = defaultdict(list)

    for rec in records:
        rk = rec.get("recordKey", "")
        if not rk:
            continue

        # Priority 1: Outlook ConversationID
        conv_id = rec.get("identity", {}).get("conversationId", "")
        if conv_id:
            ck = _make_conversation_key_from_conv_id(conv_id)
            groups[ck].append(rec)
            continue

        # Priority 2: InternetMessageId / InReplyTo / References
        # (simplified: use conversationTopic if available)
        conv_topic = rec.get("identity", {}).get("conversationTopic", "")
        if conv_topic:
            ck = sha256_text(f"topic:{conv_topic}")
            groups[ck].append(rec)
            continue

        # Priority 3: Normalised subject + participant hash
        subj = _normalise_subject(rec.get("headers", {}).get("subject", ""))
        part_h = _hash_participants(rec)
        ck = _make_conversation_key_from_fallback(subj, part_h)
        groups[ck].append(rec)

    # Build conversation records
    conv_dir = os.path.join(resolved, "conversations")
    conv_list: list[dict] = []
    manifest = {
        "conversationsFound": 0,
        "recordsGrouped": 0,
        "recordsOrphaned": 0,
        "mailboxWrites": 0,
        "kanbanWrites": 0,
        "cloudApiCalls": 0,
        "rawSourcesRetained": 0,
    }

    for ck, recs in groups.items():
        # Sort by receivedDateTime
        recs.sort(key=lambda r: r.get("headers", {}).get("receivedDateTime", ""))
        subj_canon = _normalise_subject(recs[0].get("headers", {}).get("subject", ""))
        message_keys = [r.get("recordKey", "") for r in recs if r.get("recordKey")]
        part_hashes = list(set(_hash_participants(r) for r in recs))
        folder_keys = list(set(r.get("source", {}).get("folderKey", "") for r in recs if r.get("source", {}).get("folderKey")))
        att_count = sum(r.get("attachments", {}).get("count", 0) for r in recs)
        ext_count = sum(len(r.get("extracts", [])) for r in recs)

        first_dt = recs[0].get("headers", {}).get("receivedDateTime", "")
        last_dt = recs[-1].get("headers", {}).get("receivedDateTime", "")

        conv_rec = {
            "_schema": "export.conversation.v1",
            "conversationKey": ck,
            "exportRunId": export_run_id,
            "sourceScope": "primary_user_store_only",
            "createdAt": now_iso,
            "updatedAt": now_iso,
            "messageRecordKeys": message_keys,
            "subjectCanonical": subj_canon,
            "participantHashes": part_hashes,
            "folderKeys": folder_keys,
            "dateRange": {"first": first_dt, "last": last_dt},
            "messageCount": len(message_keys),
            "attachmentCount": att_count,
            "extractCount": ext_count,
            "retrievalChunkIds": [],
            "audit": {
                "mailboxWrite": False,
                "kanbanWrite": False,
                "cloudApiCalls": False,
                "rawSourceRetained": False,
            },
        }

        # Write per-conversation file
        dt_for_path = first_dt or now_iso
        cy, cm = dt_for_path[:4], dt_for_path[5:7] if len(dt_for_path) >= 7 else ("unknown", "unknown")
        cdir = os.path.join(conv_dir, cy, cm)
        os.makedirs(cdir, exist_ok=True)
        cpath = os.path.join(cdir, f"conversation_{ck}.json")
        with open(cpath, "w", encoding="utf-8") as f:
            json.dump(conv_rec, f, indent=2, ensure_ascii=False)

        conv_list.append(conv_rec)
        manifest["conversationsFound"] += 1
        manifest["recordsGrouped"] += len(message_keys)

    # Write conversations_latest.jsonl
    jsonl_path = os.path.join(conv_dir, "conversations_latest.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for cv in conv_list:
            f.write(json.dumps(cv, ensure_ascii=False) + "\n")

    manifest["recordsOrphaned"] = 0
    return manifest
