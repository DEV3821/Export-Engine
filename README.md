# Engine Exporter — Local Mailbox Export Engine

Local-first, read-only Outlook mailbox export, conversion, and indexing engine.
Produces a structured local Knowledge Store suitable as an evidence substrate
for downstream tools.

## Scope

- Read-only Outlook COM access to the current user's primary store only
- Recursive folder scan under the primary Outlook store
- Backfill of roughly one year
- Polling-based near-live refresh
- Hashed JSON record output
- Attachment parsing into JSON sidecars
- Markdown vault, retrieval chunks, SQLite recall index

## Safety Guarantees

| Constraint                   | Status                |
|------------------------------|-----------------------|
| Mailbox writes               | Disabled              |
| Kanban writes                | Disabled              |
| Cloud/API calls              | Disabled              |
| LLM usage                    | No                    |
| Raw source retention         | Disabled              |
| Scope                        | Primary user store only |
| Outlook COM access mode      | Read-only             |

## Default Store Path

```
C:\Users\<user>\AppData\Local\SAMI\KnowledgeStore\
```

This is a **legacy-compatible** path (inherited from an earlier project name).
Path migration to `%LOCALAPPDATA%\EngineExporter\KnowledgeStore` can be
considered in a future phase with backup/restore tests.

## CLI

```bash
python -m export_engine.cli store-status
python -m export_engine.cli store-verify
python -m export_engine.cli store-validate
python -m export_engine.cli store-live-status
python -m export_engine.cli store-live-enable
python -m export_engine.cli store-live-refresh-once
```

## Live Export Runner

PowerShell:

```powershell
.\scripts\start_live_export.ps1 -StatusOnly
.\scripts\start_live_export.ps1 -Enable
.\scripts\start_live_export.ps1 -Once
.\scripts\start_live_export.ps1 -Watch
```

Command Prompt (BAT):

```cmd
scripts\start_live_export.bat status
scripts\start_live_export.bat enable
scripts\start_live_export.bat once
scripts\start_live_export.bat watch
```

## Documentation

- [Operator Live Export Guide](docs/operator_live_export.md)

## Project Structure

```
export_engine/
    __init__.py
    cli.py           — CLI entry point
    config.py        — Default configuration
    paths.py         — Store path resolution
    guards.py        — Path and safety guards
    hashing.py       — Deterministic hash helpers
    schemas.py       — Schema dataclasses/factories
    fixture_source.py— Synthetic source adapter for tests
    verify.py        — Store verification logic
    bridge.py        — Evidence bridge retrieval
    query_adapter.py — Local evidence query adapter
    guided_session.py— Guided card evidence sessions
    offline.py       — Offline audit/analyse/rebuild/validate
    live.py          — Near-live incremental refresh
    vault.py         — Markdown vault builder
tests/
    test_paths.py
    test_guards.py
    test_hashing.py
    test_schemas.py
    test_cli_status.py
    test_fixture_source.py
scripts/
    start_live_export.ps1
    start_live_export.bat
docs/
    operator_live_export.md
```
