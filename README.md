# Export Engine

Export Engine is a local Windows Outlook COM export/conversion engine.

It reads the current user's primary Outlook mailbox in read-only mode and converts messages into a local, machine-readable knowledge store under per-user AppData.

## Safety model

- Read-only Outlook mailbox access
- Current user's primary Outlook store by default
- Shared/archive/additional stores excluded by default
- No mailbox writes
- No Kanban writes
- No retained `.msg` or `.eml` files
- No retained raw attachment files
- Evidence store remains local under `%LOCALAPPDATA%`
- Duplicate-safe canonical records
- Resumable backfill
- Attachment extraction sidecars
- Conversation build output
- Retrieval JSONL output
- SQLite recall index

## Intended use

This engine is designed as a local evidence substrate for downstream recall, search, review, and assistant workflows.

The installer should package the engine code only. It must not package mailbox-derived data or local evidence stores.

## Privacy

Mailbox-derived records, indexes, retrieval chunks, attachment extracts, and logs are local runtime artifacts and must not be committed to source control.
