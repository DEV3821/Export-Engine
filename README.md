# Local Knowledge Store Export Engine

Phase 1 of a local-first Outlook export, conversion, and indexing engine.

## Scope

- Read-only Outlook COM access to the current user's primary store only
- Recursive folder scan under the primary Outlook store
- Backfill of roughly one year
- Polling-based near-live refresh (future phase)
- Hashed JSON record output
- Attachment parsing into JSON sidecars
- Markdown vault, Canvas maps, retrieval JSONL, SQLite index

## Safety Guarantees

| Constraint            | Status  |
|-----------------------|---------|
| Mailbox writes        | Disabled|
| Kanban writes         | Disabled|
| Cloud/API calls       | Disabled|
| Raw source retention  | Disabled|
| Scope                 | Primary user store only|

## Default Store Path

```
C:\Users\<user>\AppData\Local\SAMI\KnowledgeStore\
```

## CLI

```bash
python -m export_engine.cli store-status
python -m export_engine.cli store-verify
```

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
tests/
    test_paths.py
    test_guards.py
    test_hashing.py
    test_schemas.py
    test_cli_status.py
    test_fixture_source.py
```
