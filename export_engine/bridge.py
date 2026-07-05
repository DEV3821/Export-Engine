"""Hermes/Mr Kanban retrieval bridge — deterministic evidence contract.

This module converts card context or free-form queries into structured
evidence packs from the Local Knowledge Store.  No LLM, no Outlook COM,
no Kanban write, no answer generation.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from .hashing import sha256_text
from .paths import get_store_root
from .query_adapter import run_local_query


def build_bridge_query_from_card(
    card_context: dict[str, Any],
    question: str | None = None,
) -> str:
    """Build a deterministic query string from card context fields.

    Combines non-empty card fields (title, currentState, nextAction,
    lead/owner, risk) with an optional question.
    """
    parts: list[str] = []

    title = (card_context.get("cardTitle") or "").strip()
    if title:
        parts.append(title)

    state = (card_context.get("currentState") or "").strip()
    if state:
        parts.append(state)

    action = (card_context.get("nextAction") or "").strip()
    if action:
        parts.append(action)

    lead = (card_context.get("cardLead") or "").strip()
    if lead:
        parts.append(lead)

    owner = (card_context.get("cardOwner") or "").strip()
    if owner:
        parts.append(owner)

    risk = (card_context.get("cardRisk") or "").strip()
    if risk:
        parts.append(risk)

    status = (card_context.get("cardStatus") or "").strip()
    if status:
        parts.append(status)

    if question:
        parts.append(question)

    return " ".join(parts)


def run_bridge_retrieval(
    card_context: dict[str, Any] | None = None,
    question: str | None = None,
    query_text: str | None = None,
    store_root: str | None = None,
    caller: str = "cli",
    mode: str | None = None,
    limit: int = 10,
    include_chunk_text: bool = False,
    max_chunk_chars: int = 1200,
    min_score: float = 0.0,
) -> dict[str, Any]:
    """Run a bridge retrieval and return a structured evidence pack.

    No answer generation.  No LLM.  No Outlook COM.  No Kanban write.
    """
    resolved = get_store_root(store_root)
    now_iso = datetime.now(timezone.utc).isoformat()
    bridge_id = sha256_text(f"bridge:{now_iso}:{uuid.uuid4().hex}")

    # Determine mode and build query
    actual_mode = mode or "free_query"
    if card_context and question:
        actual_mode = "card_plus_question"
    elif card_context:
        actual_mode = "card_context"
    elif query_text:
        actual_mode = "free_query"

    # Build query text
    if query_text:
        actual_query = query_text
    elif card_context:
        actual_query = build_bridge_query_from_card(card_context, question)
    else:
        actual_query = question or ""

    # Call local query adapter
    query_result = run_local_query(
        actual_query,
        resolved,
        limit=limit * 2,  # fetch extra for dedupe
        include_chunk_text=include_chunk_text,
        max_chunk_chars=max_chunk_chars,
        min_score=min_score,
    )

    # Build evidence items
    evidence_items: list[dict[str, Any]] = []
    for r in query_result.get("results", [])[:limit]:
        item = {
            "rank": r.get("rank", 0),
            "score": r.get("score", 0.0),
            "title": r.get("title", ""),
            "date": r.get("date", ""),
            "folderPath": r.get("folderPath", ""),
            "sourceKind": r.get("sourceKind", ""),
            "chunkKey": r.get("chunkKey", ""),
            "recordKey": r.get("evidence", {}).get("recordKey", ""),
            "extractKey": r.get("evidence", {}).get("extractKey"),
            "conversationKey": r.get("evidence", {}).get("conversationKey"),
            "textPreview": r.get("textPreview", ""),
            "textHash": r.get("textHash", ""),
        }
        evidence_items.append(item)

    pack: dict[str, Any] = {
        "_schema": "export.bridgeEvidencePack.v1",
        "bridgeRequestId": bridge_id,
        "createdAt": now_iso,
        "caller": caller,
        "mode": actual_mode,
        "queryText": actual_query,
        "cardContext": card_context or {},
        "queryResult": {
            "resultCount": query_result.get("resultCount", 0),
            "evidenceCount": query_result.get("evidenceCount", 0),
        },
        "evidenceItems": evidence_items,
        "evidenceCount": len(evidence_items),
        "warnings": query_result.get("warnings", []),
        "errors": query_result.get("errors", []),
        "recommendedNextStep": {
            "canAnswerLater": True,
            "reason": "Answer generation not implemented in this phase",
            "requiredHumanCheck": True,
        },
        "audit": {
            "mailboxWrites": 0,
            "kanbanWrites": 0,
            "cloudApiCalls": 0,
            "outlookComUsed": False,
            "llmUsed": False,
            "answerGenerated": False,
            "rawSourcesRetained": 0,
        },
    }

    return pack
