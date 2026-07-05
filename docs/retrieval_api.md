# Generic Retrieval Search API

**Phase 1.8I**

This document describes the stable public retrieval search API exposed by
the Export-Engine local evidence store.

## Purpose

Provide a generic, read-only, deterministic search surface that downstream
repos (e.g. SAMI Retrieval Bridge) can consume without importing internal
engine modules.

## Public Function

```python
from export_engine.retrieval import search, SearchResponse, SearchResult
```

### `search()`

```python
def search(
    query: str,
    max_results: int = 10,
    since_days: int | None = None,
    store_root: str | Path | None = None,
) -> SearchResponse:
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | required | Keyword search query (passed to FTS5 or LIKE) |
| `max_results` | `int` | `10` | Maximum number of results to return |
| `since_days` | `int\|None` | `None` | Recency filter in days (`None` = no filter) |
| `store_root` | `str\|Path\|None` | `None` | Override store root path (`None` = auto-detect) |

**Returns:** [`SearchResponse`](#searchresponse)

**Safety guarantees:**

- ✅ Read-only — never writes to the store
- ✅ Deterministic — same query always returns same results
- ✅ Local-only — no cloud, no API calls
- ✅ Generic — no SAMI, Hermes, Mr Kanban, or Kanban references
- ✅ Tolerant — missing or empty store returns safe empty response with warnings
- ❌ No LLM calls
- ❌ No mailbox writes
- ❌ No Kanban writes

## Response Shape

### SearchResponse

| Field | Type | Description |
|-------|------|-------------|
| `query` | `str` | The original search query |
| `max_results` | `int` | Maximum results requested |
| `since_days` | `int\|None` | Recency window in days (None = no filter) |
| `store_root` | `str` | Resolved store root path used |
| `status` | `str` | One of: `ok`, `empty`, `warning`, `error` |
| `results` | `list[SearchResult]` | Ordered list of results |
| `warnings` | `list[str]` | Non-fatal warnings |
| `result_count` | `int` | Convenience field = `len(results)` |

### SearchResult

| Field | Type | Description |
|-------|------|-------------|
| `record_id` | `str` | Unique chunk or record identifier |
| `source_type` | `str` | Source type (message, attachmentExtract, conversation, etc.) |
| `title` | `str\|None` | Human-readable title or subject |
| `subject` | `str\|None` | Subject line (may duplicate title) |
| `sender` | `str\|None` | Sender/from address (when available) |
| `recipients` | `list[str]` | Recipient addresses |
| `folder_path` | `str\|None` | Source folder path |
| `received_at` | `str\|None` | ISO-8601 received date |
| `sent_at` | `str\|None` | ISO-8601 sent date |
| `conversation_id` | `str\|None` | Conversation grouping key |
| `snippet` | `str` | Short content preview (first 300 chars) |
| `score` | `float` | Deterministic relevance score (higher = better) |
| `content_hash` | `str\|None` | Content hash (when available) |
| `record_path` | `str\|None` | Parent record or chunk path |
| `extract_paths` | `list[str]` | Related attachment extract paths |

## Retrieval Sources

The search function uses these sources in order of preference:

1. **SQLite recall index** (`index/recall.sqlite`) — FTS5 full-text search with LIKE fallback
2. **JSONL retrieval chunks** (`retrieval/chunks_latest.jsonl`) — fallback when SQLite index is missing

Both sources are built from canonical records, attachment extracts, and
conversation summaries. No raw `.msg` or `.eml` files are searched.

## CLI Usage

Two CLI commands use the public API:

### `store-search` (existing)

```bash
python -m export_engine.cli store-search --query "meeting notes" --limit 5 --since-days 90
```

### `retrieval-search` (Phase 1.8I)

```bash
python -m export_engine.cli retrieval-search --query "meeting notes" --max-results 5 --since-days 90
```

Both support `--json` for machine-readable output.

## Example: Python Usage

```python
from export_engine.retrieval import search

# Basic search
response = search(query="meeting notes")
print(f"Status: {response.status}")
print(f"Results: {response.result_count}")

for r in response.results:
    print(f"  {r.title} ({r.score:.1f})")
    print(f"  Path: {r.folder_path}")
    print(f"  Snippet: {r.snippet[:100]}")

# Search with recency filter
response = search(
    query="project update",
    max_results=20,
    since_days=30,
)

# Handle degraded states
if response.warnings:
    for w in response.warnings:
        print(f"Warning: {w}")

if response.status == "error":
    print("Store is not ready — run store-build-index first")
elif response.status == "empty":
    print("No results found")
```

## Downstream Adapter Consumption

Downstream repos (like SAMI Retrieval Bridge) should call
`export_engine.retrieval.search()` rather than importing internal
modules like `export_engine.index.search_index()`.

```python
# ✅ Correct — public stable API
from export_engine.retrieval import search
response = search(query="card evidence")

# ❌ Wrong — imports internal module
from export_engine.index import search_index  # may change without notice
```
