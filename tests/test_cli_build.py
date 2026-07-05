"""Tests for CLI build commands — store-build-conversations, store-build-retrieval, store-build-index, store-search."""

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


class TestCLIBuildCommands:
    """Build commands appear in help and produce output."""

    def test_help_contains_commands(self) -> None:
        help_text = build_parser().format_help()
        assert "store-build-conversations" in help_text
        assert "store-build-retrieval" in help_text
        assert "store-build-index" in help_text
        assert "store-search" in help_text

    def test_no_banned_branding(self) -> None:
        help_text = build_parser().format_help()
        for phrase in BANNED:
            assert phrase.lower() not in help_text.lower(), f"Banned: {phrase}"

    def test_build_conversations_help(self) -> None:
        code, output = _run(["store-build-conversations", "--help"])
        assert code == 0

    def test_build_retrieval_help(self) -> None:
        code, output = _run(["store-build-retrieval", "--help"])
        assert code == 0

    def test_build_index_help(self) -> None:
        code, output = _run(["store-build-index", "--help"])
        assert code == 0

    def test_search_help(self) -> None:
        code, output = _run(["store-search", "--help"])
        assert code == 0
