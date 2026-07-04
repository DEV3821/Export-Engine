"""Tests for folder path normalisation — root-relative canonical paths."""

from export_engine.outlook_com_source import (
    normalise_outlook_folder_path,
    folder_path_to_parts,
)


class TestNormaliseOutlookFolderPath:
    """Canonical path normalisation."""

    def test_strips_store_prefix(self) -> None:
        result = normalise_outlook_folder_path(
            "\\Brian.Shaw@sa.gov.au\\Inbox",
            store_display_name="Brian.Shaw@sa.gov.au",
        )
        assert result == "\\Inbox"

    def test_strips_store_prefix_nested(self) -> None:
        result = normalise_outlook_folder_path(
            "\\Brian.Shaw@sa.gov.au\\Inbox\\Projects",
            store_display_name="Brian.Shaw@sa.gov.au",
        )
        assert result == "\\Inbox\\Projects"

    def test_double_backslash_normalised(self) -> None:
        result = normalise_outlook_folder_path(
            "\\\\Brian.Shaw@sa.gov.au\\\\Inbox\\\\Projects",
            store_display_name="Brian.Shaw@sa.gov.au",
        )
        assert result == "\\Inbox\\Projects"

    def test_forward_slash_conversion(self) -> None:
        result = normalise_outlook_folder_path(
            "Inbox/Projects",
            store_display_name="Brian.Shaw@sa.gov.au",
        )
        assert result == "\\Inbox\\Projects"

    def test_root_relative_preserved(self) -> None:
        result = normalise_outlook_folder_path(
            "\\Inbox",
            store_display_name="Brian.Shaw@sa.gov.au",
        )
        assert result == "\\Inbox"

    def test_root_relative_nested_preserved(self) -> None:
        result = normalise_outlook_folder_path(
            "\\Sent Items",
            store_display_name="Brian.Shaw@sa.gov.au",
        )
        assert result == "\\Sent Items"

    def test_case_insensitive_store_match(self) -> None:
        result = normalise_outlook_folder_path(
            "\\BRIAN.SHAW@SA.GOV.AU\\Inbox",
            store_display_name="brian.shaw@sa.gov.au",
        )
        assert result == "\\Inbox"

    def test_trailing_slash_stripped(self) -> None:
        result = normalise_outlook_folder_path(
            "\\Inbox\\",
            store_display_name="Brian.Shaw@sa.gov.au",
        )
        assert result == "\\Inbox"

    def test_empty_path_returns_root(self) -> None:
        result = normalise_outlook_folder_path("")
        assert result == "\\"

    def test_no_store_prefix_unchanged(self) -> None:
        result = normalise_outlook_folder_path(
            "\\Inbox\\SubTeam",
            store_display_name="SomeOtherStore",
        )
        assert result == "\\Inbox\\SubTeam"

    def test_mixed_slashes(self) -> None:
        result = normalise_outlook_folder_path(
            "\\Brian.Shaw@sa.gov.au\\Inbox/Projects",
            store_display_name="Brian.Shaw@sa.gov.au",
        )
        assert result == "\\Inbox\\Projects"

    def test_fixture_path_unchanged(self) -> None:
        """Fixture paths like \\Inbox should pass through cleanly."""
        result = normalise_outlook_folder_path("\\Inbox")
        assert result == "\\Inbox"
        result = normalise_outlook_folder_path("\\Sent Items")
        assert result == "\\Sent Items"
        result = normalise_outlook_folder_path("\\Inbox\\SubTeam")
        assert result == "\\Inbox\\SubTeam"

    def test_legacy_catalog_path_normalises(self) -> None:
        """Legacy store-prefixed paths must still resolve."""
        result = normalise_outlook_folder_path(
            "\\mailbox@example.com\\Inbox\\Projects",
            store_display_name="mailbox@example.com",
        )
        assert result == "\\Inbox\\Projects"


class TestFolderPathToParts:
    """Split canonical paths into parts."""

    def test_inbox(self) -> None:
        assert folder_path_to_parts("\\Inbox") == ["Inbox"]

    def test_nested(self) -> None:
        assert folder_path_to_parts("\\Inbox\\Projects") == ["Inbox", "Projects"]

    def test_deep(self) -> None:
        assert folder_path_to_parts("\\Inbox\\Team\\Sub\\Deep") == ["Inbox", "Team", "Sub", "Deep"]
