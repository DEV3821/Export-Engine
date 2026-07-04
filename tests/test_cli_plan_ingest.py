"""Tests for cli.py — store-plan-ingest CLI behaviour."""

from export_engine.cli import main, build_parser

BANNED_PHRASES = [
    "Phase 8A", "Mr Kanban", "Hermes cache", "chatbot memory",
    "Kanban brain", "EmailBrain", "email dump", "mailbox scrape",
    "raw mailbox export",
]


def _capture_output(args: list[str]) -> tuple[int, str]:
    """Run CLI with args, return (exit_code, output_text)."""
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


class TestCLIPlanIngest:
    """store-plan-ingest CLI behaviour."""

    def test_plan_ingest_help(self) -> None:
        parser = build_parser()
        help_text = parser.format_help()
        assert "store-plan-ingest" in help_text

    def test_plan_ingest_help_detail(self) -> None:
        code, output = _capture_output(["store-plan-ingest", "--help"])
        assert code == 0

    def test_fixture_plan_output(self) -> None:
        code, output = _capture_output([
            "store-plan-ingest",
            "--all-user-folders",
            "--since", "2025-07-05",
            "--until", "2026-07-05",
            "--fixture",
        ])
        assert code == 0
        assert "Local Knowledge Store historic backfill plan" in output
        assert "Backfill chunks: monthly" in output
        assert "Backfill chunk purpose: historic_backfill" in output
        assert "Near-live refresh after backfill: polling" in output
        assert "Default polling interval: 5 minutes" in output
        assert "Minimum polling interval: 1 minute" in output
        assert "Mailbox write: disabled" in output
        assert "Kanban write: disabled" in output
        assert "Cloud/API calls: disabled" in output
        assert "Raw source retention: disabled" in output

    def test_fixture_plan_shows_fixture_mode(self) -> None:
        code, output = _capture_output([
            "store-plan-ingest",
            "--all-user-folders",
            "--since", "2025-07-05",
            "--until", "2026-07-05",
            "--fixture",
        ])
        assert "Fixture mode: enabled" in output

    def test_no_banned_branding(self) -> None:
        code, output = _capture_output([
            "store-plan-ingest",
            "--all-user-folders",
            "--since", "2025-07-05",
            "--until", "2026-07-05",
            "--fixture",
        ])
        for phrase in BANNED_PHRASES:
            assert phrase.lower() not in output.lower(), f"Banned: {phrase}"

    def test_no_monthly_ingest_wording(self) -> None:
        """Must not contain 'monthly ingest', 'monthly refresh', 'monthly operating mode'."""
        code, output = _capture_output([
            "store-plan-ingest",
            "--all-user-folders",
            "--since", "2025-07-05",
            "--until", "2026-07-05",
            "--fixture",
        ])
        assert "monthly ingest" not in output.lower()
        assert "monthly refresh" not in output.lower()
        assert "monthly operating mode" not in output.lower()

    def test_missing_catalog_returns_error(self) -> None:
        """Without fixture and without catalog, should error."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(os.path.join(store_root, "catalog"), exist_ok=True)
            code, output = _capture_output([
                "store-plan-ingest",
                "--all-user-folders",
                "--since", "2025-07-05",
                "--until", "2026-07-05",
                "--store-root", store_root,
            ])
            assert code == 1
            assert "No source catalog found" in output

    def test_plan_shows_folder_count(self) -> None:
        code, output = _capture_output([
            "store-plan-ingest",
            "--all-user-folders",
            "--since", "2025-07-05",
            "--until", "2026-07-05",
            "--fixture",
        ])
        assert "Folders planned: 4" in output
        assert "Chunks planned: 52" in output

    def test_plan_shows_estimated_items(self) -> None:
        code, output = _capture_output([
            "store-plan-ingest",
            "--all-user-folders",
            "--since", "2025-07-05",
            "--until", "2026-07-05",
            "--fixture",
        ])
        assert "Estimated items:" in output
