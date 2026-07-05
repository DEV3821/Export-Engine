"""Tests for Phase 1.8G — Engine Exporter rebrand and live runner scripts."""

import os
import sys

from export_engine.cli import main, build_parser


BANNED_BRANDING = [
    "Mr Kanban",
    "Hermes",
    "chatbot",
    "assistant",
    "coach",
    "evidence session",
]


def _run(args: list[str]) -> tuple[int, str]:
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


class TestRebrandHelpText:
    """CLI help text must use Engine Exporter wording."""

    def test_parser_description_engine_exporter(self) -> None:
        """Top-level description must say Engine Exporter."""
        help_text = build_parser().format_help()
        assert "Engine Exporter" in help_text

    def test_no_mr_kanban_in_help(self) -> None:
        """Help text must not contain Mr Kanban."""
        help_text = build_parser().format_help()
        assert "Mr Kanban" not in help_text

    def test_no_hermes_in_help(self) -> None:
        """Help text must not contain Hermes."""
        help_text = build_parser().format_help()
        assert "Hermes" not in help_text

    def test_no_kanban_brain_in_help(self) -> None:
        """Help text must not contain Kanban brain."""
        help_text = build_parser().format_help()
        assert "Kanban brain" not in help_text.lower()

    def test_store_query_help_no_hermes(self) -> None:
        """store-query help must not reference Hermes."""
        from io import StringIO
        old = sys.stdout
        captured = StringIO()
        sys.stdout = captured
        try:
            main(["store-query", "--help"])
        except SystemExit:
            pass
        finally:
            sys.stdout = old
        output = captured.getvalue()
        assert "no Hermes" not in output
        assert "Hermes" not in output

    def test_store_bridge_query_help_no_hermes(self) -> None:
        """store-bridge-query help must not reference Hermes."""
        from io import StringIO
        old = sys.stdout
        captured = StringIO()
        sys.stdout = captured
        try:
            main(["store-bridge-query", "--help"])
        except SystemExit:
            pass
        finally:
            sys.stdout = old
        output = captured.getvalue()
        assert "Hermes" not in output


class TestRebrandStatusOutput:
    """store-status output must be Engine Exporter branded."""

    def test_status_engine_exporter_header(self) -> None:
        """store-status output should mention Engine Exporter or Local Knowledge Store."""
        code, output = _run(["store-status"])
        assert code == 0
        assert "Engine Exporter" in output or "Local Knowledge Store" in output

    def test_status_no_banned_branding(self) -> None:
        """store-status output must not contain banned branding."""
        code, output = _run(["store-status"])
        for phrase in BANNED_BRANDING:
            assert phrase.lower() not in output.lower(), (
                f"Banned phrase found: {phrase!r}"
            )

    def test_status_safety_flags_present(self) -> None:
        """store-status must show safety flags."""
        code, output = _run(["store-status"])
        assert "Mailbox write: disabled" in output
        assert "Kanban write: disabled" in output
        assert "Cloud/API calls: disabled" in output
        assert "Raw source retention: disabled" in output
        assert "Outlook COM" in output


class TestRebrandLiveStatus:
    """store-live-status output must show enhanced safety flags."""

    def test_live_status_header(self) -> None:
        """store-live-status must show Engine Exporter heading."""
        code, output = _run(["store-live-status"])
        assert "Engine Exporter" in output

    def test_live_status_safety_flags(self) -> None:
        """store-live-status must show all required safety flags."""
        code, output = _run(["store-live-status"])
        assert "Mailbox writes:" in output
        assert "Kanban writes:" in output
        assert "Cloud/API calls:" in output
        assert "LLM used:" in output or "LLM" not in output
        assert "Raw .msg/.eml retention:" in output

    def test_live_status_no_banned_branding(self) -> None:
        """store-live-status must not contain banned branding."""
        code, output = _run(["store-live-status"])
        for phrase in BANNED_BRANDING:
            assert phrase.lower() not in output.lower(), (
                f"Banned phrase found: {phrase!r}"
            )


class TestRebrandLiveEnable:
    """store-live-enable output must use Engine Exporter header."""

    def test_live_enable_header(self) -> None:
        """store-live-enable help must show Engine Exporter."""
        from io import StringIO
        old = sys.stdout
        captured = StringIO()
        sys.stdout = captured
        try:
            main(["store-live-enable", "--help"])
        except SystemExit:
            pass
        finally:
            sys.stdout = old
        output = captured.getvalue()
        assert "store-live-enable" in output


class TestRunnerScriptsExist:
    """Runner scripts must exist and contain expected calls."""

    def test_powershell_script_exists(self) -> None:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        ps_path = os.path.join(repo_root, "scripts", "start_live_export.ps1")
        assert os.path.isfile(ps_path), f"PowerShell script not found: {ps_path}"

    def test_bat_script_exists(self) -> None:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        bat_path = os.path.join(repo_root, "scripts", "start_live_export.bat")
        assert os.path.isfile(bat_path), f"BAT script not found: {bat_path}"

    def test_powershell_contains_cli_calls(self) -> None:
        """PowerShell script must call store-live-status and store-live-refresh-once."""
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        ps_path = os.path.join(repo_root, "scripts", "start_live_export.ps1")
        with open(ps_path, encoding="utf-8") as f:
            content = f.read()
        assert "store-live-status" in content
        assert "store-live-refresh-once" in content
        assert "store-live-enable" in content

    def test_bat_calls_powershell(self) -> None:
        """BAT wrapper must call the PowerShell script."""
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        bat_path = os.path.join(repo_root, "scripts", "start_live_export.bat")
        with open(bat_path, encoding="utf-8") as f:
            content = f.read()
        assert "start_live_export.ps1" in content


class TestOperatorDoc:
    """Operator documentation must exist and contain safety warnings."""

    def test_operator_doc_exists(self) -> None:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        doc_path = os.path.join(repo_root, "docs", "operator_live_export.md")
        assert os.path.isfile(doc_path), f"Operator doc not found: {doc_path}"

    def test_operator_doc_safety_warnings(self) -> None:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        doc_path = os.path.join(repo_root, "docs", "operator_live_export.md")
        with open(doc_path, encoding="utf-8") as f:
            content = f.read()
        assert "Mailbox writes" in content
        assert "Kanban writes" in content
        assert "Cloud/API" in content
        assert "LLM" in content
        assert "retention" in content
        assert "read-only" in content

    def test_operator_doc_authorised_mailbox_wording(self) -> None:
        """Operator doc must contain authorised mailbox warning."""
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        doc_path = os.path.join(repo_root, "docs", "operator_live_export.md")
        with open(doc_path, encoding="utf-8") as f:
            content = f.read()
        assert "authorisation" in content.lower() or "Authorisation" in content
        assert "other" in content.lower()
        assert "mailbox" in content.lower()

    def test_operator_doc_engine_exporter_branded(self) -> None:
        """Operator doc must use Engine Exporter branding."""
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        doc_path = os.path.join(repo_root, "docs", "operator_live_export.md")
        with open(doc_path, encoding="utf-8") as f:
            content = f.read()
        assert "Engine Exporter" in content
        assert "Mr Kanban" not in content
        assert "Hermes" not in content
