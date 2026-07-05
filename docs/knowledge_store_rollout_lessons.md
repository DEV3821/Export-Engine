# Knowledge Store Rollout Lessons

Captured during Phase 1 backfill and refinement of the SAMI Outlook KnowledgeStore Export Engine.

> **Project:** SAMI Outlook KnowledgeStore Export Engine
> **Repo root:** `C:\Tools\Export engine`
> **Evidence store:** `%LOCALAPPDATA%\SAMI\KnowledgeStore\`

---

## 1. Full reprocessing is expensive and must not be required for derived fixes

Historic backfill over 178 source folders, 12K+ records, and 52K chunks is a multi-hour operation. Fixes to derived artefacts (conversations, chunks, SQLite index, vault notes, dashboards) must be achievable by offline rebuild from the canonical record JSON files — without touching Outlook again.

**Rule:** Derived outputs are rebuildable from `records/` only. The `store-rebuild-derived --offline` command must do this deterministically.

## 2. Offline derived rebuild must exist for all derived layers

The system has several derived layers that can drift out of sync:

- Conversation groupings (`conversations/`)
- Retrieval chunks (`retrieval/`)
- SQLite recall index (`index/recall.sqlite`)
- Vault Markdown notes (`vault/`)
- Dashboards (`vault/00_Dashboards/`)

Each must have an offline rebuild path that does not call Outlook COM and does not re-export. The `store-rebuild-derived --offline` command covers all five.

## 3. Empty Obsidian vault is a hard fail if records/chunks exist and vault output is enabled

If the vault folder scaffold exists but contains 0 Markdown notes while there are 12K+ records and 52K chunks on disk, the validator must fail. The vault is the primary evidence-review surface for downstream tools (Mr Kanban evidence sessions). An empty vault means evidence is invisible.

**Validator rule:** `requireVaultNoteCountGtZeroIfVaultEnabled`.

## 4. Conversation-key consistency must be validated before downstream evidence sessions

A conversation key in a canonical record must join to a real conversation JSON file. Every conversation must have at least one record. Every chunk must join to a valid record or valid conversation. Orphan records, orphan conversations, and orphan chunks indicate state corruption.

**Validator:** Cross-join `records/` → `conversations/` → `retrieval/` → `index/recall.sqlite` and report every mismatch.

## 5. Fixture/test data must never leak into real AppData KnowledgeStore

During development, test fixture runs write to `%LOCALAPPDATA%\SAMI\KnowledgeStore` by default. Test data (e.g. "Fixture message" subjects, synthetic email addresses) must never appear in production vault notes, search results, or recall queries.

**Countermeasure:** Fixture writes must only go to temp directories. A quarantine command scans for fixture markers and moves suspect records out of the live store.

## 6. Folder paths must be canonical and must not include store display name prefixes

Store paths must be relative to the store root:

| Correct | Incorrect |
|---------|-----------|
| `\Inbox` | `\Brian.Shaw@sa.gov.au\Inbox` |
| `\Sent Items` | `mailbox@example.com\Sent Items` |
| `\Inbox\SubTeam` | `\Primary\Inbox\SubTeam` |

Store-prefixed paths break folder-key joins between records, conversations, chunks, vault notes, and SQLite rows. The validator rejects them.

## 7. Duplicate-only chunks are terminal only if existing canonical records are verified

A chunk containing only duplicate-skipped items is a non-issue if the corresponding canonical records already exist from a prior chunk. The fast-path duplicate skip is correct. But if a full chunk is marked "complete" with 0 records exported and the destination record path is empty, that is a problem.

**Rule:** Chunks can be "complete" with 0 exports only when the target records already exist.

## 8. Partial/splitting/pending states must remain visible

No "all clear" wording when partial or splitting chunks exist. The health report shows every status explicitly. The validator fails if status wording hides partials.

## 9. Attachments must have explicit status

Attachment parsing was deferred in Phase 1 (0 extract JSON files). This must be recorded clearly in every report, manifest, and vault note:

```
attachmentExtractMode: deferred
extractsCreated: 0
attachmentParsingDeferred: true
```

The validator fails if attachment status is absent or ambiguous.

## 10. Sent Items is mandatory for full-picture evidence

An evidence store that only captures Inbox misses the outbound side of work conversations: replies, clarifications, decisions, follow-ups, operator actions. Sent Items links into conversations with received messages via ConversationID, normalised subjects, participants, and timestamps.

**Rule:** Sent Items is included by default. Validator fails if live mode explicitly excludes Sent Items without override.

## 11. Live refresh must include Sent Items, not only Inbox

The near-live incremental refresh polls both Inbox-side folders AND Sent Items. High-watermarks for Sent Items are tracked separately. live-status reports Sent Items included as a boolean.

## 12. Outlook COM reads must be visibly gated and read-only

Only `live-refresh-once` instantiates Outlook COM. All offline commands (`audit-offline`, `analyse-state --offline`, `rebuild-derived --offline`, `build-vault --offline`, `validate --offline`) must fail visibly if COM is accidentally requested. All safety reports confirm `outlookComUsed: false`.

## 13. Primary store detection must be validated per user

The export engine resolves the default store via `GetNamespace("MAPI").DefaultStore`. This must be validated before live refresh is enabled. Shared stores, archive stores, and imported PSTs are excluded by default.

## 14. Shared/archive/imported PST stores must be excluded by default

Extended stores (shared mailboxes, archive mailboxes, imported PSTs) contain content that may not belong in the user's local evidence store. They are excluded unless explicitly enabled via config override.

## 15. Team rollout should default to validate-first, then live incremental

New user deployments of the export engine run:
1. `store-validate --offline` (verifies existing store health)
2. `store-live-enable` (turns on polling after validation passes)
3. `store-live-refresh-once` (first incremental run)
4. `store-live-status` (confirm state)

No automatic full backfill. No silent live start.

## 16. No mailbox write, no Kanban write, no cloud/API by default

Safety invariants enforced by code and by test:
- `mailboxWrites` = 0
- `kanbanWrites` = 0
- `cloudApiCalls` = 0
- `rawSourceRetained` = 0

These are checked by every health report, every validator run, every CLI command output, and every vault note YAML frontmatter.

## 17. A local evidence store must be safe to rebuild from canonical exports without touching Outlook

The entire derived store (conversations, chunks, SQLite, vault, dashboards) must be rebuildable from `records/` alone. A user with 12K exported records on disk but no Outlook connection can:
- rebuild conversations
- rebuild retrieval chunks
- rebuild recall.sqlite
- rebuild vault notes
- rebuild dashboards
- run validation
- run search/query

This guarantees the store is self-contained.

## 18. This export engine must remain separate from Mr Kanban/Hermes UI layers

The export engine produces evidence. Mr Kanban consumes it. Hermes indexes it. These are separate concerns in separate repos. The export engine's job ends at providing the local evidence substrate — it does not render cards, write to Kanban boards, summarise with LLM, or maintain chatbot state.
