# Phase H1.1 live refresh safety note

This phase repaired the one-shot near-live refresh path used by:

```powershell
python -m export_engine.cli store-live-refresh-once
```

## What was fixed

- `_refresh_folder()` now imports and uses the existing Outlook COM folder resolver from `outlook_com_source.resolve_com_folder_by_path`.
- Folder high-watermarks advance only after that folder refreshes with zero errors.
- If a folder refresh fails, its high-watermark remains unchanged so the next one-shot refresh can retry the same window.
- The CLI returns non-zero when refresh errors are reported and prints a warning that failed folder high-watermarks were not advanced.

## Safe verification

Run exactly one manual one-shot refresh after Outlook has been opened as the normal operator account and the expected mailbox is visible:

```powershell
cd "C:\Tools\Export engine"
python -m export_engine.cli store-live-status
python -m export_engine.cli store-live-refresh-once
python -m export_engine.cli store-live-status
```

Do not run historic backfill. Do not enable unattended polling until `store-live-refresh-once` completes with `Errors: 0`.

## Safety invariants

The one-shot refresh remains read-only for Outlook COM and must report:

- Mailbox writes: 0
- Kanban writes: 0
- Cloud/API: 0
- Full mailbox: no
