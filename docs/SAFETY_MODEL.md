# Safety Model

Export Engine is designed around local-only evidence handling.

## Non-negotiables

- No mailbox writes
- No Kanban writes
- No retained `.msg`
- No retained `.eml`
- No retained raw attachments
- No source-control commits of mailbox-derived data
- Per-user local evidence store only

## Evidence store

Runtime evidence belongs under:

`%LOCALAPPDATA%\SAMI\KnowledgeStore`

The source repository must contain engine code, tests, and documentation only.
