# Installer Readiness

The future installer should package the Export Engine code and command-line entrypoints.

It must not package:

- mailbox-derived records
- attachment extracts
- conversations
- retrieval chunks
- SQLite indexes
- raw attachments
- `.msg`
- `.eml`
- logs containing sensitive mailbox data

## First-run flow

1. Install engine files.
2. Run bootstrap/health checks.
3. Create per-user AppData folder tree.
4. Let the user explicitly run export/resume.
5. Keep all evidence local.

## Upgrade flow

Future versions should use schema versioning and migrations.

## Repair flow

Future repair commands should validate metadata, indexes, chunks, temp files, and forbidden raw evidence files.
