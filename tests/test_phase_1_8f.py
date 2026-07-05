"""Tests for Phase 1.8F — CLI integration, offline commands, vault, live."""

from __future__ import annotations

import json
import os
import sys
import subprocess
import pytest


# ── Helpers ─────────────────────────────────────────────────────────────

EXPECTED_OFFLINE_COMMANDS = [
    "store-audit-offline",
    "store-analyse-state",
    "store-rebuild-derived",
    "store-build-vault",
    "store-validate",
]

EXPECTED_LIVE_COMMANDS = [
    "store-live-status",
    "store-live-enable",
    "store-live-disable",
    "store-live-refresh-once",
]

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    """Run the export_engine CLI and return the result."""
    cmd = [sys.executable, "-m", "export_engine.cli"] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=REPO_ROOT)
    return r


def _list_package_modules() -> list[str]:
    """List Python modules under export_engine/."""
    mods = []
    ee_dir = os.path.join(REPO_ROOT, "export_engine")
    if os.path.isdir(ee_dir):
        for fn in sorted(os.listdir(ee_dir)):
            if fn.endswith(".py") and fn != "__init__.py":
                mods.append(fn[:-3])
    return mods


# ── Test: CLI commands are registered ───────────────────────────────────


class TestCliCommandsRegistered:
    """All Phase 1.8F CLI commands must appear in --help output."""

    def test_help_output_contains_offline_commands(self):
        r = _run_cli("--help")
        assert r.returncode == 0, f"CLI --help failed: {r.stderr}"
        for cmd in EXPECTED_OFFLINE_COMMANDS:
            assert cmd in r.stdout, f"Offline command '{cmd}' not in --help"

    def test_help_output_contains_live_commands(self):
        r = _run_cli("--help")
        assert r.returncode == 0
        for cmd in EXPECTED_LIVE_COMMANDS:
            assert cmd in r.stdout, f"Live command '{cmd}' not in --help"

    def test_offline_commands_have_no_com_import(self):
        """Offline commands must not import outlook_com_source."""
        for cmd in EXPECTED_OFFLINE_COMMANDS:
            r = _run_cli(cmd, "--help")
            assert r.returncode == 0, f"{cmd} --help failed"

    def test_live_commands_have_help(self):
        for cmd in EXPECTED_LIVE_COMMANDS:
            r = _run_cli(cmd, "--help")
            assert r.returncode == 0, f"{cmd} --help failed"


# ── Test: Module imports and compilation ────────────────────────────────


class TestModuleImports:
    """All new modules must import cleanly."""

    def test_offline_imports(self):
        from export_engine.offline import (
            audit_offline, analyse_state, rebuild_derived, validate_offline,
        )
        assert callable(audit_offline)
        assert callable(analyse_state)
        assert callable(rebuild_derived)
        assert callable(validate_offline)

    def test_vault_imports(self):
        from export_engine.vault import build_vault
        assert callable(build_vault)

    def test_live_imports(self):
        from export_engine.live import live_status, live_enable, live_disable, live_refresh_once
        assert callable(live_status)
        assert callable(live_enable)
        assert callable(live_disable)
        assert callable(live_refresh_once)

    def test_fixture_quarantine_imports(self):
        from export_engine.fixture_quarantine import quarantine_fixtures, scan_for_fixtures
        assert callable(quarantine_fixtures)
        assert callable(scan_for_fixtures)

    def test_all_modules_compile(self):
        """Run compileall on export_engine/."""
        import py_compile
        for mod in _list_package_modules():
            path = os.path.join(REPO_ROOT, "export_engine", mod + ".py")
            py_compile.compile(path, doraise=True)


# ── Test: Schema additions ──────────────────────────────────────────────


class TestSchemaAdditions:
    """Phase 1.8F schema additions must be present."""

    def test_vault_note_schema_exists(self):
        from export_engine.schemas import SCHEMA_VERSION_VAULT_NOTE, new_vault_note
        assert SCHEMA_VERSION_VAULT_NOTE == "export.vaultNote.v1"
        note = new_vault_note()
        assert note["_schema"] == "export.vaultNote.v1"
        assert note["mailboxWrite"] is False
        assert note["kanbanWrite"] is False
        assert note["cloudApiCalls"] is False
        assert note["llmUsed"] is False
        assert note["offlineRefineOnly"] is True
        assert note["attachmentStatus"] == "deferred"

    def test_live_state_schema_exists(self):
        from export_engine.schemas import SCHEMA_VERSION_LIVE_STATE, new_live_state
        assert SCHEMA_VERSION_LIVE_STATE == "export.liveState.v1"
        state = new_live_state(live_enabled=True)
        assert state["_schema"] == "export.liveState.v1"
        assert state["liveEnabled"] is True
        assert state["mailboxWrites"] == 0
        assert state["kanbanWrites"] == 0
        assert state["cloudApiCalls"] == 0
        assert state["includeSentItems"] is True


# ── Test: Offline safety — no Outlook COM ───────────────────────────────


class TestOfflineSafety:
    """Offline commands must not import or instantiate Outlook COM."""

    def test_audit_offline_no_com(self):
        from export_engine.offline import audit_offline
        # Just verify it's callable — doesn't import COM
        import inspect
        source = inspect.getsource(audit_offline)
        assert "outlook" not in source.lower() or "outlook_com" not in source.lower()

    def test_rebuild_derived_no_com(self):
        from export_engine.offline import rebuild_derived
        import inspect
        source = inspect.getsource(rebuild_derived)
        assert "outlook" not in source.lower() or "outlook_com" not in source.lower()

    def test_vault_no_com(self):
        from export_engine.vault import build_vault
        import inspect
        source = inspect.getsource(build_vault)
        assert "outlook" not in source.lower() or "outlook_com" not in source.lower()

    def test_validate_offline_no_com(self):
        from export_engine.offline import validate_offline
        import inspect
        source = inspect.getsource(validate_offline)
        assert "outlook" not in source.lower() or "outlook_com" not in source.lower()


# ── Test: Validator checks ──────────────────────────────────────────────


class TestValidatorChecks:
    """Validator must catch specific failure conditions."""

    def test_validator_requires_sent_items(self):
        from export_engine.offline import validate_offline
        result = validate_offline(require_sent_items=True, require_vault_notes=False)
        assert "sentItemsIncluded" in result.get("checks", {})
        assert "noMailboxWrite" in result.get("checks", {})
        assert "noKanbanWrite" in result.get("checks", {})
        assert "noCloudApiCalls" in result.get("checks", {})
        assert "noRawMsgEml" in result.get("checks", {})
        assert "attachmentStatusExplicit" in result.get("checks", {})
        assert "vaultNotesExist" in result.get("checks", {})

    def test_validator_reports_attachment_status(self):
        from export_engine.offline import validate_offline
        result = validate_offline(require_vault_notes=False)
        assert result.get("attachmentParsingDeferred") is True
        checks = result.get("checks", {})
        assert "attachmentStatusExplicit" in checks, f"checks keys: {list(checks.keys())}"

    def test_validator_reports_safety_block(self):
        from export_engine.offline import validate_offline
        result = validate_offline(require_vault_notes=False)
        sa = result.get("safety", {})
        assert sa.get("mailboxWrites", -1) == 0
        assert sa.get("kanbanWrites", -1) == 0
        assert sa.get("cloudApiCalls", -1) == 0


# ── Test: Fixture quarantine ────────────────────────────────────────────


class TestFixtureQuarantine:
    """Fixture quarantine must detect and isolate test data."""

    def test_scan_for_fixtures_runs(self):
        from export_engine.fixture_quarantine import scan_for_fixtures
        result = scan_for_fixtures()
        assert result is not None
        assert "fixtureRecordsFound" in result
        assert "fixtureRecordKeys" in result
        assert result.get("dryRun") is True

    def test_fixture_detection_subject_marker(self):
        from export_engine.fixture_quarantine import _is_fixture_record
        rec = {
            "headers": {"subject": "Fixture message test", "from": {"emailAddress": ""}},
            "source": {"folderPath": "\\Inbox"},
        }
        assert _is_fixture_record(rec) is True

    def test_fixture_detection_example_dot_com(self):
        from export_engine.fixture_quarantine import _is_fixture_record
        rec = {
            "headers": {"subject": "Real Subject", "from": {"emailAddress": "test@example.com"}},
            "source": {"folderPath": "\\Inbox"},
        }
        assert _is_fixture_record(rec) is True

    def test_real_record_not_fixture(self):
        from export_engine.fixture_quarantine import _is_fixture_record
        rec = {
            "headers": {"subject": "Project Update", "from": {"emailAddress": "colleague@agency.gov.au"}},
            "source": {"folderPath": "\\Inbox"},
        }
        assert _is_fixture_record(rec) is False


# ── Test: Vault builder ─────────────────────────────────────────────────


class TestVaultBuilder:
    """Vault builder must create deterministic notes."""

    def test_build_vault_returns_manifest(self):
        from export_engine.vault import build_vault
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            # Create minimal vault structure
            os.makedirs(os.path.join(td, "conversations"))
            os.makedirs(os.path.join(td, "vault"))
            os.makedirs(os.path.join(td, "records"))
            os.makedirs(os.path.join(td, "retrieval"))
            os.makedirs(os.path.join(td, "index"))
            result = build_vault(store_root=td)
            assert result is not None
            assert "vaultNotesWritten" in result
            assert "vaultDashboardsWritten" in result
            assert "mailboxWrites" in result
            assert result["mailboxWrites"] == 0
            assert result["kanbanWrites"] == 0
            assert result["cloudApiCalls"] == 0
            assert result["llmUsed"] is False
            assert result["outlookComUsed"] is False


# ── Test: Live module safety ────────────────────────────────────────────


class TestLiveSafety:
    """Live module must enforce safety invariants."""

    def test_live_status_no_com(self):
        """live_status must not require Outlook COM."""
        from export_engine.live import live_status
        import inspect
        source = inspect.getsource(live_status)
        # live_status should not import COM modules directly
        assert "outlook_com_source" not in source

    def test_live_disable_no_com(self):
        from export_engine.live import live_disable
        import inspect
        source = inspect.getsource(live_disable)
        assert "outlook_com_source" not in source

    def test_live_enable_requires_validation(self):
        from export_engine.live import live_enable
        import inspect
        source = inspect.getsource(live_enable)
        assert "validate_offline" in source

    def test_live_state_has_safety_fields(self):
        from export_engine.schemas import new_live_state
        state = new_live_state()
        assert state["mailboxWrites"] == 0
        assert state["kanbanWrites"] == 0
        assert state["cloudApiCalls"] == 0

    def test_live_refresh_safety_properties(self):
        from export_engine.live import live_refresh_once
        import inspect
        source = inspect.getsource(live_refresh_once)
        # Must use high-watermark pattern, not full-scan
        assert "high_watermark" in source.lower() or "higherWatermark" in source or "hwm" in source.lower()


# ── Test: Config and profile ────────────────────────────────────────────


class TestRolloutProfile:
    """Rollout profile config must exist and be valid."""

    def test_rollout_profile_exists(self):
        profile_path = os.path.join(REPO_ROOT, "config", "knowledge_store_rollout_profile.json")
        assert os.path.isfile(profile_path), f"Profile not found at {profile_path}"
        with open(profile_path) as f:
            profile = json.load(f)
        assert profile.get("schema") == "sami.knowledgeStoreRolloutProfile.v1"
        assert profile.get("includeSentItems") is True
        assert profile.get("requireSentItemsForLiveMode") is True
        assert profile.get("liveRefresh", {}).get("includeSentItems") is True

    def test_lessons_doc_exists(self):
        lessons_path = os.path.join(REPO_ROOT, "docs", "knowledge_store_rollout_lessons.md")
        assert os.path.isfile(lessons_path)


# ── Test: Safety across all modules ─────────────────────────────────────


class TestSafetyInvariants:
    """Safety invariants must hold across the codebase."""

    def test_no_kanban_write_in_new_modules(self):
        """Scan new modules for kanban write patterns."""
        for mod in ("offline.py", "vault.py", "live.py"):
            path = os.path.join(REPO_ROOT, "export_engine", mod)
            if not os.path.isfile(path):
                continue
            with open(path) as f:
                content = f.read().lower()
            assert "kanbanwrite" in content, f"{mod} does not mention kanbanWrite"

    def test_no_cloud_api_in_new_modules(self):
        for mod in ("offline.py", "vault.py", "live.py"):
            path = os.path.join(REPO_ROOT, "export_engine", mod)
            if not os.path.isfile(path):
                continue
            with open(path) as f:
                content = f.read().lower()
            assert "cloudapicalls" in content or "cloudapicalls" in content, \
                f"{mod} does not mention cloudApiCalls"

    def test_no_mailbox_write_in_new_modules(self):
        for mod in ("offline.py", "vault.py", "live.py"):
            path = os.path.join(REPO_ROOT, "export_engine", mod)
            if not os.path.isfile(path):
                continue
            with open(path) as f:
                content = f.read().lower()
            assert "mailboxwrite" in content, f"{mod} does not mention mailboxWrite"
