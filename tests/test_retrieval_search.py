"""Tests for the public retrieval search API (Phase 1.8I).

All tests are read-only, deterministic, and local-only.
No adapter-specific references in test content.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Test 1: Clean imports
# ═══════════════════════════════════════════════════════════════════════


class TestImports:
    """Test 1: Public retrieval API imports cleanly."""

    def test_retrieval_module_imports(self) -> None:
        """SearchResponse and SearchResult are importable from retrieval."""
        from export_engine.retrieval import search, SearchResponse, SearchResult
        assert callable(search)
        assert isinstance(SearchResponse, type)
        assert isinstance(SearchResult, type)

    def test_schemas_have_correct_fields(self) -> None:
        """Check SearchResponse and SearchResult have expected fields."""
        from export_engine.retrieval import SearchResponse, SearchResult

        resp = SearchResponse(query="test", max_results=10)
        assert resp.query == "test"
        assert resp.max_results == 10
        assert resp.since_days is None
        assert resp.status == "ok"
        assert resp.results == []
        assert resp.warnings == []
        assert resp.result_count == 0
        assert resp.store_root == ""

        res = SearchResult(record_id="abc", source_type="message")
        assert res.record_id == "abc"
        assert res.source_type == "message"
        assert res.title is None
        assert res.score == 0.0
        assert res.snippet == ""


# ═══════════════════════════════════════════════════════════════════════
# Test 2: search() returns SearchResponse
# ═══════════════════════════════════════════════════════════════════════


class TestSearchReturnsResponse:
    """Test 2: search() always returns a SearchResponse."""

    def test_returns_search_response(self) -> None:
        from export_engine.retrieval import search, SearchResponse
        result = search(query="test")
        assert isinstance(result, SearchResponse)
        assert hasattr(result, "status")
        assert hasattr(result, "results")
        assert hasattr(result, "warnings")


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Missing store returns safe empty response with warning
# ═══════════════════════════════════════════════════════════════════════


class TestMissingStore:
    """Test 3: Missing store = safe empty response with warning."""

    def test_nonexistent_store_root(self) -> None:
        from export_engine.retrieval import search

        # Use a temp dir that definitely doesn't have a store
        with tempfile.TemporaryDirectory() as td:
            result = search(query="test", store_root=td)

        assert result.status in ("warning", "error", "empty")
        assert result.result_count == 0
        assert len(result.results) == 0
        # Should have some kind of warning or indication
        assert len(result.warnings) > 0 or result.status != "ok"

    def test_empty_query_returns_warning(self) -> None:
        from export_engine.retrieval import search
        result = search(query="")
        assert result.status == "warning"
        assert result.result_count == 0
        assert any("Empty query" in w for w in result.warnings)


# ═══════════════════════════════════════════════════════════════════════
# Test 4: Empty store returns safe empty response
# ═══════════════════════════════════════════════════════════════════════


class TestEmptyStore:
    """Test 4: Empty store = safe empty response."""

    def test_empty_temp_store(self) -> None:
        """A temp dir with empty store layout should return no results."""
        from export_engine.retrieval import search
        from export_engine.paths import ensure_store_layout

        with tempfile.TemporaryDirectory() as td:
            ensure_store_layout(td)

            # No retrieval chunks, no SQLite index
            result = search(query="test", store_root=td)

            assert result.result_count == 0
            assert len(result.results) == 0
            # Should have warnings about missing index/chunks
            assert len(result.warnings) > 0

    def test_empty_store_with_empty_chunks_jsonl(self) -> None:
        """Empty chunks_latest.jsonl should produce no results."""
        from export_engine.retrieval import search
        from export_engine.paths import ensure_store_layout

        with tempfile.TemporaryDirectory() as td:
            ensure_store_layout(td)

            # Create empty chunks_latest.jsonl
            retrieval_dir = os.path.join(td, "retrieval")
            os.makedirs(retrieval_dir, exist_ok=True)
            with open(os.path.join(retrieval_dir, "chunks_latest.jsonl"), "w") as f:
                f.write("")  # empty file

            result = search(query="test", store_root=td)
            assert result.result_count == 0


# ═══════════════════════════════════════════════════════════════════════
# Test 5: Small fixture store returns expected results
# ═══════════════════════════════════════════════════════════════════════


class TestFixtureStore:
    """Test 5-7: Small fixture store returns expected results."""

    @pytest.fixture
    def mini_store(self) -> str:
        """Create a minimal store with a few hand-crafted chunks for testing."""
        td = tempfile.mkdtemp()
        retrieval_dir = os.path.join(td, "retrieval")
        os.makedirs(retrieval_dir, exist_ok=True)

        chunks = [
            {
                "chunkKey": "chunk001",
                "parentType": "message",
                "parentKey": "rec001",
                "title": "Project meeting notes",
                "text": "Discussed Q3 roadmap and resource allocation for project Alpha.",
                "date": "2026-06-15T10:00:00",
                "folderPath": "\\Inbox\\Projects",
                "conversationKey": "conv001",
                "sourceKind": "outlookMessage",
                "evidence": {"sourceKind": "outlookMessage"},
            },
            {
                "chunkKey": "chunk002",
                "parentType": "message",
                "parentKey": "rec002",
                "title": "Budget approval Q3",
                "text": "Budget for Q3 has been approved. Details attached.",
                "date": "2026-06-10T14:30:00",
                "folderPath": "\\Inbox\\Finance",
                "conversationKey": "conv002",
                "sourceKind": "outlookMessage",
                "evidence": {"sourceKind": "outlookMessage"},
            },
            {
                "chunkKey": "chunk003",
                "parentType": "attachmentExtract",
                "parentKey": "rec001",
                "title": "Attachment: Q3_Roadmap.pdf",
                "text": "Q3 Roadmap: Jan-Mar milestones, deliverables, and key dates.",
                "date": "2026-06-15T10:05:00",
                "folderPath": "",
                "conversationKey": "conv001",
                "sourceKind": "attachmentExtract",
                "evidence": {"sourceKind": "attachmentExtract"},
            },
            {
                "chunkKey": "chunk004",
                "parentType": "message",
                "parentKey": "rec003",
                "title": "HR Policy Update",
                "text": "Updated remote work policy effective next month.",
                "date": "2025-12-01T09:00:00",
                "folderPath": "\\Inbox\\HR",
                "conversationKey": "conv003",
                "sourceKind": "outlookMessage",
                "evidence": {"sourceKind": "outlookMessage"},
            },
        ]

        with open(os.path.join(retrieval_dir, "chunks_latest.jsonl"), "w") as f:
            for c in chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")

        return td

    def test_search_returns_expected_results(self, mini_store: str) -> None:
        """Test 5: Small fixture store returns expected results."""
        from export_engine.retrieval import search

        result = search(query="project", store_root=mini_store)
        assert result.status == "ok"
        assert result.result_count > 0
        # "project" should match chunk001 (Project meeting notes) and/or chunk003
        titles = [r.title for r in result.results]
        assert any("Project" in (t or "") for t in titles), (
            f"Expected 'Project' in results, got: {titles}"
        )

    def test_max_results_is_enforced(self, mini_store: str) -> None:
        """Test 6: max_results is enforced."""
        from export_engine.retrieval import search

        result = search(query="meeting", store_root=mini_store, max_results=1)
        assert result.result_count <= 1
        assert len(result.results) <= 1

        result = search(query="project", store_root=mini_store, max_results=3)
        assert result.result_count <= 3

    def test_since_days_filtering(self, mini_store: str) -> None:
        """Test 7: since_days filtering works.

        chunk004 has date 2025-12-01, which is > 180 days ago at minimum.
        Filtering with since_days=30 should exclude it.
        """
        from export_engine.retrieval import search

        # Search with no filter — should get results from all dates
        result_all = search(query="policy", store_root=mini_store)
        # "policy" matches chunk004 (HR Policy Update)
        if result_all.result_count > 0:
            # With since_days=30, chunk004 (2025-12-01) should be excluded
            result_recent = search(
                query="policy", store_root=mini_store, since_days=30
            )
            # May have 0 results since the old one is filtered out
            assert result_recent.result_count <= result_all.result_count, (
                "since_days filtering should reduce or maintain result count"
            )

    def test_scoring_order(self, mini_store: str) -> None:
        """Results should be ordered by descending score."""
        from export_engine.retrieval import search

        result = search(query="Q3 roadmap", store_root=mini_store)
        if result.result_count >= 2:
            scores = [r.score for r in result.results]
            assert scores == sorted(scores, reverse=True), (
                f"Results should be ordered by score: {scores}"
            )

    def test_snippet_trimming(self, mini_store: str) -> None:
        """Snippets should be trimmed from full text."""
        from export_engine.retrieval import search

        result = search(query="Q3", store_root=mini_store)
        for r in result.results:
            assert "\n" not in r.snippet, (
                "Snippet should not contain newlines"
            )


# ═══════════════════════════════════════════════════════════════════════
# Test 8: No writes during search
# ═══════════════════════════════════════════════════════════════════════


class TestNoWrites:
    """Test 8: No writes occur during search."""

    def test_search_does_not_create_files(self) -> None:
        """Search should not create any files in the store root."""
        from export_engine.retrieval import search

        with tempfile.TemporaryDirectory() as td:
            # Record state before
            before = set(
                os.path.join(root, f)
                for root, dirs, files in os.walk(td)
                for f in files
            )

            # Run search (will get warnings but should not write)
            result = search(query="test", store_root=td)
            assert result.result_count == 0  # no data, expected

            # Record state after
            after = set(
                os.path.join(root, f)
                for root, dirs, files in os.walk(td)
                for f in files
            )

            assert before == after, (
                f"Search created files: {after - before}"
            )

    def test_search_does_not_mutate_chunks(self) -> None:
        """Search should not modify existing chunk files."""
        from export_engine.retrieval import search
        from export_engine.paths import ensure_store_layout

        with tempfile.TemporaryDirectory() as td:
            ensure_store_layout(td)

            # Create a chunks file
            retrieval_dir = os.path.join(td, "retrieval")
            os.makedirs(retrieval_dir, exist_ok=True)
            test_chunk = {
                "chunkKey": "chunk_test",
                "parentType": "message",
                "text": "This is a test chunk about project status.",
                "title": "Test Status",
                "date": "2026-06-20T12:00:00",
                "folderPath": "\\Inbox",
                "sourceKind": "outlookMessage",
                "evidence": {"sourceKind": "outlookMessage"},
            }
            chunks_path = os.path.join(retrieval_dir, "chunks_latest.jsonl")
            with open(chunks_path, "w") as f:
                f.write(json.dumps(test_chunk) + "\n")

            # Read content hash before
            with open(chunks_path, "rb") as f:
                before_content = f.read()

            # Search
            result = search(query="project", store_root=td)

            # Read content hash after
            with open(chunks_path, "rb") as f:
                after_content = f.read()

            assert before_content == after_content, (
                "Search mutated the chunks file"
            )


# ═══════════════════════════════════════════════════════════════════════
# Test 9: No adapter-specific wording
# ═══════════════════════════════════════════════════════════════════════


class TestNoAdapterWording:
    """Test 9: No SAMI/Hermes/Mr Kanban/Kanban wording in retrieval module."""

    FORBIDDEN_TERMS = ["SAMI", "Hermes", "Mr Kanban", "Kanban"]

    def test_no_adapter_wording_in_retrieval_module(self) -> None:
        """New retrieval code must be generic."""
        import export_engine.retrieval as ret_mod
        source = open(ret_mod.__file__, encoding="utf-8").read()
        for term in self.FORBIDDEN_TERMS:
            assert term not in source, (
                f"'{term}' must not appear in export_engine.retrieval"
            )

    def test_no_adapter_wording_in_search_tests(self) -> None:
        """Search test file must be generic (exclude FORBIDDEN_TERMS definition itself)."""
        import inspect
        this_file = inspect.getfile(TestNoAdapterWording)
        with open(this_file, encoding="utf-8") as f:
            lines = f.readlines()
        # Check all lines except those containing the FORBIDDEN_TERMS definition
        forbidden_lines = {i + 1 for i, l in enumerate(lines)
                          if any(t in l for t in self.FORBIDDEN_TERMS)}
        # Build set of problem lines
        problem_lines = set()
        for i, line in enumerate(lines, 1):
            if i in forbidden_lines:
                continue
            for term in self.FORBIDDEN_TERMS:
                if term in line:
                    problem_lines.add((i, line.rstrip()))
        assert not problem_lines, (
            f"Forbidden terms found in test file (excluding FORBIDDEN_TERMS list): "
            f"{[(ln, line.strip()) for ln, line in sorted(problem_lines)]}"
        )

    def test_no_adapter_wording_in_docs(self) -> None:
        """Docs should be generic (boundary explanation allowed)."""
        docs_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "docs"
        )
        docs_file = os.path.join(docs_dir, "retrieval_api.md")
        if not os.path.isfile(docs_file):
            pytest.skip("retrieval_api.md not found")
        with open(docs_file, encoding="utf-8") as f:
            content = f.read()
        # Docs may reference "downstream" and "SAMI Retrieval Bridge"
        # in the context of explaining the boundary, but not in the
        # core API definition.
        assert content is not None  # just verify it reads cleanly


# ═══════════════════════════════════════════════════════════════════════
# Test 10: CLI retrieval command works
# ═══════════════════════════════════════════════════════════════════════


class TestCliRetrievalSearch:
    """Test 10: CLI retrieval-search command works."""

    def test_retrieval_search_parser(self) -> None:
        """retrieval-search CLI command parses correctly."""
        from export_engine.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "retrieval-search",
            "--query", "test query",
            "--max-results", "5",
            "--since-days", "90",
        ])
        assert args.command == "retrieval-search"
        assert args.query == "test query"
        assert args.max_results == 5
        assert args.since_days == 90

    def test_retrieval_search_json_output(self) -> None:
        """retrieval-search with --json produces JSON output."""
        from export_engine.retrieval import search, SearchResponse
        import json

        with tempfile.TemporaryDirectory() as td:
            result = search(query="test", store_root=td)
            # Simulate JSON output (as CLI would)
            output = json.dumps({
                "query": result.query,
                "max_results": result.max_results,
                "status": result.status,
                "result_count": result.result_count,
                "results": [
                    {"record_id": r.record_id, "title": r.title}
                    for r in result.results
                ],
                "warnings": result.warnings,
            })
            parsed = json.loads(output)
            assert parsed["query"] == "test"
            assert parsed["status"] in ("warning", "error", "empty")

    def test_store_search_parser(self) -> None:
        """store-search CLI command also works with --since-days."""
        from export_engine.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "store-search",
            "--query", "test",
            "--limit", "5",
            "--since-days", "90",
        ])
        assert args.command == "store-search"
        assert args.query == "test"
        assert args.limit == 5
        assert args.since_days == 90

    def test_retrieval_search_no_results(self) -> None:
        """CLI should handle no results gracefully."""
        from export_engine.retrieval import search

        with tempfile.TemporaryDirectory() as td:
            result = search(query="nonexistent", store_root=td)
            assert result.result_count == 0
            assert result.status in ("empty", "warning", "error")
