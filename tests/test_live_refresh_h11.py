from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from export_engine import live
from export_engine.schemas import new_live_state


class _FakeItems:
    Count = 0

    def Restrict(self, _filter: str):
        return self


class _FakeFolder:
    def __init__(self, name: str, children: list["_FakeFolder"] | None = None):
        self.Name = name
        self.Folders = children or []
        self.Items = _FakeItems()


def _write_live_store(root: Path, folders: list[dict], state: dict) -> None:
    (root / "catalog").mkdir(parents=True)
    (root / "catalog" / "source_catalog_latest.json").write_text(
        json.dumps({"folders": folders}), encoding="utf-8"
    )
    (root / "live_state.json").write_text(json.dumps(state), encoding="utf-8")


def test_refresh_folder_uses_existing_com_folder_resolver() -> None:
    root = _FakeFolder("Mailbox", [_FakeFolder("Inbox")])
    idx = {"\\inbox": {"folderPath": "\\Inbox"}}

    new_count, changed_count, dup_count, err_count = live._refresh_folder(
        root=root,
        folder_index=idx,
        folder_entry={"folderPath": "\\Inbox", "folderKey": "inbox"},
        store_display_name="Mailbox",
        store_id_hash="storehash",
        store_root="unused",
        hwm="",
        role="inbox",
    )

    assert (new_count, changed_count, dup_count, err_count) == (0, 0, 0, 0)


def test_failed_folder_refresh_does_not_advance_that_folder_or_summary_watermark(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = "2026-07-05T08:59:34+00:00"
    folders = [
        {"folderPath": "\\Inbox", "folderKey": "inbox", "defaultRole": "inbox", "included": True},
        {"folderPath": "\\Sent Items", "folderKey": "sent", "defaultRole": "sent", "included": True},
    ]
    state = new_live_state(live_enabled=True)
    state["inboxHighWatermark"] = before
    state["sentItemsHighWatermark"] = before
    state["highWatermarks"] = {"inbox": before, "sent": before}
    _write_live_store(tmp_path, folders, state)

    class _FakeStore:
        DisplayName = "Mailbox"
        StoreID = "store"

        def GetRootFolder(self):
            return _FakeFolder("Mailbox")

    class _FakeInbox:
        Store = _FakeStore()

    class _FakeNamespace:
        def GetDefaultFolder(self, _folder_id: int):
            return _FakeInbox()

    class _FakeOutlook:
        def GetNamespace(self, _name: str):
            return _FakeNamespace()

        def Quit(self):
            pass

    class _FakeWin32Com:
        def Dispatch(self, _name: str):
            return _FakeOutlook()

    monkeypatch.setattr("export_engine.outlook_com_source.outlook_available", lambda: True)
    monkeypatch.setattr("export_engine.outlook_com_source._win32com", _FakeWin32Com())
    monkeypatch.setattr("export_engine.outlook_com_source.build_folder_index", lambda *a, **k: ({}, []))

    def fake_refresh(*args, **kwargs):
        raise RuntimeError("folder unavailable")

    monkeypatch.setattr(live, "_refresh_folder", fake_refresh)
    monkeypatch.setattr("export_engine.vault.build_vault", lambda _root: {"vaultNotesWritten": 0})

    result = live.live_refresh_once(str(tmp_path))
    updated = json.loads((tmp_path / "live_state.json").read_text(encoding="utf-8"))

    assert result["errors"] == 2
    assert result["errorMessages"]
    assert updated["highWatermarks"] == {"inbox": before, "sent": before}
    assert updated["inboxHighWatermark"] == before
    assert updated["sentItemsHighWatermark"] == before
    assert updated["errorsLastRun"] == 2
    assert updated["mailboxWrites"] == 0
    assert updated["kanbanWrites"] == 0
    assert updated["cloudApiCalls"] == 0


def test_successful_folder_refresh_advances_only_successful_watermark(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = "2026-07-05T08:59:34+00:00"
    folders = [
        {"folderPath": "\\Inbox", "folderKey": "inbox", "defaultRole": "inbox", "included": True},
        {"folderPath": "\\Sent Items", "folderKey": "sent", "defaultRole": "sent", "included": True},
    ]
    state = new_live_state(live_enabled=True)
    state["inboxHighWatermark"] = before
    state["sentItemsHighWatermark"] = before
    state["highWatermarks"] = {"inbox": before, "sent": before}
    _write_live_store(tmp_path, folders, state)

    class _FakeStore:
        DisplayName = "Mailbox"
        StoreID = "store"

        def GetRootFolder(self):
            return _FakeFolder("Mailbox")

    class _FakeInbox:
        Store = _FakeStore()

    class _FakeNamespace:
        def GetDefaultFolder(self, _folder_id: int):
            return _FakeInbox()

    class _FakeOutlook:
        def GetNamespace(self, _name: str):
            return _FakeNamespace()

        def Quit(self):
            pass

    class _FakeWin32Com:
        def Dispatch(self, _name: str):
            return _FakeOutlook()

    monkeypatch.setattr("export_engine.outlook_com_source.outlook_available", lambda: True)
    monkeypatch.setattr("export_engine.outlook_com_source._win32com", _FakeWin32Com())
    monkeypatch.setattr("export_engine.outlook_com_source.build_folder_index", lambda *a, **k: ({}, []))
    monkeypatch.setattr(live, "_refresh_folder", lambda *a, **k: (0, 0, 0, 0))
    monkeypatch.setattr("export_engine.vault.build_vault", lambda _root: {"vaultNotesWritten": 0})

    result = live.live_refresh_once(str(tmp_path))
    updated = json.loads((tmp_path / "live_state.json").read_text(encoding="utf-8"))

    assert result["errors"] == 0
    assert updated["highWatermarks"]["inbox"] != before
    assert updated["highWatermarks"]["sent"] != before
    assert updated["inboxHighWatermark"] == updated["highWatermarks"]["inbox"]
    assert updated["sentItemsHighWatermark"] == updated["highWatermarks"]["sent"]
    assert updated["mailboxWrites"] == 0
    assert updated["kanbanWrites"] == 0
    assert updated["cloudApiCalls"] == 0


def test_cli_reports_refresh_errors_and_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from export_engine import cli

    monkeypatch.setattr(
        "export_engine.live.live_refresh_once",
        lambda: {
            "storeRoot": "C:/store",
            "foldersProcessed": 0,
            "sentItemsIncluded": True,
            "newRecords": 0,
            "changedRecords": 0,
            "duplicatesSkipped": 0,
            "errors": 1,
            "mailboxWrites": 0,
            "kanbanWrites": 0,
            "cloudApiCalls": 0,
            "fullMailboxReprocess": False,
            "errorMessages": ["Error refreshing \\Inbox: boom"],
        },
    )

    rc = cli.cmd_store_live_refresh_once(argparse.Namespace())
    out = capsys.readouterr().out

    assert rc == 1
    assert "Errors:            1" in out
    assert "Error refreshing \\Inbox: boom" in out
    assert "failed folder high-watermarks were not advanced" in out
    assert "Mailbox writes: 0" in out
    assert "Kanban writes:  0" in out
    assert "Cloud/API:      0" in out
