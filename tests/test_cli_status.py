"""Tests for cli.py — CLI status output and banned brand checks."""

import sys

from export_engine.cli import main, build_parser

# Banned phrases that must NOT appear in status output
BANNED_PHRASES = [
    "Phase 8A",
    "Mr Kanban",
    "Hermes cache",
    "chatbot memory",
    "Kanban brain",
    "EmailBrain",
    "email dump",
    "mailbox scrape",
    "raw mailbox export",
]


class TestCLIStatusOutput:
    """store-status output must be neutral and not contain banned branding."""

    def test_store_status_help(self) -> None:
        """Check store-status is listed in help."""
        parser = build_parser()
        help_text = parser.format_help()
        assert "store-status" in help_text
        assert "store-verify" in help_text

    def test_store_status_output_no_banned_phrases(self) -> None:
        """Cature store-status output and check for banned phrases."""
        from io import StringIO

        old_stdout = sys.stdout
        captured = StringIO()
        sys.stdout = captured
        try:
            exit_code = main(["store-status"])
        finally:
            sys.stdout = old_stdout

        assert exit_code == 0
        output = captured.getvalue()

        # Check for neutral wording
        assert "Local Knowledge Store" in output
        assert "Outlook COM" in output
        assert "hashed JSON records" in output

        # Check no banned phrases
        for phrase in BANNED_PHRASES:
            assert phrase.lower() not in output.lower(), (
                f"Banned phrase found in status output: {phrase!r}"
            )

    def test_store_status_contains_required_lines(self) -> None:
        from io import StringIO

        old_stdout = sys.stdout
        captured = StringIO()
        sys.stdout = captured
        try:
            main(["store-status"])
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        # Required lines from spec
        assert "Source adapter: Outlook COM" in output
        assert "Scope: primary user store only" in output
        assert "Persistent format: hashed JSON records" in output
        assert "Mailbox write: disabled" in output
        assert "Kanban write: disabled" in output
        assert "Cloud/API calls: disabled" in output
        assert "Raw source retention: disabled" in output
        assert "Vault projection: enabled" in output
        assert "Canvas projection: enabled" in output

    def test_store_verify_help(self) -> None:
        parser = build_parser()
        help_text = parser.format_help()
        assert "store-verify" in help_text


class TestStubCommands:
    """Stub commands must be listed in help and return cleanly."""

    STUB_COMMANDS = [
        "store-refresh",
        "store-watch",
        "store-search",
        "store-rebuild-index",
        "store-build-vault",
        "store-refresh-vault",
        "store-build-canvas",
        "store-refresh-canvas",
        "store-protect",
        "store-verify-protection",
    ]

    def test_stub_commands_in_help(self) -> None:
        parser = build_parser()
        help_text = parser.format_help()
        for cmd in self.STUB_COMMANDS:
            assert cmd in help_text, f"Stub command {cmd} not in help"

    def test_stub_commands_return_not_implemented(self) -> None:
        for cmd in self.STUB_COMMANDS:
            from io import StringIO

            old_stdout = sys.stdout
            captured = StringIO()
            sys.stdout = captured
            try:
                exit_code = main([cmd])
            finally:
                sys.stdout = old_stdout

            assert exit_code == 0, f"Command {cmd} returned non-zero"
            output = captured.getvalue()
            assert "not implemented in this phase" in output, (
                f"Command {cmd} missing Phase 1.1 message"
            )
