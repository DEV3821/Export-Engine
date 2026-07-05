"""Tests for CLI query command — store-query."""

from export_engine.cli import main, build_parser

BANNED = [
    "Phase 8A", "Mr Kanban", "Hermes cache", "chatbot memory",
    "Kanban brain", "EmailBrain", "email dump", "mailbox scrape",
    "raw mailbox export",
]


def _run(args: list[str]) -> tuple[int, str]:
    from io import StringIO
    import sys
    old = sys.stdout
    captured = StringIO()
    sys.stdout = captured
    try:
        code = main(args)
    except SystemExit as e:
        code = e.code if e.code is not None else 0
    finally:
        sys.stdout = old
    return code, captured.getvalue()


class TestCLIQuery:
    def test_query_in_help(self) -> None:
        assert "store-query" in build_parser().format_help()

    def test_query_help(self) -> None:
        code, _ = _run(["store-query", "--help"])
        assert code == 0

    def test_no_banned_branding(self) -> None:
        help_text = build_parser().format_help()
        for phrase in BANNED:
            assert phrase.lower() not in help_text.lower(), f"Banned: {phrase}"

    def test_missing_index_gives_warning(self) -> None:
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(os.path.join(store_root, "index"), exist_ok=True)
            code, output = _run([
                "store-query", "--query", "test", "--store-root", store_root,
            ])
            assert code == 0
            assert "index not found" in output or "Warning" in output or "No matching" in output
