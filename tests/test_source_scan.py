"""Tests for source_scan.py — source scan orchestration with fixtures."""

import json
import os
import tempfile

from export_engine.source_scan import run_source_scan


class TestFixtureSourceScan:
    """Fixture-based source scan writes correct catalog and run manifest."""

    def _run_scan(self, **kwargs) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            catalog = run_source_scan(store_root, use_fixture=True, **kwargs)
            return catalog

    def _run_scan_and_check_files(self, **kwargs) -> tuple[dict, str]:
        """Run scan and return (catalog, store_root) with files written."""
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            catalog = run_source_scan(store_root, use_fixture=True, **kwargs)

            # Check files exist
            catalog_path = os.path.join(store_root, "catalog", "source_catalog_latest.json")
            assert os.path.isfile(catalog_path), "Catalog file not written"

            runs_dir = os.path.join(store_root, "runs")
            run_files = [f for f in os.listdir(runs_dir) if f.startswith("source_scan_")]
            assert len(run_files) >= 1, "Run manifest not written"

            return catalog, store_root

    def test_scan_writes_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            run_source_scan(store_root, use_fixture=True)
            catalog_path = os.path.join(store_root, "catalog", "source_catalog_latest.json")
            assert os.path.isfile(catalog_path)

    def test_scan_writes_run_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            run_source_scan(store_root, use_fixture=True)
            runs_dir = os.path.join(store_root, "runs")
            run_files = [f for f in os.listdir(runs_dir) if f.startswith("source_scan_")]
            assert len(run_files) >= 1

    def test_catalog_schema_version(self) -> None:
        catalog = self._run_scan()
        assert catalog["_schema"] == "export.sourceCatalog.v1"

    def test_scan_run_schema_in_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_root, exist_ok=True)
            run_source_scan(store_root, use_fixture=True)
            runs_dir = os.path.join(store_root, "runs")
            run_files = sorted(os.listdir(runs_dir))
            run_path = os.path.join(runs_dir, run_files[0])
            with open(run_path) as f:
                manifest = json.load(f)
            assert manifest["_schema"] == "export.sourceScanRun.v1"

    def test_scope_is_primary_user_store_only(self) -> None:
        catalog = self._run_scan()
        assert catalog["scope"] == "primary_user_store_only"

    def test_primary_inbox_included(self) -> None:
        catalog = self._run_scan()
        inbox = [f for f in catalog["folders"] if f["defaultRole"] == "inbox"]
        assert len(inbox) >= 1
        assert all(f["included"] for f in inbox)

    def test_sent_items_included(self) -> None:
        catalog = self._run_scan()
        sent = [f for f in catalog["folders"] if f["defaultRole"] == "sent"]
        assert len(sent) >= 1
        assert all(f["included"] for f in sent)

    def test_inbox_subfolders_included(self) -> None:
        catalog = self._run_scan()
        subteam = [f for f in catalog["folders"] if f["displayName"] == "SubTeam"]
        assert len(subteam) >= 1
        assert subteam[0]["included"] is True

    def test_custom_folders_included(self) -> None:
        catalog = self._run_scan()
        projects = [f for f in catalog["folders"] if f["displayName"] == "Projects"]
        assert len(projects) >= 1
        assert projects[0]["included"] is True

    def test_deleted_items_excluded(self) -> None:
        catalog = self._run_scan()
        deleted = [f for f in catalog["folders"] if f["defaultRole"] == "deleted"]
        assert len(deleted) >= 1
        assert all(not f["included"] for f in deleted)

    def test_junk_excluded(self) -> None:
        catalog = self._run_scan()
        junk = [f for f in catalog["folders"] if f["defaultRole"] == "junk"]
        assert len(junk) >= 1
        assert all(not f["included"] for f in junk)

    def test_drafts_excluded(self) -> None:
        catalog = self._run_scan()
        drafts = [f for f in catalog["folders"] if f["defaultRole"] == "drafts"]
        assert len(drafts) >= 1
        assert all(not f["included"] for f in drafts)

    def test_outbox_excluded(self) -> None:
        catalog = self._run_scan()
        outbox = [f for f in catalog["folders"] if f["defaultRole"] == "outbox"]
        assert len(outbox) >= 1
        assert all(not f["included"] for f in outbox)

    def test_sync_issues_excluded(self) -> None:
        catalog = self._run_scan()
        sync = [f for f in catalog["folders"] if f["defaultRole"] == "sync_issues"]
        assert len(sync) >= 1
        assert all(not f["included"] for f in sync)

    def test_calendar_excluded(self) -> None:
        catalog = self._run_scan()
        cal = [f for f in catalog["folders"] if f["defaultRole"] == "calendar"]
        assert len(cal) >= 1
        assert all(not f["included"] for f in cal)

    def test_contacts_excluded(self) -> None:
        catalog = self._run_scan()
        contacts = [f for f in catalog["folders"] if f["defaultRole"] == "contacts"]
        assert len(contacts) >= 1
        assert all(not f["included"] for f in contacts)

    def test_shared_store_excluded(self) -> None:
        catalog = self._run_scan()
        shared = [s for s in catalog["excludedStores"] if "Shared" in s["displayName"]]
        assert len(shared) >= 1

    def test_archive_store_excluded(self) -> None:
        catalog = self._run_scan()
        archive = [s for s in catalog["excludedStores"] if "Archive" in s["displayName"]]
        assert len(archive) >= 1

    def test_excluded_stores_recorded(self) -> None:
        catalog = self._run_scan()
        assert len(catalog["excludedStores"]) >= 2

    def test_mailbox_write_false(self) -> None:
        catalog = self._run_scan()
        assert catalog["audit"]["mailboxWrite"] is False

    def test_kanban_write_false(self) -> None:
        catalog = self._run_scan()
        assert catalog["audit"]["kanbanWrite"] is False

    def test_cloud_api_calls_false(self) -> None:
        catalog = self._run_scan()
        assert catalog["audit"]["cloudApiCalls"] is False

    def test_raw_source_retained_false(self) -> None:
        catalog = self._run_scan()
        assert catalog["audit"]["rawSourceRetained"] is False

    def test_no_email_body_in_catalog(self) -> None:
        """Catalog must not contain email body content."""
        catalog = self._run_scan()
        catalog_text = json.dumps(catalog).lower()
        assert "here is the latest" not in catalog_text, "Body text leaked into catalog"
        assert "bodyPreview" not in catalog_text, "bodyPreview field should not exist in catalog"

    def test_folder_key_is_hash_based(self) -> None:
        catalog = self._run_scan()
        for f in catalog["folders"]:
            assert len(f["folderKey"]) == 64, f"folderKey not a SHA-256 hash: {f['folderKey']}"
            assert all(c in "0123456789abcdef" for c in f["folderKey"]), f"folderKey not hex: {f['folderKey']}"

    def test_store_id_hash_is_hash_based(self) -> None:
        catalog = self._run_scan()
        assert len(catalog["storeIdHash"]) == 64
        assert all(c in "0123456789abcdef" for c in catalog["storeIdHash"])
