"""Tests for conversations.py — conversation builder."""

import json
import os
import tempfile

from export_engine.conversations import build_conversations, _normalise_subject


def _setup_records(store_root: str) -> None:
    """Create synthetic records for conversation testing."""
    from export_engine.source_scan import run_source_scan
    from export_engine.planning import create_backfill_plan
    from export_engine.ingest import run_ingest
    run_source_scan(store_root, use_fixture=True)
    create_backfill_plan(store_root, use_fixture=True, since="2025-07-05", until="2025-08-05")
    run_ingest(store_root, use_fixture=True, limit=10, resume=True)


class TestNormaliseSubject:
    def test_strips_re(self) -> None:
        assert _normalise_subject("RE: Project update") == "Project update"

    def test_strips_fw(self) -> None:
        assert _normalise_subject("FW: Meeting notes") == "Meeting notes"

    def test_strips_fwd(self) -> None:
        assert _normalise_subject("Fwd: Hello") == "Hello"

    def test_case_insensitive(self) -> None:
        assert _normalise_subject("re: test") == "test"


class TestBuildConversations:
    def test_conversations_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_records(store_root)
            manifest = build_conversations(store_root, export_run_id="test1")
            assert manifest["conversationsFound"] > 0
            assert manifest["recordsGrouped"] > 0

    def test_writes_conversation_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_records(store_root)
            build_conversations(store_root, export_run_id="test1")
            conv_dir = os.path.join(store_root, "conversations")
            count = 0
            for root, dirs, files in os.walk(conv_dir):
                count += len([f for f in files if f.startswith("conversation_") and f.endswith(".json")])
            assert count > 0, "No conversation files written"

    def test_writes_conversations_latest_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_records(store_root)
            build_conversations(store_root, export_run_id="test1")
            jsonl_path = os.path.join(store_root, "conversations", "conversations_latest.jsonl")
            assert os.path.isfile(jsonl_path)
            with open(jsonl_path) as f:
                lines = [l for l in f if l.strip()]
            assert len(lines) > 0

    def test_message_counts_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_records(store_root)
            build_conversations(store_root, export_run_id="test1")
            conv_dir = os.path.join(store_root, "conversations")
            for root, dirs, files in os.walk(conv_dir):
                for fn in files:
                    if fn.endswith(".json") and fn.startswith("conversation_"):
                        with open(os.path.join(root, fn)) as f:
                            cv = json.load(f)
                        assert cv["messageCount"] == len(cv["messageRecordKeys"])

    def test_safety_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            _setup_records(store_root)
            manifest = build_conversations(store_root, export_run_id="test1")
            assert manifest["mailboxWrites"] == 0
            assert manifest["kanbanWrites"] == 0
            assert manifest["cloudApiCalls"] == 0
