"""Tests for outlook_com_source.py — Outlook COM source adapter shape."""

from export_engine.outlook_com_source import (
    outlook_available,
    _infer_default_role,
    _is_folder_excluded,
)


class TestAdapterShape:
    """Adapter class exists with correct identity."""

    def test_outlook_available_does_not_crash_at_import(self) -> None:
        """Importing the module should never crash."""
        from export_engine import outlook_com_source  # noqa: F811
        assert outlook_com_source is not None

    def test_outlook_available_returns_bool(self) -> None:
        """outlook_available() returns a bool, not an exception."""
        result = outlook_available()
        assert isinstance(result, bool)


class TestRoleInference:
    """Folder display names correctly map to default roles."""

    def test_inbox_role(self) -> None:
        assert _infer_default_role("Inbox", "\\Inbox") == "inbox"

    def test_sent_role(self) -> None:
        assert _infer_default_role("Sent Items", "\\Sent Items") == "sent"

    def test_deleted_role(self) -> None:
        assert _infer_default_role("Deleted Items", "\\Deleted Items") == "deleted"

    def test_junk_role(self) -> None:
        assert _infer_default_role("Junk Email", "\\Junk Email") == "junk"

    def test_drafts_role(self) -> None:
        assert _infer_default_role("Drafts", "\\Drafts") == "drafts"

    def test_outbox_role(self) -> None:
        assert _infer_default_role("Outbox", "\\Outbox") == "outbox"

    def test_sync_issues_role(self) -> None:
        assert _infer_default_role("Sync Issues", "\\Sync Issues") == "sync_issues"

    def test_calendar_role(self) -> None:
        assert _infer_default_role("Calendar", "\\Calendar") == "calendar"

    def test_contacts_role(self) -> None:
        assert _infer_default_role("Contacts", "\\Contacts") == "contacts"

    def test_tasks_role(self) -> None:
        assert _infer_default_role("Tasks", "\\Tasks") == "tasks"

    def test_notes_role(self) -> None:
        assert _infer_default_role("Notes", "\\Notes") == "notes"

    def test_search_folders_role(self) -> None:
        assert _infer_default_role("Search Folders", "\\Search Folders") == "search"

    def test_custom_role(self) -> None:
        assert _infer_default_role("My Custom Folder", "\\My Custom Folder") == "custom"

    def test_subfolder_role_inherited(self) -> None:
        assert _infer_default_role("SubTeam", "\\Inbox\\SubTeam") == "custom"


class TestFolderExclusion:
    """Default-excluded folders are correctly excluded."""

    def test_deleted_excluded(self) -> None:
        excluded, reason = _is_folder_excluded("deleted", "Deleted Items")
        assert excluded is True
        assert "deleted" in reason

    def test_junk_excluded(self) -> None:
        excluded, reason = _is_folder_excluded("junk", "Junk Email")
        assert excluded is True
        assert "junk" in reason

    def test_drafts_excluded(self) -> None:
        excluded, reason = _is_folder_excluded("drafts", "Drafts")
        assert excluded is True
        assert "drafts" in reason

    def test_outbox_excluded(self) -> None:
        excluded, reason = _is_folder_excluded("outbox", "Outbox")
        assert excluded is True
        assert "outbox" in reason

    def test_calendar_excluded(self) -> None:
        excluded, reason = _is_folder_excluded("calendar", "Calendar")
        assert excluded is True
        assert "calendar" in reason

    def test_contacts_excluded(self) -> None:
        excluded, reason = _is_folder_excluded("contacts", "Contacts")
        assert excluded is True
        assert "contacts" in reason

    def test_inbox_included(self) -> None:
        excluded, reason = _is_folder_excluded("inbox", "Inbox")
        assert excluded is False

    def test_sent_included(self) -> None:
        excluded, reason = _is_folder_excluded("sent", "Sent Items")
        assert excluded is False

    def test_custom_included(self) -> None:
        excluded, reason = _is_folder_excluded("custom", "Projects")
        assert excluded is False


class TestFolderInclusionWithFlags:
    """Include flags override default exclusions."""

    def test_include_deleted_flag(self) -> None:
        excluded, reason = _is_folder_excluded("deleted", "Deleted Items", include_deleted=True)
        assert excluded is False

    def test_include_junk_flag(self) -> None:
        excluded, reason = _is_folder_excluded("junk", "Junk Email", include_junk=True)
        assert excluded is False

    def test_include_drafts_flag(self) -> None:
        excluded, reason = _is_folder_excluded("drafts", "Drafts", include_drafts=True)
        assert excluded is False
