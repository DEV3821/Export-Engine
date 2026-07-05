"""Tests for cli.py — store-source-scan CLI behaviour."""

import sys

from export_engine.cli import main, build_parser, outlook_available


def _capture_output(args: list[str]) -> tuple[int, str]:
    """Run CLI with args, return (exit_code, output_text)."""
    from io import StringIO
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


class TestCLISourceScan:
    """store-source-scan CLI behaviour."""

    def test_source_scan_help(self) -> None:
        parser = build_parser()
        help_text = parser.format_help()
        assert "store-source-scan" in help_text

    def test_source_scan_help_detail(self) -> None:
        code, output = _capture_output(["store-source-scan", "--help"])
        assert code == 0

    def test_fixture_scan_writes_output(self) -> None:
        """Fixture-based scan should produce clean output."""
        code, output = _capture_output(["store-source-scan", "--all-user-folders", "--fixture"])
        assert code == 0
        assert "Local Knowledge Store source scan" in output
        assert "Source adapter: Outlook COM" in output
        assert "Folders seen:" in output
        assert "Folders included:" in output
        assert "Folders excluded:" in output
        assert "Excluded stores:" in output

    def test_fixture_scan_no_banned_phrases(self) -> None:
        BANNED = [
            "Phase 8A", "Mr Kanban", "Hermes cache", "chatbot memory",
            "Kanban brain", "EmailBrain", "email dump", "mailbox scrape",
            "raw mailbox export",
        ]
        code, output = _capture_output(["store-source-scan", "--all-user-folders", "--fixture"])
        for phrase in BANNED:
            assert phrase.lower() not in output.lower(), f"Banned phrase: {phrase}"

    def test_live_scan_without_outlook_returns_error(self) -> None:
        """If Outlook is unavailable, live scan should give clear error."""
        if outlook_available():
            return  # Can't test if Outlook IS available

        code, output = _capture_output(["store-source-scan", "--all-user-folders"])
        assert code == 1
        assert "Outlook COM unavailable" in output

    def test_source_scan_output_contains_required_lines(self) -> None:
        code, output = _capture_output(["store-source-scan", "--all-user-folders", "--fixture"])
        assert "Mailbox write: disabled" in output
        assert "Kanban write: disabled" in output
        assert "Cloud/API calls: disabled" in output
        assert "Raw source retention: disabled" in output
