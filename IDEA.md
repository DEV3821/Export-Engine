You are working in:

```text
C:\Tools\Export engine
```

# Phase 1 — Local Knowledge Store Export Engine

## Goal

Build a standalone local Outlook export, conversion, indexing, and recall engine.

This is now its own project, split off from the previous SAMI Kanban Coach work.

Do not call this Phase 8A.

This is:

```text
Phase 1 — Local Knowledge Store Export Engine
```

This is not a chatbot phase.

This is not a Kanban phase.

This is not a UI phase.

This is not an assistant/persona phase.

The goal is to build the core local evidence engine that future knowledge tools can safely use later.

The engine must backfill the current Windows user’s primary Outlook mailbox into a local, machine-readable, searchable, Obsidian-friendly knowledge store, then continue with polling-based near-live incremental refresh after the backfill.

The laptop has enough capacity, so design this as a serious local engine, not a tiny demo.

The engine must be professional, resumable, safe, searchable, verifiable, and local-first.

---

# 1. Strategic Direction

Build the engine first.

The final architecture is:

```text
Current Windows user Outlook profile
  -> primary Outlook store only
  -> all folders under that primary store
  -> one-year backfill
  -> hashed canonical JSON records
  -> parsed attachment extract JSON sidecars
  -> sent/received conversation matching
  -> RAG-ready JSONL chunks
  -> local SQLite recall index
  -> Obsidian Markdown vault projection
  -> Obsidian Canvas visual maps
  -> polling-based near-live refresh
```

This phase creates the local evidence substrate that future tools can query.

The engine must feel like a professional local data repository, not an email dump.

Use neutral naming throughout:

```text
Local Knowledge Store
Outlook Export Engine
Knowledge Store Export Engine
Evidence Store
Recall Index
Retrieval Store
```

Avoid these names completely in code, help text, status output, docs, and tests:

```text
Phase 8A
Mr Kanban
Hermes
chatbot memory
Kanban brain
EmailBrain
email dump
mailbox scrape
raw mailbox export
```

It is acceptable to keep safety wording like:

```text
Kanban write: disabled
Kanban writes: 0
```

because the engine must prove it has not written to any existing Kanban system.

---

# 2. Non-Negotiable Safety Boundaries

The engine must:

* use Outlook COM
* read only the current user’s primary Outlook store
* recursively scan all folders under that primary store
* exclude additional/shared/archive stores by default
* backfill roughly the last year
* support polling-based near-live incremental refresh after backfill
* convert emails into hashed canonical JSON records
* convert attachments into parsed JSON extract sidecars
* match sent and received messages into conversation records
* create RAG-ready JSONL chunks
* create a local SQLite recall index
* automatically maintain an Obsidian-compatible Markdown vault
* automatically maintain Obsidian-compatible `.canvas` visual maps
* store exported evidence under local user AppData
* perform zero Outlook mailbox writes
* perform zero Kanban writes
* perform zero cloud/API calls
* retain no raw `.msg`, `.eml`, or raw attachment files
* avoid writing exported evidence to the repo
* avoid writing exported evidence to OneDrive, Team_ESMI, GitHub, network paths, removable drives, or shared folders by default

The engine must never:

* send emails
* move emails
* delete emails
* mark emails read/unread
* alter Outlook categories
* alter Outlook flags
* alter Outlook folders
* write to Kanban
* call cloud AI/API services
* store raw Outlook `.msg` or `.eml` files
* store raw attachments after parsing
* create persistent raw document copies

---

# 3. Project and Store Paths

Project repo path:

```text
C:\Tools\Export engine
```

Default local evidence store root:

```text
C:\Users\<current_user>\AppData\Local\SAMI\KnowledgeStore\
```

The evidence store must not live inside the repo.

Required local store layout:

```text
KnowledgeStore\
  config\
  catalog\
  records\
  extracts\
  conversations\
  retrieval\
  state\
  runs\
  logs\
  temp\
  vault\
```

Folder meanings:

| Folder          | Meaning                                            |
| --------------- | -------------------------------------------------- |
| `config`        | Local config and safe defaults                     |
| `catalog`       | Source/folder/content catalog manifests            |
| `records`       | Canonical hashed JSON records from Outlook items   |
| `extracts`      | Parsed attachment/content extract JSON sidecars    |
| `conversations` | Matched sent/received conversation JSON            |
| `retrieval`     | RAG-ready JSONL chunks for future knowledge tools  |
| `state`         | Backfill state, refresh state, SQLite recall index |
| `runs`          | Source scans, ingest plans, ingest run manifests   |
| `logs`          | Engine logs                                        |
| `temp`          | Temporary parsing workspace, cleaned after runs    |
| `vault`         | Obsidian-compatible Markdown and Canvas projection |

---

# 4. Persistent Filename Rules

Persistent evidence filenames must be hash-based.

Examples:

```text
records\2026\07\record_<recordKey>.json
extracts\2026\07\record_<recordKey>_extract_01_<extractKey>.json
conversations\2026\07\conversation_<conversationKey>.json
retrieval\chunks_2026_07.jsonl
state\recall_index.sqlite
vault\10_Conversations\2026-07\conversation_<conversationKey>.md
vault\05_Canvases\Project - <safe_project_name>.canvas
```

Do not use email subjects or original attachment names as persistent filenames.

Original display names may appear only as structured metadata where useful:

* email subject
* sender display name
* recipient display names
* attachment display name
* Outlook folder path

---

# 5. Data Strategy

Use:

```text
JSON-first
SQLite-indexed
Markdown-projected
Canvas-visualised
Polling-refreshed
```

Canonical JSON/JSONL files are the durable source of truth:

```text
records\
extracts\
conversations\
retrieval\
```

SQLite is a rebuildable search accelerator:

```text
state\recall_index.sqlite
```

The Obsidian Markdown vault is a rebuildable human-readable projection:

```text
vault\
```

The Obsidian Canvas files are rebuildable visual maps:

```text
vault\05_Canvases\
```

Canvas and Markdown must never become the only source of truth.

If SQLite or vault files are damaged, rebuild from canonical JSON/JSONL.

If JSON records are damaged, the evidence store is damaged.

---

# 6. Required CLI Commands

Add these commands in the project CLI style:

```text
store-status
store-source-scan
store-plan-ingest
store-ingest
store-refresh
store-watch
store-verify
store-search
store-rebuild-index
store-build-vault
store-refresh-vault
store-build-canvas
store-refresh-canvas
store-protect
store-verify-protection
```

Example usage:

```powershell
cd "C:\Tools\Export engine"

.\.venv\Scripts\python.exe -m export_engine.cli store-status

.\.venv\Scripts\python.exe -m export_engine.cli store-source-scan --all-user-folders

.\.venv\Scripts\python.exe -m export_engine.cli store-plan-ingest `
  --all-user-folders `
  --since 2025-07-05 `
  --until 2026-07-05

.\.venv\Scripts\python.exe -m export_engine.cli store-ingest `
  --all-user-folders `
  --since 2025-07-05 `
  --until 2026-07-05 `
  --chunk monthly `
  --parse-extracts `
  --build-retrieval `
  --build-index `
  --build-vault `
  --build-canvas `
  --resume

.\.venv\Scripts\python.exe -m export_engine.cli store-watch --interval-minutes 5

.\.venv\Scripts\python.exe -m export_engine.cli store-verify

.\.venv\Scripts\python.exe -m export_engine.cli store-search "UltraRad"
```

If the current package name is not yet `export_engine`, create that clean package name.

Do not keep old Kanban or assistant branding in new module names, command help, status text, docs, tests, or CLI examples.

Vault and Canvas projection must be enabled by default during ingest and refresh.

The explicit flags may exist for repair, debug, or clarity, but the standard pipeline must update the Markdown vault and Canvas visual maps automatically.

---

# 7. Suggested Package Structure

Create a clean standalone package:

```text
export_engine\
  __init__.py
  cli.py
  config.py
  paths.py
  guards.py
  hashing.py
  schemas.py
  outlook_com_source.py
  fixture_source.py
  source_scan.py
  planning.py
  ingest.py
  refresh.py
  watch.py
  parsers.py
  conversations.py
  retrieval.py
  sqlite_index.py
  vault.py
  canvas.py
  protection.py
  verify.py
  search.py
```

Keep the engine testable without live Outlook by using fixture sources.

---

# 8. Outlook COM Source Scope

Implement:

```text
OutlookComPrimaryStoreSource
```

Scope rule:

```text
Primary user Outlook store only.
No shared mailboxes by default.
No archive stores by default.
No additional mailbox stores by default.
```

Store resolution rule:

1. Connect to Outlook COM.
2. Get the default Inbox folder from the current Outlook profile.
3. Resolve the Store for that default Inbox.
4. Treat that Store as the primary user mailbox store.
5. Call `Store.GetRootFolder()`.
6. Recursively enumerate child folders below that root.
7. Include mail-capable folders.
8. Exclude all other `Namespace.Stores` by default.

Do not perform a broad `NameSpace.Folders` scan by default because that may cross into shared/additional stores.

---

# 9. Folder Scan Requirements

`store-source-scan` must:

* connect to Outlook COM read-only
* resolve the primary user store
* recursively scan all folders under the primary store
* classify folders
* include/exclude based on safe rules
* write a source scan manifest
* update latest catalog file
* perform zero Outlook writes
* perform zero Kanban writes

Write:

```text
runs\source_scan_<timestamp>.json
catalog\source_catalog_latest.json
```

Source catalog schema:

```json
{
  "schemaVersion": "export.sourceCatalog.v1",
  "sourceAdapter": "OutlookComPrimaryStoreSource",
  "scope": "primary_user_store_only",
  "storeDisplayName": "",
  "storeIdHash": "",
  "scannedAt": "",
  "folders": [
    {
      "folderKey": "",
      "folderPath": "\\Inbox",
      "displayName": "Inbox",
      "defaultRole": "inbox",
      "itemCount": 0,
      "included": true,
      "excludedReason": ""
    }
  ],
  "excludedStores": [
    {
      "displayName": "",
      "storeIdHash": "",
      "reason": "additional_store_excluded_by_default"
    }
  ],
  "audit": {
    "mailboxWrite": false,
    "kanbanWrite": false
  }
}
```

---

# 10. Folder Inclusion and Exclusion Rules

Default include:

```text
Inbox
Sent Items
Inbox subfolders
custom user folders
project/process folders
normal mail folders under the primary store
```

Default exclude unless explicitly enabled:

```text
Deleted Items
Junk Email
Drafts
Outbox
Sync Issues
RSS Feeds
Conversation History
Calendar
Contacts
Tasks
Notes
Search Folders
public folders
shared mailbox stores
archive stores
non-mail folders
```

Optional flags:

```text
--include-deleted
--include-junk
--include-drafts
--include-archive-store
--include-shared-stores
```

These must default to false.

---

# 11. Backfill Window

Default backfill window:

```text
last 365 days
```

Allow explicit range:

```text
--since YYYY-MM-DD
--until YYYY-MM-DD
```

For this first build and live smoke/full first run, test with:

```text
2025-07-05 to 2026-07-05
```

Backfill must use monthly chunks and support resume.

---

# 12. Ingest Planning

`store-plan-ingest` must:

* use latest source catalog or run source scan first
* expand selected folders into monthly chunks
* estimate item counts where safe
* estimate extract/attachment counts where safe
* write an ingest plan
* export no records
* save no attachments
* perform zero Outlook writes
* perform zero Kanban writes

Write:

```text
runs\ingest_plan_<timestamp>.json
```

Plan schema:

```json
{
  "schemaVersion": "export.ingestPlan.v1",
  "planId": "",
  "createdAt": "",
  "scope": "primary_user_store_only",
  "storeDisplayName": "",
  "storeIdHash": "",
  "since": "",
  "until": "",
  "chunkMode": "monthly",
  "allUserFolders": true,
  "folders": [],
  "chunks": [],
  "estimatedItems": 0,
  "estimatedExtracts": 0,
  "audit": {
    "mailboxWrite": false,
    "kanbanWrite": false,
    "rawSourceRetained": false
  },
  "warnings": []
}
```

---

# 13. Standard Backfill Ingest Pipeline

Every `store-ingest` run must perform this sequence:

1. Read Outlook COM from the primary user store only.
2. Write/update hashed canonical record JSON.
3. Parse attachments into extract JSON sidecars.
4. Match sent and received items into conversation JSON.
5. Build/update retrieval JSONL chunks.
6. Build/update SQLite recall index.
7. Build/update Markdown vault notes.
8. Build/update Canvas visual maps.
9. Write run manifest.
10. Verify no raw source files remain.
11. Update backfill state.
12. Leave refresh state ready for near-live polling.

`store-ingest` must:

* process selected folders/month chunks
* read Outlook COM only
* write each message as JSON immediately
* parse attachments into extract JSON sidecars
* delete temporary raw extract files
* build conversation records
* build retrieval JSONL chunks
* build/update SQLite recall index
* build/update Markdown vault notes
* build/update Canvas files
* update backfill state
* prepare refresh state
* write an ingest run manifest
* support resume
* avoid duplicate records

Write:

```text
state\backfill_state.json
state\refresh_state.json
runs\ingest_run_<timestamp>.json
```

Ingest must be resilient:

* if a folder fails, record error and continue where safe
* if a single item fails, record warning/error and continue
* if an attachment cannot be parsed, create metadata-only extract JSON with `needsReview=true`
* never silently drop an item or attachment

---

# 14. Incremental Refresh

`store-refresh` must:

* run one safe incremental refresh
* use last successful state per folder
* rescan recent items in included folders
* export new/changed records
* update extracts where needed
* update conversations
* update retrieval chunks
* update SQLite index
* update Markdown vault notes
* update Canvas files
* perform zero mailbox writes
* perform zero Kanban writes
* retain no raw source files

State:

```text
state\refresh_state.json
```

Near-live means periodic polling refresh, not mailbox mutation.

Polling refresh is the source of truth.

Do not rely only on Outlook events.

---

# 15. Watch Mode

`store-watch` must:

* run repeated polling refresh
* default interval: 5 minutes
* support `--interval-minutes`
* support minimum interval of 1 minute
* stop cleanly on Ctrl+C
* print safety status before starting
* perform zero Outlook writes
* perform zero Kanban writes
* retain no raw source files
* update records/extracts/conversations/retrieval/index/vault/canvas on each refresh cycle

Required startup wording:

```text
Near-live local knowledge refresh
Outlook read-only
Mailbox write: disabled
Kanban write: disabled
Raw source retention: disabled
Vault projection: enabled
Canvas projection: enabled
Polling interval: <N> minute(s)
Press Ctrl+C to stop
```

The laptop has enough grunt, so the standard recommended polling interval is 5 minutes, with 1 minute available for aggressive local refresh.

---

# 16. Date Filtering Rules

Use Outlook COM date filtering where practical.

Preferred date fields:

| Folder type            | Preferred date                                                                     |
| ---------------------- | ---------------------------------------------------------------------------------- |
| Inbox/received folders | `ReceivedTime`                                                                     |
| Sent Items             | `SentOn`                                                                           |
| Unknown/custom folders | best available of `ReceivedTime`, `SentOn`, `CreationTime`, `LastModificationTime` |

If folder date filtering fails:

* log warning
* fall back to safe bounded enumeration
* record fallback in manifest

Do not silently skip an item because one date field is missing.

---

# 17. Canonical Record JSON Schema

One canonical JSON file per email-like Outlook item:

```text
records\yyyy\mm\record_<recordKey>.json
```

Required schema:

```json
{
  "schemaVersion": "export.knowledgeRecord.v1",
  "recordType": "outlookMessage",
  "recordKey": "",
  "exportRunId": "",
  "exportedAt": "",
  "source": {
    "system": "Outlook",
    "sourceAdapter": "OutlookComPrimaryStoreSource",
    "scope": "primary_user_store_only",
    "storeDisplayName": "",
    "storeIdHash": "",
    "mailbox": "",
    "folderPath": "",
    "folderKey": "",
    "messageClass": "",
    "direction": "sent | received | unknown",
    "readOnly": true
  },
  "identity": {
    "outlookEntryIdHash": "",
    "internetMessageId": "",
    "conversationId": "",
    "conversationTopic": "",
    "conversationKey": "",
    "contentHash": ""
  },
  "headers": {
    "subject": "",
    "from": {
      "displayName": "",
      "emailAddress": "",
      "emailAddressHash": ""
    },
    "to": [],
    "cc": [],
    "sentDateTime": "",
    "receivedDateTime": "",
    "creationTime": "",
    "lastModificationTime": ""
  },
  "content": {
    "bodyPreview": "",
    "bodyText": "",
    "bodyTextHash": "",
    "htmlStripped": true,
    "quotedTextIncluded": true,
    "cleaningNotes": []
  },
  "extracts": [],
  "classification": {
    "keywords": [],
    "ticketNumbers": [],
    "ipAddresses": [],
    "serverNames": [],
    "aeTitles": [],
    "possibleSystems": [],
    "possibleTopics": []
  },
  "retrieval": {
    "chunkIds": []
  },
  "vault": {
    "notePaths": [],
    "canvasPaths": []
  },
  "audit": {
    "mailboxWrite": false,
    "kanbanWrite": false,
    "rawMsgStored": false,
    "rawSourceRetained": false,
    "parseWarnings": [],
    "needsReview": false
  }
}
```

---

# 18. Extract JSON Schema

Every attachment becomes one extract sidecar JSON:

```text
extracts\yyyy\mm\record_<recordKey>_extract_<n>_<extractKey>.json
```

Required schema:

```json
{
  "schemaVersion": "export.knowledgeExtract.v1",
  "recordType": "outlookAttachmentExtract",
  "parentRecordKey": "",
  "exportRunId": "",
  "extractKey": "",
  "source": {
    "originalName": "",
    "originalNameHash": "",
    "extension": "",
    "sizeBytes": 0,
    "contentHash": ""
  },
  "parse": {
    "status": "parsed | metadata_only | failed | skipped",
    "parser": "",
    "parsedAt": "",
    "failureReason": "",
    "needsReview": false
  },
  "content": {
    "text": "",
    "textHash": "",
    "tables": [],
    "sheets": [],
    "metadata": {}
  },
  "retrieval": {
    "chunkIds": []
  },
  "vault": {
    "notePaths": [],
    "canvasPaths": []
  },
  "audit": {
    "rawSourceRetained": false,
    "tempFileDeleted": true,
    "parseWarnings": []
  }
}
```

Attachment handling rule:

```text
Save raw attachment only to temp\parsing.
Hash it.
Parse it.
Write extract JSON.
Delete temp file.
Verify deletion.
Never retain raw attachment by default.
```

---

# 19. Parser Support

Implement best-effort parsers.

| Type                            | Behaviour                                                                           |
| ------------------------------- | ----------------------------------------------------------------------------------- |
| `.xlsx`, `.xlsm`                | Use `openpyxl`; extract sheet names, used rows, cell values, searchable text        |
| `.csv`                          | Use Python `csv`; extract rows and searchable text                                  |
| `.docx`                         | Use `python-docx` if available, otherwise metadata-only `needsReview=true`          |
| `.pdf`                          | Text extraction if dependency available, otherwise metadata-only `needsReview=true` |
| `.txt`, `.log`, `.xml`, `.json` | Direct text extraction                                                              |
| Images                          | Metadata-only `needsReview=true` unless OCR already exists                          |
| Unknown/binary                  | Metadata-only `needsReview=true`                                                    |

Never silently drop attachments.

---

# 20. All-Context Rule

Implement this as a hard rule in comments, help text, and tests:

```text
All available machine-readable Outlook message and attachment context must be captured.
If something cannot be parsed, record that failure explicitly.
Never silently drop a body, attachment, table, sheet, PDF, image, parse warning, or folder warning.
```

---

# 21. Conversation Matching

The engine must match Sent Items and received items into conversation records.

Do not treat Inbox and Sent Items as isolated evidence pools.

Create:

```text
conversations\yyyy\mm\conversation_<conversationKey>.json
```

Matching priority:

1. Outlook ConversationID / ConversationTopic
2. InternetMessageId, In-Reply-To, References where available
3. Normalised subject
4. Sender/recipient overlap
5. Timestamp proximity
6. Quoted body similarity
7. Attachment filename/hash similarity
8. Ticket/request/change numbers
9. IP addresses, server names, AE titles, project/topic keywords

Required schema:

```json
{
  "schemaVersion": "export.conversation.v1",
  "recordType": "outlookConversation",
  "conversationKey": "",
  "matchMethod": "",
  "conversationId": "",
  "conversationTopic": "",
  "normalisedSubject": "",
  "participants": [],
  "dateRange": {
    "firstMessage": "",
    "lastMessage": ""
  },
  "records": [],
  "extracts": [],
  "classification": {
    "ticketNumbers": [],
    "ipAddresses": [],
    "serverNames": [],
    "aeTitles": [],
    "possibleSystems": [],
    "possibleTopics": []
  },
  "retrieval": {
    "chunkIds": []
  },
  "vault": {
    "conversationNotePath": "",
    "projectNotePaths": [],
    "systemNotePaths": [],
    "peopleNotePaths": [],
    "ticketNotePaths": [],
    "canvasPaths": []
  },
  "audit": {
    "mailboxWrite": false,
    "kanbanWrite": false,
    "needsReview": false,
    "warnings": []
  }
}
```

Conversation records should support later knowledge-tool answers such as:

```text
This thread includes one received request, two sent replies, one attached firewall spreadsheet, and one follow-up mentioning REQ2026637.
```

---

# 22. Retrieval JSONL Schema

Create RAG-ready chunks under:

```text
retrieval\chunks_yyyy_mm.jsonl
```

One JSON object per line.

Required schema:

```json
{
  "schemaVersion": "export.retrievalChunk.v1",
  "chunkId": "",
  "parentRecordType": "record | extract | conversation",
  "parentRecordKey": "",
  "extractKey": null,
  "conversationKey": null,
  "chunkType": "record_header | record_body | extract_text | excel_sheet | excel_table | word_text | pdf_text | plain_text | conversation_timeline | conversation_summary | metadata_only",
  "text": "",
  "metadata": {
    "subject": "",
    "from": "",
    "sentDate": "",
    "receivedDate": "",
    "folderPath": "",
    "folderKey": "",
    "conversationId": "",
    "sourcePath": "",
    "jsonPointer": "",
    "extractName": "",
    "sheetName": "",
    "systems": [],
    "ticketNumbers": [],
    "ipAddresses": [],
    "serverNames": [],
    "aeTitles": [],
    "possibleTopics": []
  },
  "hashes": {
    "textHash": "",
    "sourceContentHash": ""
  }
}
```

Chunking rules:

* use meaningful source units first
* create header/subject chunks
* create body chunks
* create extract chunks
* create Excel sheet/table chunks
* create Word/PDF/text chunks
* create conversation timeline chunks
* create conversation summary chunks
* target around 400–512 tokens for long text
* use 10–20% overlap for long body/PDF text
* do not split spreadsheet rows apart where avoidable
* always include `sourcePath` and `jsonPointer`

Future knowledge tools should use:

```text
C:\Users\<current_user>\AppData\Local\SAMI\KnowledgeStore\retrieval\
```

and/or:

```text
C:\Users\<current_user>\AppData\Local\SAMI\KnowledgeStore\state\recall_index.sqlite
```

---

# 23. SQLite Recall Index

Create:

```text
state\recall_index.sqlite
```

JSON/JSONL remains the source of truth.

SQLite is a rebuildable accelerator.

Required command:

```text
store-rebuild-index
```

Suggested SQLite tables:

```text
records
extracts
conversations
retrieval_chunks
retrieval_chunks_fts
ingest_state
folder_state
vault_notes
canvas_files
```

Index these fields:

* record key
* extract key
* conversation key
* subject
* sender/recipient fields
* sent/received dates
* folder path
* direction
* message class
* ticket numbers
* IP addresses
* server names
* AE titles
* possible systems/topics
* extracted attachment text
* spreadsheet cell text
* conversation timeline text
* vault note paths
* canvas paths
* JSON source path
* content hashes

Use SQLite FTS5 for full-text search where available.

If FTS5 is not available in the local Python SQLite build, fall back to regular indexed text search and record a warning in status/manifest.

---

# 24. Search Command

`store-search "<query>"` must search:

* canonical records
* extract JSON
* conversation JSON
* retrieval JSONL
* SQLite/FTS index where available
* vault notes where useful

Output format:

```text
Matches: N

1. <subject or conversation>
   Date: <date>
   Folder: <folder>
   Direction: sent/received/mixed
   Record key: <recordKey>
   Conversation key: <conversationKey>
   Chunk type: <chunkType>
   Evidence file: <sourcePath>
   Vault note: <notePath>
   Canvas: <canvasPath>
   Snippet: <snippet>
```

It should find:

* email body content
* sent replies
* received messages
* attachment text
* spreadsheet cells
* PDF/Word/text extracts
* conversation timeline text
* ticket numbers
* IP addresses
* AE titles
* server names

---

# 25. Hashing Requirements

Required hashes:

```text
recordKey
conversationKey
extractKey
chunkId
Outlook EntryID hash
folder key
store ID hash
sender/recipient email address hashes
body text hash
record content hash
extract content hash
extract text hash
retrieval chunk text hash
vault note content hash
canvas content hash
```

Do not hash away body or extract text.

Future knowledge tools need readable machine text for recall.

Hash identities and fingerprints, but preserve useful machine-readable content.

---

# 26. Dedupe Requirements

Dedupe behaviour:

* unchanged record: skip rewrite or record as duplicate
* changed record: update JSON and retrieval projection
* duplicate extract content: avoid duplicate sidecar where safe, but preserve parent linkage
* duplicate chunks: avoid repeated chunk writes
* duplicate vault sections: replace generated blocks only
* duplicate canvas nodes/edges: use stable IDs and update in place
* incremental refresh should not re-export unchanged items

Manifest must count duplicates.

---

# 27. Mandatory Obsidian Markdown Vault Projection

The Local Knowledge Store engine must automatically maintain a human-readable Markdown vault projection as part of the standard ingest and refresh process.

This is not optional.

Markdown is not the source of truth.

The source of truth remains:

```text
records\
extracts\
conversations\
retrieval\
state\recall_index.sqlite
```

But every successful ingest or refresh must also update the Markdown vault.

Required vault layout:

```text
KnowledgeStore\
  vault\
    00_Dashboards\
    05_Canvases\
    10_Conversations\
    20_Projects\
    30_People\
    40_Systems\
    50_Tickets\
    90_Review\
    .sami_backups\
```

---

# 28. Vault Design Principles

The vault must be:

* Obsidian-compatible
* local folder only
* Markdown-first
* rebuildable from JSON
* safe to open visually later in Obsidian
* useful for review and management visibility
* not noisy with one note per email by default
* linked by conversations, projects/topics, systems, people, and tickets
* based on evidence, not hallucinated summaries

Do not create one Markdown note per raw email by default.

Prefer:

```text
one note per conversation
one note per project/topic
one note per system
one note per person
one note per ticket/request/change number
dashboard notes
review queue notes
```

---

# 29. Vault Commands

Keep these commands:

```text
store-build-vault
store-refresh-vault
```

These are repair/rebuild commands, not the normal ingest path.

Normal ingest and refresh update the vault automatically.

Command behaviour:

```text
store-build-vault --force
```

Rebuilds the full Markdown vault from JSON/SQLite if notes are missing, damaged, or templates change.

---

# 30. Markdown Note Update Rules

When a new item is exported and belongs to an existing conversation:

1. Update the conversation JSON.
2. Regenerate generated sections of the matching conversation Markdown note.
3. Preserve user notes.
4. Update linked project/system/person/ticket notes.
5. Update dashboards.
6. Update Canvas files.

When a new item starts a new conversation:

1. Create new conversation JSON.
2. Create new conversation Markdown note.
3. Link it to detected projects/systems/people/tickets where possible.
4. Update dashboards and review notes.
5. Update Canvas files.

When a new attachment/extract is parsed:

1. Update parent record JSON.
2. Write extract JSON.
3. Update conversation JSON.
4. Add extract evidence to the conversation Markdown note.
5. Add needsReview/failed extract to review notes if applicable.
6. Update Canvas files if the extract is relevant to a project/system/ticket.

---

# 31. Markdown Frontmatter Rules

Use YAML frontmatter.

Keep properties flat and simple.

Use strings, lists, dates, booleans, and simple numbers.

Avoid deeply nested YAML because Obsidian properties are cleaner with flat fields.

Example:

```yaml
---
type: conversation
schemaVersion: export.vaultNote.v1
conversationKey: d9239fb81ac3312
source: outlook_primary_store
generatedFrom: local_knowledge_store_export_engine
recordCount: 4
extractCount: 2
dateStart: 2026-07-02
dateEnd: 2026-07-05
systems:
  - VPN
  - PACS
  - UltraRad
tickets:
  - REQ2026637
relatedTopics:
  - NT UltraRad Stroke VPN Firewall Rules
rawSourceRetained: false
mailboxWrite: false
kanbanWrite: false
lastBuiltAt: 2026-07-05T15:40:00+10:00
---
```

---

# 32. Generated Markdown Blocks

Markdown notes must use protected generated blocks.

The engine may replace generated blocks:

```markdown
<!-- EXPORT_ENGINE:GENERATED:START summary -->
<!-- EXPORT_ENGINE:GENERATED:END summary -->

<!-- EXPORT_ENGINE:GENERATED:START timeline -->
<!-- EXPORT_ENGINE:GENERATED:END timeline -->

<!-- EXPORT_ENGINE:GENERATED:START evidence -->
<!-- EXPORT_ENGINE:GENERATED:END evidence -->

<!-- EXPORT_ENGINE:GENERATED:START open_actions -->
<!-- EXPORT_ENGINE:GENERATED:END open_actions -->

<!-- EXPORT_ENGINE:GENERATED:START source_records -->
<!-- EXPORT_ENGINE:GENERATED:END source_records -->
```

The engine must preserve manual notes:

```markdown
<!-- EXPORT_ENGINE:USER_NOTES:START -->
User notes go here.
<!-- EXPORT_ENGINE:USER_NOTES:END -->
```

If preserving user notes fails, write the previous note to:

```text
vault\.sami_backups\
```

Then continue safely.

---

# 33. Required Markdown Notes

## Conversation Notes

Path:

```text
vault\10_Conversations\yyyy-mm\conversation_<conversationKey>.md
```

Each conversation note must contain:

```text
YAML frontmatter
summary
timeline
key evidence
open actions
attachments/extracts
related projects/topics
related systems
related people
related tickets
source record keys
manual notes block
```

## Project/Topic Notes

Path:

```text
vault\20_Projects\<safe_project_or_topic_name>.md
```

Each project/topic note must aggregate:

```text
related conversations
recent activity
open actions
key evidence
linked systems
linked people
linked tickets
source conversation keys
possible relationship to later workflow tools
```

## People Notes

Path:

```text
vault\30_People\<safe_person_name>.md
```

Each people note must aggregate:

```text
related conversations
projects/topics mentioned
recent interactions
known systems/topics
```

Do not include private speculation.

Only evidence-derived links and summaries.

## System Notes

Path:

```text
vault\40_Systems\<safe_system_name>.md
```

Each system note must aggregate:

```text
related conversations
recent activity
known tickets
related projects/topics
related people
open issues
```

## Ticket Notes

Path:

```text
vault\50_Tickets\<safe_ticket_or_request_id>.md
```

Ticket examples:

```text
REQ2026637
SRV-3890870
RFC-SAHCHG...
```

Each ticket note must aggregate:

```text
related conversations
source records
extracts
dates
systems
open actions
possible related projects/topics
```

## Dashboards

Required dashboard notes:

```text
vault\00_Dashboards\Local Knowledge Store.md
vault\00_Dashboards\Recent Activity.md
vault\00_Dashboards\Open Actions.md
vault\00_Dashboards\Needs Review.md
```

## Review Notes

Required review notes:

```text
vault\90_Review\Needs Review.md
vault\90_Review\Failed Extracts.md
vault\90_Review\Unmatched Conversations.md
vault\90_Review\Parser Warnings.md
```

---

# 34. Obsidian Links

Use Obsidian wiki links:

```text
[[VPN]]
[[PACS]]
[[UltraRad]]
[[REQ2026637]]
[[NT UltraRad Stroke VPN Firewall Rules]]
[[conversation_d9239fb81ac3312]]
```

Conversation filenames should stay key-based.

Project/topic, person, system, and ticket filenames may use safe display names.

---

# 35. Markdown Safety Rules

The vault must not contain:

```text
.msg
.eml
.xlsx
.xlsm
.docx
.pdf
.png
.jpg
jpeg
.tif
.tiff
raw attachment files
```

The vault may contain:

```text
.md
.canvas
.json metadata if required
Obsidian config if generated later
```

Markdown notes may include readable evidence summaries and snippets, but must not store raw email files or raw attachments.

The vault remains sensitive and must stay under:

```text
C:\Users\<current_user>\AppData\Local\SAMI\KnowledgeStore\vault\
```

Do not sync it to OneDrive, Team_ESMI, GitHub, or shared folders by default.

---

# 36. Mandatory Obsidian Canvas Projection

The Local Knowledge Store engine must generate Obsidian-compatible `.canvas` files as part of the human/management visual layer.

Canvas is not the source of truth.

Markdown is the readable note layer.

Canvas is the visual map layer.

Canvas files live under:

```text
vault\05_Canvases\
```

---

# 37. Canvas Design Rule

Canvas files should mostly use `file` nodes that point to generated Markdown notes.

Do not embed large raw email bodies or attachment text directly into Canvas nodes.

Preferred Canvas node types:

```text
project/topic Markdown note
conversation Markdown note
system Markdown note
person Markdown note
ticket Markdown note
dashboard Markdown note
review Markdown note
small text/group labels where useful
```

Canvas files should be generated from:

```text
canonical JSON
conversation JSON
SQLite index
Markdown vault note paths
```

---

# 38. Required Canvas Files

Generate standard canvases:

```text
vault\05_Canvases\Local Knowledge Overview.canvas
vault\05_Canvases\Recent Activity.canvas
vault\05_Canvases\Open Actions.canvas
vault\05_Canvases\Needs Review.canvas
```

Generate project/topic canvases where related evidence exists:

```text
vault\05_Canvases\Project - <safe_project_or_topic_name>.canvas
```

Generate system canvases where related evidence exists:

```text
vault\05_Canvases\System - <safe_system_name>.canvas
```

Examples:

```text
vault\05_Canvases\Project - NT UltraRad Stroke VPN Firewall Rules.canvas
vault\05_Canvases\System - VPN.canvas
vault\05_Canvases\System - PACS.canvas
```

Do not generate one canvas per raw email.

Prefer:

```text
one canvas per project/topic
one canvas per major system
overview canvas
recent activity canvas
open actions canvas
needs review canvas
```

---

# 39. Canvas Update Behaviour

Every `store-ingest` run must update Canvas files after Markdown vault notes are updated.

Pipeline:

1. Write/update record JSON.
2. Write/update extract JSON.
3. Write/update conversation JSON.
4. Write/update retrieval JSONL.
5. Write/update SQLite index.
6. Write/update Markdown vault notes.
7. Write/update Canvas visual maps.

Every `store-refresh` run must update affected Canvas files when:

```text
a new conversation is created
an existing conversation receives a new sent/received item
a new extract is parsed
a project/topic note changes
a system note changes
a person note changes
a ticket note changes
needsReview/failed extract status changes
dashboards change
```

---

# 40. Canvas Commands

Add repair/rebuild commands:

```text
store-build-canvas
store-refresh-canvas
```

Normal ingest and refresh must update Canvas automatically.

These commands are for repair/rebuild only:

```text
store-build-canvas --force
store-refresh-canvas --since YYYY-MM-DD
```

---

# 41. Canvas File Format

Canvas files must be valid JSON Canvas `.canvas` files.

Top-level shape:

```json
{
  "nodes": [],
  "edges": []
}
```

Use stable deterministic node IDs based on source keys:

```text
project_<projectKey>
conversation_<conversationKey>
record_<recordKey>
extract_<extractKey>
system_<systemKey>
person_<personKey>
ticket_<ticketKey>
dashboard_<dashboardKey>
review_<reviewKey>
```

Use stable deterministic edge IDs:

```text
edge_<fromKey>_<toKey>_<relationshipHash>
```

Canvas node example:

```json
{
  "id": "project_nt_ultrarad",
  "type": "file",
  "x": 0,
  "y": 0,
  "width": 420,
  "height": 220,
  "file": "20_Projects/NT UltraRad Stroke VPN Firewall Rules.md"
}
```

Conversation node example:

```json
{
  "id": "conversation_d9239fb81ac3312",
  "type": "file",
  "x": 520,
  "y": 0,
  "width": 460,
  "height": 220,
  "file": "10_Conversations/2026-07/conversation_d9239fb81ac3312.md"
}
```

Canvas edge example:

```json
{
  "id": "edge_project_nt_ultrarad_conversation_d9239",
  "fromNode": "project_nt_ultrarad",
  "toNode": "conversation_d9239fb81ac3312",
  "label": "evidence"
}
```

---

# 42. Canvas Layout Rules

Use deterministic layout so rebuilds are stable.

Recommended layout for project/topic canvases:

```text
Column 1: Project/topic note
Column 2: Related conversations
Column 3: Extracts/tickets/open actions
Column 4: Systems/people
```

Recommended layout for system canvases:

```text
Column 1: System note
Column 2: Related projects/topics
Column 3: Conversations
Column 4: People/tickets/open actions
```

Recommended layout for overview canvas:

```text
Top: Local Knowledge Store dashboard
Left: active projects/topics
Middle: recent conversations
Right: open actions / needs review
Bottom: systems and people clusters
```

Avoid overlapping nodes.

Use consistent node width/height.

Do not depend on manual dragging for correctness.

---

# 43. Canvas Manual Edit Rule

Generated Canvas files should be treated as generated outputs.

The engine may rewrite generated `.canvas` files during rebuild.

If a generated canvas already exists and is about to be overwritten, optionally back it up to:

```text
vault\.sami_backups\
```

User-custom canvases should go under:

```text
vault\05_Canvases\User\
```

The engine must not overwrite files under:

```text
vault\05_Canvases\User\
```

---

# 44. Canvas Safety Rules

Canvas files must not contain raw attachments.

Canvas files must not contain `.msg` or `.eml`.

Canvas files should point to Markdown notes inside the vault.

Canvas files may contain short labels and relationship text, but should not contain full raw email bodies.

Allowed Canvas content:

```text
file nodes pointing to Markdown notes
small text nodes for labels
group nodes
edges with relationship labels
```

Forbidden Canvas content:

```text
raw email exports
raw attachment paths
direct links to temp files
broad filesystem paths outside KnowledgeStore
OneDrive/Team_ESMI/GitHub paths
```

---

# 45. Local Store Protection

Add optional protection commands:

```text
store-protect
store-verify-protection
```

Protection behaviour:

* confirm store path is under current user AppData
* confirm store path is on local C drive
* remove broad inherited access where safe
* grant access to:

  * current Windows user
  * SYSTEM
  * Administrators
* detect/warn/refuse broad access for:

  * Everyone
  * Users
  * Authenticated Users
  * network/shared groups where detectable

Do not claim:

```text
only the engine can access this folder
```

Use wording:

```text
Access model: current Windows user only
Knowledge tool access: via current user session
NTFS protection: enabled/disabled/unknown
```

---

# 46. Path Guards

Reject store paths under:

```text
OneDrive
Dropbox
Google Drive
Desktop
Downloads
Documents unless explicitly approved in config
USB/removable drives
UNC paths
mapped network drives
Team_ESMI
Git repo
the project repo itself
```

Default root must be:

```text
C:\Users\<current_user>\AppData\Local\SAMI\KnowledgeStore\
```

---

# 47. Raw Source Retention Rules

Persistent store must not contain raw email or raw attachment files.

Allowed persistent extensions:

```text
.json
.jsonl
.sqlite
.log
.md
.canvas
config/state/manifest files
```

Forbidden persistent extensions:

```text
.msg
.eml
.xlsx
.xlsm
.docx
.pdf
.png
.jpg
.jpeg
.tif
.tiff
raw attachment files
```

Temporary raw files are allowed only under:

```text
temp\parsing\
```

They must be deleted after parsing.

Verification must prove:

```text
Raw .msg/.eml stored: 0
Raw attachments retained: 0
```

---

# 48. Status Output

`store-status` should print:

```text
Local Knowledge Store
Source adapter: Outlook COM
Scope: primary user Outlook store only
Persistent format: hashed JSON records
Retrieval folder: KnowledgeStore\retrieval
Local index: KnowledgeStore\state\recall_index.sqlite
Markdown vault: KnowledgeStore\vault
Vault projection: enabled
Canvas projection: enabled
Canvas folder: KnowledgeStore\vault\05_Canvases
Mailbox write: disabled
Kanban write: disabled
Raw source retention: disabled
NTFS protection: enabled/disabled/unknown
Near-live mode: polling incremental refresh, not mailbox mutation
Default polling interval: 5 minutes
Minimum polling interval: 1 minute
```

Avoid wording such as:

```text
email dump
mailbox scrape
raw export
chatbot memory
assistant brain
Kanban brain
```

---

# 49. Future Integration Note

Do not deeply integrate any future knowledge tool in Phase 1.

Document future integration:

```text
Future knowledge tools should not receive broad filesystem access.
Future knowledge tools should read/search only through allow-listed commands or the KnowledgeStore retrieval/index paths.
Profiles alone are not treated as a hard sandbox.
Outlook COM access remains engine-only.
Kanban or external write-back remains a separate gated workflow outside this engine.
```

Future allowed read paths:

```text
KnowledgeStore\retrieval\
KnowledgeStore\state\recall_index.sqlite
```

Future access should preferably go through wrapper commands:

```text
store-search
store-get-record
store-get-conversation
store-get-extract
```

If implementing these helper commands now is cheap, add them. Otherwise document them as future commands.

---

# 50. Run Manifests

Every scan/plan/ingest/refresh run must write a manifest under `runs`.

Source scan:

```text
runs\source_scan_<timestamp>.json
```

Ingest plan:

```text
runs\ingest_plan_<timestamp>.json
```

Ingest run:

```text
runs\ingest_run_<timestamp>.json
```

Refresh run:

```text
runs\refresh_run_<timestamp>.json
```

Ingest manifest should include:

```json
{
  "schemaVersion": "export.ingestRun.v1",
  "exportRunId": "",
  "startedAt": "",
  "finishedAt": "",
  "storeRoot": "",
  "scope": "primary_user_store_only",
  "storeDisplayName": "",
  "storeIdHash": "",
  "since": "",
  "until": "",
  "allUserFolders": true,
  "foldersSeen": 0,
  "foldersIncluded": 0,
  "foldersExcluded": 0,
  "foldersProcessed": [],
  "chunkMode": "monthly",
  "resume": true,
  "limit": null,
  "recordsSeen": 0,
  "recordsExported": 0,
  "recordsSkippedDuplicate": 0,
  "recordsChanged": 0,
  "nonMailItemsSkipped": 0,
  "extractsSeen": 0,
  "extractsParsed": 0,
  "extractsMetadataOnly": 0,
  "extractsFailed": 0,
  "conversationsWritten": 0,
  "retrievalChunksWritten": 0,
  "sqliteRowsWritten": 0,
  "rawMessagesStored": 0,
  "rawSourcesRetained": 0,
  "mailboxWrites": 0,
  "kanbanWrites": 0,
  "refreshStatePrepared": true,
  "vaultProjection": {
    "enabled": true,
    "conversationNotesCreated": 0,
    "conversationNotesUpdated": 0,
    "projectNotesCreated": 0,
    "projectNotesUpdated": 0,
    "systemNotesCreated": 0,
    "systemNotesUpdated": 0,
    "peopleNotesCreated": 0,
    "peopleNotesUpdated": 0,
    "ticketNotesCreated": 0,
    "ticketNotesUpdated": 0,
    "dashboardNotesUpdated": 0,
    "reviewNotesUpdated": 0,
    "manualNoteBlocksPreserved": 0,
    "manualNoteBackupsWritten": 0,
    "warnings": []
  },
  "canvasProjection": {
    "enabled": true,
    "canvasFilesCreated": 0,
    "canvasFilesUpdated": 0,
    "projectCanvasesUpdated": 0,
    "systemCanvasesUpdated": 0,
    "dashboardCanvasesUpdated": 0,
    "reviewCanvasesUpdated": 0,
    "canvasBackupsWritten": 0,
    "warnings": []
  },
  "chunks": [],
  "warnings": [],
  "errors": []
}
```

Refresh manifest should include:

```json
{
  "schemaVersion": "export.refreshRun.v1",
  "refreshRunId": "",
  "startedAt": "",
  "finishedAt": "",
  "storeRoot": "",
  "scope": "primary_user_store_only",
  "pollingMode": true,
  "foldersChecked": 0,
  "recordsSeen": 0,
  "recordsNew": 0,
  "recordsChanged": 0,
  "recordsSkippedDuplicate": 0,
  "extractsParsed": 0,
  "conversationsUpdated": 0,
  "retrievalChunksWritten": 0,
  "sqliteRowsWritten": 0,
  "vaultNotesUpdated": 0,
  "canvasFilesUpdated": 0,
  "rawMessagesStored": 0,
  "rawSourcesRetained": 0,
  "mailboxWrites": 0,
  "kanbanWrites": 0,
  "warnings": [],
  "errors": []
}
```

---

# 51. Testing Requirements

Add or update tests for all major behaviours.

## Naming and Paths

* professional neutral folder naming
* safe default KnowledgeStore path
* unsafe path refusal
* repo path refusal
* OneDrive/Desktop/Downloads/UNC refusal
* persistent filename hash format
* no old assistant/Kanban branding in command help or status output except safety lines

## Source Scan

* source catalog schema
* primary store scope represented in manifests
* fixture additional/shared stores excluded by default
* recursive folder scan
* folder include/exclude rules

## Planning and Resume

* monthly chunk planning
* plan creates chunks for every included folder
* backfill state creation
* refresh state preparation
* resume skips complete chunks
* failed chunk can be retried

## JSON Schemas

* canonical record schema
* extract schema
* conversation schema
* retrieval JSONL schema
* ingest manifest schema
* refresh manifest schema

## Hashing and Dedupe

* stable record hash
* stable extract hash
* stable conversation hash
* stable chunk hash
* duplicate record skip
* changed record update
* duplicate extract handling
* duplicate chunk skip

## Parser Tests

* Excel extraction
* CSV extraction
* DOCX extraction if dependency available
* PDF extraction or metadata-only `needsReview`
* image metadata-only `needsReview` if OCR unavailable
* unknown attachment metadata-only `needsReview`
* temp extract deletion

## Conversations

* sent and received with same ConversationID link into one conversation
* subject/participant/time fallback linking
* unrelated same-subject emails do not link
* conversation retrieval chunks written

## SQLite/Search

* SQLite index creation
* SQLite FTS search where available
* fallback search when FTS5 unavailable
* rebuild index from JSON
* search finds body content
* search finds extract content
* search finds conversation content
* search returns evidence path and snippet
* search returns vault note path where applicable
* search returns canvas path where applicable

## Markdown Vault

* vault folder creation
* ingest automatically creates vault folder
* ingest automatically creates conversation note
* refresh updates existing conversation note when related record arrives
* refresh preserves `EXPORT_ENGINE:USER_NOTES` block
* project/topic note updates when related conversation changes
* system note updates when related conversation changes
* person note updates when related conversation changes
* ticket note updates when related conversation changes
* dashboard notes update after ingest
* review notes include failed extracts
* review notes include needsReview records
* vault rebuild works from canonical JSON
* vault rebuild preserves user notes where possible
* no raw `.msg`/`.eml` in vault
* no raw attachments in vault
* vault note includes source record keys
* vault note includes Obsidian wiki links
* manifest records vault projection counts

## Canvas

* canvas folder creation
* overview canvas creation
* project/topic canvas creation
* system canvas creation
* valid `.canvas` JSON shape with top-level `nodes` and `edges`
* canvas file nodes point to Markdown notes
* stable node IDs
* stable edge IDs
* no raw email body dump in canvas
* no raw attachment paths in canvas
* no `.msg` or `.eml` in canvas
* canvas updates when a new related conversation is ingested
* canvas updates when an existing conversation gets a new sent/received item
* generated canvas backups are written if needed
* user canvases under `vault\05_Canvases\User\` are not overwritten
* manifest records canvas projection counts

## Refresh and Watch

* `store-refresh` performs one polling refresh
* refresh uses `state\refresh_state.json`
* refresh exports new records
* refresh updates changed records
* refresh skips duplicates
* refresh updates conversations/retrieval/index/vault/canvas
* `store-watch` prints required safety banner
* `store-watch` accepts `--interval-minutes`
* `store-watch` supports minimum interval 1 minute
* `store-watch` stops cleanly on Ctrl+C

## Safety

* no mailbox writes
* no Kanban writes
* no cloud/API calls
* no `.msg`
* no `.eml`
* no raw attachments retained
* temp parsing folder cleaned
* protection status detects broad ACLs where testable

---

# 52. Verification Commands

Run:

```powershell
cd "C:\Tools\Export engine"

.\.venv\Scripts\python.exe -m compileall export_engine

.\.venv\Scripts\python.exe -m pytest

.\.venv\Scripts\python.exe -m export_engine.cli store-status

.\.venv\Scripts\python.exe -m export_engine.cli store-source-scan --all-user-folders

.\.venv\Scripts\python.exe -m export_engine.cli store-plan-ingest `
  --all-user-folders `
  --since 2025-07-05 `
  --until 2026-07-05

.\.venv\Scripts\python.exe -m export_engine.cli store-ingest `
  --all-user-folders `
  --since 2025-07-05 `
  --until 2026-07-05 `
  --limit 25 `
  --chunk monthly `
  --parse-extracts `
  --build-retrieval `
  --build-index `
  --build-vault `
  --build-canvas `
  --resume

.\.venv\Scripts\python.exe -m export_engine.cli store-refresh

.\.venv\Scripts\python.exe -m export_engine.cli store-verify

.\.venv\Scripts\python.exe -m export_engine.cli store-search "UltraRad"
```

Optional watch smoke:

```powershell
.\.venv\Scripts\python.exe -m export_engine.cli store-watch --interval-minutes 5
```

For watch mode, confirm the startup safety banner appears, then stop with Ctrl+C.

If full live Outlook testing is too large, run limited live smoke first and fixture tests.

---

# 53. Git Rules

Do not commit:

```text
KnowledgeStore contents
exported records
extracts from real emails
retrieval chunks from real emails
SQLite index from real emails
Markdown vault generated from real emails
Canvas files generated from real emails
logs containing real email content
temp parsing files
```

Commit only:

```text
source code
tests
docs
safe synthetic fixtures
```

Ensure `.gitignore` excludes:

```text
KnowledgeStore/
**/KnowledgeStore/
*.msg
*.eml
*.sqlite
```

Also exclude generated local AppData cache paths if any repo-relative test cache is created.

---

# 54. Acceptance Criteria

Phase 1 is complete when:

1. `store-status` runs and prints safe store status.
2. `store-source-scan --all-user-folders` scans the primary Outlook store only.
3. Additional/shared/archive stores are excluded by default.
4. `store-plan-ingest` creates a resumable monthly plan.
5. `store-ingest` can perform a limited live Outlook COM ingest.
6. Records are written as hashed JSON.
7. Attachments are parsed into extract JSON sidecars.
8. Raw attachments are deleted after parsing.
9. Sent and received messages can be matched into conversation JSON.
10. Retrieval JSONL chunks are written.
11. SQLite recall index is created.
12. Markdown vault is automatically created/updated during ingest.
13. Canvas files are automatically created/updated during ingest.
14. Refresh state is prepared after backfill.
15. `store-refresh` performs a safe polling incremental refresh.
16. `store-watch` runs polling-based near-live refresh.
17. Search can find email body text.
18. Search can find attachment/extract text.
19. Search can find conversation evidence.
20. Search returns evidence path, vault note, and canvas path where applicable.
21. Verification proves no mailbox writes.
22. Verification proves no Kanban writes.
23. Verification proves no `.msg`/`.eml` files are stored.
24. Verification proves no raw attachments are retained.
25. Existing external project/Kanban data is untouched.
26. Tests and compile pass.

---

# 55. First Build Priority

If this phase is too large for one commit, implement in this order:

## 1.1 — Store skeleton and guards

* standalone repo structure under `C:\Tools\Export engine`
* neutral package name
* professional path structure
* status command
* path guards
* `.gitignore`
* schema definitions
* fixture source

## 1.2 — Outlook COM source scan

* primary store resolution
* recursive folder scan
* include/exclude logic
* source catalog

## 1.3 — Backfill planner

* monthly chunks
* plan manifest
* resume state scaffold

## 1.4 — Limited ingest

* record JSON
* hashing/dedupe
* dry-run/limit support
* manifest
* refresh state scaffold

## 1.5 — Extract parsing

* temp attachment save
* parse
* JSON extract sidecars
* delete temp
* verify no raw retention

## 1.6 — Conversations

* sent/received matching
* conversation JSON
* thread/conversation chunks

## 1.7 — Retrieval and SQLite

* retrieval JSONL
* SQLite index
* FTS search where available
* search command

## 1.8 — Markdown vault

* conversation/project/system/person/ticket notes
* dashboards
* review notes
* generated block preservation

## 1.9 — Canvas projection

* overview canvas
* project canvas
* system canvas
* deterministic layout
* stable nodes/edges

## 1.10 — Refresh and watch

* polling refresh
* refresh state
* `store-refresh`
* `store-watch`
* default 5-minute interval
* minimum 1-minute interval
* Ctrl+C shutdown

## 1.11 — Protection and verification

* NTFS protection commands
* verify command
* full test pass
* final SITREP

Do not skip safety verification.

---

# 56. Final SITREP Required

Final response must include:

* phase name
* repo path
* files changed
* commands added
* default store path
* retrieval folder
* SQLite index path
* Markdown vault path
* Canvas folder path
* Outlook COM scope
* whether all primary-store folders are scanned
* folders included/excluded
* default backfill window
* near-live polling behaviour
* default polling interval
* minimum polling interval
* record schema summary
* extract schema summary
* conversation schema summary
* retrieval chunk schema summary
* SQLite tables/FTS summary
* Markdown vault summary
* Canvas projection summary
* parsers implemented
* manifest/resume behaviour
* refresh/watch behaviour
* path guards implemented
* NTFS protection support
* tests run
* pass/fail counts
* whether Outlook mailbox writes occurred
* whether Kanban writes occurred
* whether cloud/API calls occurred
* whether raw `.msg` or `.eml` files were stored
* whether raw attachments were retained
* whether existing external project/Kanban data changed
* git commit hash if committed

Expected safety lines:

```text
Phase name: Phase 1 — Local Knowledge Store Export Engine
Repo path: C:\Tools\Export engine
Mailbox writes: 0
Kanban writes: 0
Cloud/API calls: 0
Raw .msg/.eml stored: 0
Raw attachments retained: 0
Store location: current user local AppData only
Outlook scope: primary user store only
Retrieval folder: KnowledgeStore\retrieval
SQLite index: KnowledgeStore\state\recall_index.sqlite
Markdown vault: KnowledgeStore\vault
Canvas folder: KnowledgeStore\vault\05_Canvases
Near-live polling: implemented / not implemented
Default polling interval: 5 minutes
Minimum polling interval supported: 1 minute
```

---

# 57. Build Discipline

Do not refactor unrelated systems.

Do not add chatbot features.

Do not add Kanban features.

Do not add UI features unless needed for CLI status/output.

Do not add cloud AI/API calls.

Do not mutate Outlook.

Do not write to Kanban.

Do not commit real mailbox-derived data.

Build the engine first.

Keep it boring, professional, local, resumable, searchable, verifiable, and safe.
