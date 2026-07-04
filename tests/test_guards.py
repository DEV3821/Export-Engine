"""Tests for guards.py — path and safety guard functions."""

import os

from export_engine.guards import (
    is_under_path,
    contains_forbidden_fragment,
    has_forbidden_prefix,
    is_removable_drive,
    is_network_drive,
    is_path_allowed,
    verify_text_absent,
)


class TestIsUnderPath:
    def test_child_under_parent(self) -> None:
        assert is_under_path("C:/Users/me/AppData/Local/SAMI/KnowledgeStore", "C:/Users/me/AppData")

    def test_same_path(self) -> None:
        p = "C:/Users/me/AppData"
        assert is_under_path(p, p)

    def test_not_under(self) -> None:
        assert not is_under_path("C:/Windows", "C:/Users")

    def test_case_insensitive(self) -> None:
        assert is_under_path("C:/USERS/ME/AppData", "C:/users/me")


class TestForbiddenFragment:
    def test_onedrive_rejected(self) -> None:
        assert contains_forbidden_fragment("C:/Users/me/OneDrive/Documents")

    def test_dropbox_rejected(self) -> None:
        assert contains_forbidden_fragment("C:/Users/me/Dropbox/KnowledgeStore")

    def test_google_drive_rejected(self) -> None:
        assert contains_forbidden_fragment("C:/Users/me/Google Drive/Stuff")

    def test_desktop_rejected(self) -> None:
        assert contains_forbidden_fragment("C:/Users/me/Desktop/knowledge")

    def test_downloads_rejected(self) -> None:
        assert contains_forbidden_fragment("C:/Users/me/Downloads/export")

    def test_team_esmi_rejected(self) -> None:
        assert contains_forbidden_fragment("C:/Team_ESMI/KnowledgeStore")

    def test_appdata_accepted(self) -> None:
        assert not contains_forbidden_fragment(
            "C:/Users/me/AppData/Local/SAMI/KnowledgeStore"
        )


class TestForbiddenPrefix:
    def test_unc_rejected(self) -> None:
        assert has_forbidden_prefix("\\\\server\\share\\KnowledgeStore")

    def test_unc_forward_slash_rejected(self) -> None:
        assert has_forbidden_prefix("//server/share/KnowledgeStore")

    def test_normal_accepted(self) -> None:
        assert not has_forbidden_prefix("C:/Users/me/AppData")


class TestRemovableDrive:
    def test_d_drive_flagged(self) -> None:
        assert is_removable_drive("D:/KnowledgeStore")

    def test_e_drive_flagged(self) -> None:
        assert is_removable_drive("E:/some/path")

    def test_c_drive_accepted(self) -> None:
        assert not is_removable_drive("C:/Users/me/AppData")


class TestNetworkDrive:
    def test_z_drive_flagged(self) -> None:
        assert is_network_drive("Z:/KnowledgeStore")

    def test_y_drive_flagged(self) -> None:
        assert is_network_drive("Y:/shared/data")

    def test_c_drive_not_network(self) -> None:
        assert not is_network_drive("C:/Users")


class TestIsPathAllowed:
    def test_appdata_allowed(self) -> None:
        p = "C:/Users/me/AppData/Local/SAMI/KnowledgeStore"
        assert is_path_allowed(p)

    def test_repo_path_rejected(self) -> None:
        store = "C:/Tools/Export engine/KnowledgeStore"
        repo = "C:/Tools/Export engine"
        assert not is_path_allowed(store, repo_path=repo)

    def test_onedrive_rejected(self) -> None:
        assert not is_path_allowed("C:/Users/me/OneDrive/KnowledgeStore")

    def test_desktop_rejected(self) -> None:
        assert not is_path_allowed("C:/Users/me/Desktop/data")

    def test_downloads_rejected(self) -> None:
        assert not is_path_allowed("C:/Users/me/Downloads/data")

    def test_unc_rejected(self) -> None:
        assert not is_path_allowed("\\\\server\\share\\KnowledgeStore")


class TestVerifyTextAbsent:
    """Check that banned phrases are detected in text."""

    BANNED = [
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

    def test_clean_text(self) -> None:
        text = "Local Knowledge Store — all systems nominal."
        results = verify_text_absent(text, self.BANNED)
        assert all(not found for found in results.values())

    def test_banned_phrase_detected(self) -> None:
        text = "This is a Phase 8A reference"
        results = verify_text_absent(text, ["Phase 8A"])
        assert results["Phase 8A"] is True

    def test_case_insensitive_detection(self) -> None:
        text = "this uses mr kanban in the description"
        results = verify_text_absent(text, ["Mr Kanban"])
        assert results["Mr Kanban"] is True
