# Engine Exporter — Live Export Operator Guide

## What is Engine Exporter?

**Engine Exporter** is a local, read-only Outlook mailbox export and conversion
engine.  It produces a structured local Knowledge Store of hashed JSON records,
conversation groupings, retrieval chunks, a SQLite recall index, and a Markdown
vault — all from a single Outlook profile.

The engine is generic and can serve as an evidence substrate for different
downstream tools.  It is not tied to any specific assistant, chatbot, or
project management system.

## What live export does

Live incremental refresh polls the configured Outlook folders at a regular
interval (default: every 5 minutes).  Each cycle:

1. Checks for new or changed items in included folders using high-watermarks.
2. Exports new/changed items as deterministic hashed JSON records.
3. Rebuilds derived outputs (conversations, retrieval chunks, SQLite index,
   Markdown vault) from the updated record set.
4. Records metrics (new records, changed records, duplicates skipped, errors).

## What live export does NOT do

- Does **not** write to the mailbox.
- Does **not** write to any external system.
- Does **not** make cloud/API calls.
- Does **not** use an LLM or AI model.
- Does **not** retain raw `.msg` or `.eml` files.
- Does **not** retain raw attachments.
- Does **not** bypass Outlook security or credentials.
- Does **not** access shared, archive, or other people's stores unless
  explicitly configured and authorised (not implemented in this phase).

## How to check status

### PowerShell

```powershell
cd "C:\Tools\Export engine"
.\scripts\start_live_export.ps1 -StatusOnly
```

### Command Prompt (BAT)

```cmd
cd "C:\Tools\Export engine"
scripts\start_live_export.bat status
```

This shows:

- Whether live refresh is enabled.
- Polling interval.
- Included folders and whether Sent Items is included.
- High-watermarks per folder.
- Last run timestamp.
- New, changed, and duplicate-skipped counts for the last run.
- Store path, recall DB path, vault path, quarantine path.
- Safety flags: mailbox writes, Kanban writes, cloud/API calls, LLM usage,
  Outlook COM mode, raw message/attachment retention.

## How to enable live refresh

### PowerShell

```powershell
.\scripts\start_live_export.ps1 -Enable
```

### BAT

```cmd
scripts\start_live_export.bat enable
```

This validates the offline store first, then enables polling incremental
refresh.  Live refresh will run automatically at the configured interval.

## How to run one cycle

### PowerShell

```powershell
.\scripts\start_live_export.ps1 -Once
```

### BAT

```cmd
scripts\start_live_export.bat once
```

This runs one incremental refresh cycle now, then shows the updated status.
The cycle reads Outlook COM (read-only), exports new/changed items, and
rebuilds derived outputs.

## How to watch live refresh

### PowerShell

```powershell
.\scripts\start_live_export.ps1 -Watch
```

### BAT

```cmd
scripts\start_live_export.bat watch
```

This loops at the configured polling interval, running one refresh cycle per
iteration and showing status after each cycle.  Press **Ctrl+C** to stop.

## Where local data is stored

All exported data lives under the user's local AppData:

```
%LOCALAPPDATA%\SAMI\KnowledgeStore\
```

This path is **legacy-compatible** (inherited from an earlier project name).
A future migration phase may move it to:

```
%LOCALAPPDATA%\EngineExporter\KnowledgeStore\
```

Do not move or rename the store folder manually — the engine expects this path.

Store subfolder layout:

| Subfolder       | Contents                                      |
|-----------------|-----------------------------------------------|
| `records/`      | Hashed JSON records (one per exported item)   |
| `extracts/`     | Attachment extract JSON sidecars              |
| `conversations/`| Conversation grouping JSON                    |
| `retrieval/`    | Retrieval chunk JSONL                         |
| `index/`        | SQLite recall index (`recall.sqlite`)         |
| `vault/`        | Markdown vault notes                          |
| `catalog/`      | Source folder catalog                         |
| `state/`        | Backfill and refresh state                    |
| `runs/`         | Run manifests                                 |
| `logs/`         | Log files                                     |
| `temp/`         | Temporary files (cleared after use)           |
| `quarantine/`   | Quarantined fixture/test data                 |

## Safety invariants

Every command confirms:

| Safety check                   | Status |
|--------------------------------|--------|
| Mailbox writes                 | 0      |
| Kanban writes                  | 0      |
| Cloud/API calls                | 0      |
| LLM used                       | no     |
| Outlook COM write              | no (read-only) |
| Raw .msg/.eml retention        | no     |
| Raw attachment retention       | no     |

## Authorisation warning — other people's mailboxes

The Engine Exporter connects to the mailbox available to the **active Outlook
profile** only.  Exporting another person's mailbox requires:

- Proper authorisation (legal/regulatory compliance, data subject consent).
- Explicit Outlook profile or delegate access configuration.
- The tool must not bypass credentials, permissions, or organisational policy.

**Default mode:** current user primary store only.

Shared, archive, archive mailbox, and additional stores are excluded by default
unless a future explicit authorised configuration enables them.

## Known limitations

- One Outlook profile at a time.
- Near-live polling, not push/event-driven.
- High-watermarks reset if the live state file is deleted or corrupted.
- Attachment parsing is deferred (metadata captured, binary extracted later).
- Shared/archive stores are excluded by default.
- Multi-mailbox export not yet implemented.
- Path migration from `%LOCALAPPDATA%\SAMI\` is pending a future phase.

## How to stop Watch mode

Press **Ctrl+C** in the terminal where the script is running.

To fully disable live refresh:

```powershell
python -m export_engine.cli store-live-disable
```

## Related CLI commands

```bash
python -m export_engine.cli store-live-status
python -m export_engine.cli store-live-enable
python -m export_engine.cli store-live-disable
python -m export_engine.cli store-live-refresh-once
```

## Recommended next steps after this phase

1. Verify safety flags in `store-live-status` output.
2. Enable live refresh with `-Enable`.
3. Monitor the first few cycles with `-Watch`.
4. Review the generated vault notes and retrieval chunks.
5. Plan downstream integration (evidence pack bridge, review tooling).
