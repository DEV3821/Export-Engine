"""Mr Kanban guided card evidence session — evidence-bound, no LLM, no write-back.

Produces a structured guided session object that accepts a Kanban card
context, retrieves evidence from the Local Knowledge Store via the bridge
layer, and optionally produces a conservative draft human-review note.

No LLM, no Hermes, no Outlook COM at query time, no Kanban write,
no mailbox write, no answer generation.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from .bridge import run_bridge_retrieval
from .hashing import sha256_text


def run_guided_card_evidence_session(
    card_context: dict[str, Any],
    question: str | None = None,
    store_root: str | None = None,
    limit: int = 10,
    include_text: bool = False,
    max_chunk_chars: int = 1200,
    create_draft_review: bool = False,
) -> dict[str, Any]:
    """Run a guided card evidence session.

    Accepts a card context dict and optional question, retrieves evidence
    via the bridge layer, and returns a structured session object.

    If *create_draft_review* is True, a conservative deterministic draft
    review note is included.  No LLM, no Hermes, no Outlook COM at
    query time, no Kanban write, no mailbox write.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    session_id = sha256_text(f"guided:{now_iso}:{uuid.uuid4().hex}")

    # Call the bridge retrieval layer
    pack = run_bridge_retrieval(
        card_context=card_context,
        question=question,
        query_text=None,
        store_root=store_root,
        caller="guided_session",
        limit=limit,
        include_chunk_text=include_text,
        max_chunk_chars=max_chunk_chars,
    )

    # Build evidence items (preserve pointers)
    evidence_items: list[dict[str, Any]] = []
    for ei in pack.get("evidenceItems", []):
        item = {
            "rank": ei.get("rank", 0),
            "score": ei.get("score", 0.0),
            "title": ei.get("title", ""),
            "date": ei.get("date", ""),
            "folderPath": ei.get("folderPath", ""),
            "sourceKind": ei.get("sourceKind", ""),
            "chunkKey": ei.get("chunkKey", ""),
            "recordKey": ei.get("recordKey", ""),
            "extractKey": ei.get("extractKey"),
            "conversationKey": ei.get("conversationKey"),
            "textPreview": ei.get("textPreview", ""),
            "textHash": ei.get("textHash", ""),
        }
        evidence_items.append(item)

    evidence_count = len(evidence_items)

    # Identify gaps
    gaps: list[str] = []
    if evidence_count == 0:
        gaps.append("No local evidence found for this card context and question.")
    else:
        if evidence_count < 3:
            gaps.append(f"Only {evidence_count} evidence items — may be insufficient for full review.")
        # Check if any evidence has a recordKey (message-level evidence)
        has_message_evidence = any(
            ei.get("recordKey") for ei in evidence_items
        )
        if not has_message_evidence:
            gaps.append("No direct message-level evidence — only conversation or chunk-level references.")

    # Build query text from the pack
    query_text = pack.get("queryText", "")

    # Build card context from supplied data (only store what was provided)
    safe_card_ctx: dict[str, Any] = {}
    for key in (
        "cardId", "cardTitle", "cardStatus", "cardRisk", "cardLead",
        "cardOwner", "currentState", "nextAction", "lastUpdated", "sourceCardHash",
    ):
        val = card_context.get(key)
        if val is not None:
            safe_card_ctx[key] = val

    # Build the guided session object
    session: dict[str, Any] = {
        "_schema": "export.guidedCardEvidenceSession.v1",
        "sessionId": session_id,
        "createdAt": now_iso,
        "mode": "card_evidence_session",
        "cardContext": safe_card_ctx,
        "question": question or "",
        "bridgeRequestId": pack.get("bridgeRequestId", ""),
        "queryText": query_text,
        "evidencePack": pack,
        "evidenceCount": evidence_count,
        "evidenceItems": evidence_items,
        "gaps": gaps,
        "draftReview": {},
        "allowedNextActions": [
            "copyEvidenceSummary",
            "refineQuestion",
            "inspectEvidence",
            "createDraftKanbanUpdate",
        ],
        "blockedActions": [
            "writeKanban",
            "writeMailbox",
            "callCloudApi",
            "callOutlookAtQueryTime",
        ],
        "audit": {
            "mailboxWrites": 0,
            "kanbanWrites": 0,
            "cloudApiCalls": 0,
            "outlookComUsedAtQueryTime": False,
            "rawSourcesRetained": 0,
            "automaticWriteBack": False,
        },
    }

    # Optional deterministic draft review
    if create_draft_review:
        session["draftReview"] = _build_draft_review(
            card_context=safe_card_ctx,
            evidence_items=evidence_items,
            evidence_count=evidence_count,
            gaps=gaps,
            question=question or "",
            bridge_request_id=pack.get("bridgeRequestId", ""),
        )

    return session


def _build_draft_review(
    card_context: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    evidence_count: int,
    gaps: list[str],
    question: str,
    bridge_request_id: str,
) -> dict[str, Any]:
    """Build a conservative, deterministic draft review note.

    Rules:
    - No invented claims — every bullet maps to evidence.
    - If evidenceCount is 0, draft says no local evidence found.
    - readyForApply must remain False.
    - requiresHumanReview must be True.
    - Cites chunk keys, record keys, extract keys, conversation keys.
    """
    # Collect evidence pointers
    cited_chunk_keys: list[str] = []
    cited_record_keys: list[str] = []
    cited_extract_keys: list[str] = []
    cited_conversation_keys: list[str] = []

    for ei in evidence_items:
        ck = ei.get("chunkKey", "")
        if ck and ck not in cited_chunk_keys:
            cited_chunk_keys.append(ck)
        rk = ei.get("recordKey", "")
        if rk and rk not in cited_record_keys:
            cited_record_keys.append(rk)
        ek = ei.get("extractKey")
        if ek and ek not in cited_extract_keys:
            cited_extract_keys.append(ek)
        cvk = ei.get("conversationKey")
        if cvk and cvk not in cited_conversation_keys:
            cited_conversation_keys.append(cvk)

    # Build the text deterministically
    parts: list[str] = []
    parts.append("Draft review — requires human verification before use.")
    parts.append("")

    card_title = (card_context.get("cardTitle") or "").strip() or "untitled card"
    parts.append(f"Card: {card_title}")

    if question:
        parts.append(f"Review question: {question}")
    parts.append("")

    if evidence_count == 0:
        parts.append("Evidence found: None")
        parts.append("No local email evidence was found for this card.")
        parts.append("The card may need additional search terms, or the evidence")
        parts.append("may not exist in the current Local Knowledge Store.")
    else:
        parts.append(f"Evidence found: {evidence_count} item(s)")
        parts.append("")
        for ei in evidence_items:
            title = ei.get("title", "(no title)").strip()
            score = ei.get("score", 0.0)
            dt = ei.get("date", "")
            fp = ei.get("folderPath", "")
            ck = ei.get("chunkKey", "")[:16] + "..."
            parts.append(f"- {title}")
            parts.append(f"  Score: {score}  Date: {dt}  Folder: {fp}")
            parts.append(f"  Chunk: {ck}")
            record_key = ei.get("recordKey", "")
            if record_key:
                parts.append(f"  Record: {record_key[:16]}...")
            conv_key = ei.get("conversationKey")
            if conv_key:
                parts.append(f"  Conversation: {conv_key[:16]}...")

    if gaps:
        parts.append("")
        parts.append("Gaps / needs human check:")
        for g in gaps:
            parts.append(f"- {g}")

    parts.append("")
    parts.append("This draft was generated deterministically from local evidence.")
    parts.append("No LLM, no Hermes, no Outlook COM at query time.")

    text = "\n".join(parts)

    draft: dict[str, Any] = {
        "_schema": "export.draftKanbanReviewNote.v1",
        "draftId": sha256_text(f"draft:{bridge_request_id}:{datetime.now(timezone.utc).isoformat()}"),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "sourceSessionId": bridge_request_id,
        "cardId": card_context.get("cardId", ""),
        "cardTitle": card_title,
        "sourceCardHash": card_context.get("sourceCardHash", ""),
        "evidenceBound": True,
        "text": text,
        "citedChunkKeys": cited_chunk_keys,
        "citedRecordKeys": cited_record_keys,
        "citedExtractKeys": cited_extract_keys,
        "citedConversationKeys": cited_conversation_keys,
        "warnings": ["Draft — requires human review before applying."],
        "requiresHumanReview": True,
        "readyForApply": False,
        "audit": {
            "kanbanWrites": 0,
            "mailboxWrites": 0,
            "cloudApiCalls": 0,
            "automaticWriteBack": False,
        },
    }

    return draft
