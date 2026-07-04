"""Tests for fixture_source.py — synthetic source adapter."""

from export_engine.fixture_source import (
    build_default_fixtures,
    get_excluded_store_types,
)


class TestFixtureStoreTopology:
    """The fixture source must simulate primary, shared, and archive stores."""

    def test_has_three_stores(self) -> None:
        fixtures = build_default_fixtures()
        assert "stores" in fixtures
        assert len(fixtures["stores"]) == 3

    def test_primary_store_present(self) -> None:
        fixtures = build_default_fixtures()
        primary = fixtures["stores"]["primary"]
        assert primary["storeType"] == "primary"
        assert primary["isDefault"] is True

    def test_shared_store_present(self) -> None:
        fixtures = build_default_fixtures()
        shared = fixtures["stores"]["shared"]
        assert shared["storeType"] == "shared"

    def test_archive_store_present(self) -> None:
        fixtures = build_default_fixtures()
        archive = fixtures["stores"]["archive"]
        assert archive["storeType"] == "archive"


class TestFixtureExclusions:
    """Shared and archive stores must be excluded by default."""

    def test_shared_store_folders_excluded(self) -> None:
        fixtures = build_default_fixtures()
        for folder in fixtures["stores"]["shared"]["folders"]:
            assert folder["isExcluded"] is True, (
                f"Shared folder {folder['name']} not excluded"
            )

    def test_archive_store_folders_excluded(self) -> None:
        fixtures = build_default_fixtures()
        for folder in fixtures["stores"]["archive"]["folders"]:
            assert folder["isExcluded"] is True, (
                f"Archive folder {folder['name']} not excluded"
            )

    def test_primary_store_folders_not_excluded(self) -> None:
        fixtures = build_default_fixtures()
        for folder in fixtures["stores"]["primary"]["folders"]:
            assert folder["isExcluded"] is False, (
                f"Primary folder {folder['name']} should not be excluded"
            )

    def test_excluded_store_types(self) -> None:
        excluded = get_excluded_store_types()
        assert "shared" in excluded
        assert "archive" in excluded


class TestFixtureFolders:
    """Primary store must have expected folder types."""

    def test_inbox_folder_exists(self) -> None:
        fixtures = build_default_fixtures()
        folders = fixtures["stores"]["primary"]["folders"]
        types = {f["folderType"] for f in folders}
        assert "inbox" in types

    def test_sent_folder_exists(self) -> None:
        fixtures = build_default_fixtures()
        folders = fixtures["stores"]["primary"]["folders"]
        types = {f["folderType"] for f in folders}
        assert "sent" in types

    def test_custom_folder_exists(self) -> None:
        fixtures = build_default_fixtures()
        folders = fixtures["stores"]["primary"]["folders"]
        types = {f["folderType"] for f in folders}
        assert "custom" in types


class TestFixtureItems:
    """Sample items exist for primary store."""

    def test_items_exist(self) -> None:
        fixtures = build_default_fixtures()
        assert len(fixtures["items"]) > 0

    def test_items_have_subject(self) -> None:
        fixtures = build_default_fixtures()
        for item in fixtures["items"]:
            assert item["subject"] != ""
