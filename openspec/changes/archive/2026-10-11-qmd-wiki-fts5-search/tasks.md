## 1. Parser — Summary Field

- [x] 1.1 Add `summary: str` field to `WikiPage` dataclass (default empty string)
- [x] 1.2 In `parse_wiki_file()`: extract `summary` from frontmatter if present
- [x] 1.3 In `parse_wiki_file()`: if no frontmatter summary, auto-generate from first non-heading paragraph (first 200 chars at word boundary) via `_auto_summary()`
- [x] 1.4 Add `summary` to `search_text` property so summary content is searchable
- [x] 1.5 In `format_page_for_context()`: show summary as blockquote before markdown body

## 2. Plugin — FTS5 Index

- [x] 2.1 Add `import sqlite3` and `_fts5_db`, `_fts5_available` attributes to `__init__()`
- [x] 2.2 Implement `_check_fts5_available() -> bool`: try creating a test FTS5 table, return True/False
- [x] 2.3 Implement `_build_fts5_index()`: create in-memory SQLite DB, FTS5 virtual table with columns (path, title, tags, content, wikilinks, summary), INSERT all pages
- [x] 2.4 Update `_rebuild_index()` to call `_build_fts5_index()` after parsing pages (if FTS5 available)
- [x] 2.5 Keep old keyword index (`_index` dict) as fallback storage

## 3. Plugin — FTS5 Search

- [x] 3.1 Implement `_build_fts5_query(query: str) -> str`: sanitize input, add prefix wildcards, return FTS5 MATCH string
- [x] 3.2 Rewrite `_search()`: dispatches to FTS5 or keyword fallback
- [x] 3.3 Added `_search_detailed()`: returns (page, excerpt) tuples using FTS5 snippets
- [x] 3.4 Apply confidence weighting: BM25 score divided by confidence weight
- [x] 3.5 Use FTS5 `snippet()` for excerpt generation in search results
- [x] 3.6 Keep keyword search as `_search_keyword()` fallback

## 4. Plugin — Incremental Update with FTS5

- [x] 4.1 Added `_fts5_upsert()`: DELETE + INSERT in FTS5 table for updated pages
- [x] 4.2 Added `_fts5_delete()`: DELETE from FTS5 for deleted files
- [x] 4.3 Updated `_incremental_update()`: calls `_fts5_upsert()` or `_fts5_delete()` alongside keyword index updates

## 5. Plugin — Search Results & System Prompt

- [x] 5.1 Updated `handle_tool_call()` for wiki_search: includes `summary` field and FTS5 snippet as `excerpt`
- [x] 5.2 Updated `handle_tool_call()` for wiki_read: includes `summary` field
- [x] 5.3 Updated `system_prompt_block()`: shows page summaries in catalog
- [x] 5.4 `_format_results()` uses `format_page_for_context()` which includes summary

## 6. Testing

- [x] 6.1 FTS5 availability detection — True on SQLite 3.50.4
- [x] 6.2 FTS5 index builds with all 45 pages
- [x] 6.3 FTS5 search "narrative" returns 5 relevant results with BM25 ranking
- [x] 6.4 FTS5 snippet: useful fragments with [highlighted] terms, not raw truncation
- [x] 6.5 Summary field: 45/45 pages have summaries (from frontmatter or auto-extracted)
- [x] 6.6 Type filter with FTS5: type='comparison' returns 1 matching result
- [x] 6.7 Confidence weighting: mechanism verified, weights {high: 1.5, medium: 1.0, low: 0.7}
- [x] 6.8 Incremental update with FTS5: wiki_write → search → found immediately
- [x] 6.9 Phrase query "memory architecture" returns relevant pages
- [x] 6.10 System prompt catalog shows summaries
- [x] 6.11 Fallback: keyword search works when FTS5 disabled (5 results)
- [x] 6.12 Cleanup: test files removed, index back to 45 pages
