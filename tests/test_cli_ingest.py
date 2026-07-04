"""Tests for cli.py — store-ingest CLI behaviour."""

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


class TestCLIIngest:
    """store-ingest CLI behaviour."""

    def test_ingest_help(self) -> None:
        assert "store-ingest" in build_parser().format_help()

    def test_ingest_help_detail(self) -> None:
        code, _ = _run(["store-ingest", "--help"])
        assert code == 0

    def test_fixture_ingest_output(self) -> None:
        """Test that fixture mode ingests and produces correct output."""
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            # Need a plan first
            from export_engine.source_scan import run_source_scan
            from export_engine.planning import create_backfill_plan
            run_source_scan(store_root, use_fixture=True)
            create_backfill_plan(store_root, use_fixture=True, since="2025-07-05", until="2025-08-05")
            code, output = _run(["store-ingest", "--fixture", "--limit", "5", "--resume", "--store-root", store_root])
            assert code == 0, f"Exit code {code}: {output[:200]}"
            assert "Local Knowledge Store record ingest" in output
            assert "Records exported:" in output
            assert "Fixture mode: enabled" in output

    def test_no_banned_branding(self) -> None:
        code, output = _run(["store-ingest", "--help"])
        for phrase in BANNED:
            assert phrase.lower() not in output.lower(), f"Banned: {phrase}"

    def test_future_flags_accepted(self) -> None:
        code, output = _run(["store-ingest", "--parse-extracts", "--build-retrieval", "--build-index", "--build-vault", "--build-canvas", "--help"])
        assert code == 0

    def test_missing_plan_returns_error(self) -> None:
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(os.path.join(store_root, "runs"), exist_ok=True)
            code, output = _run(["store-ingest", "--fixture", "--limit", "5", "--resume", "--store-root", store_root])
            assert "No ingest plan" in output or code == 1
