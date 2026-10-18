# QMD Bridge Integration

## Why

The QMD wiki plugin duplicates the search and indexing capabilities of the real QMD tool (github.com/tobi/qmd). The current hand-rolled implementation includes a custom FTS5 SQLite database, keyword matching engine, manual file walking, and incremental update logic — all of which QMD already provides with superior technology (hybrid BM25 + vector similarity + LLM reranking).

This redundant engine was a design error: the plugin should be a thin "Bridge" wrapper that delegates search and indexing to the QMD CLI, not a duplicate implementation.

## What Changes

- Remove the custom FTS5 database, keyword index, and all associated search methods from `__init__.py`
- Replace with delegation to the QMD CLI: `qmd search --json` (BM25 fast path) and `qmd query --json` (hybrid search with reranking)
- Plugin keeps: directory orchestration via `wiki_dirs`, OKF post-processing (type filter, confidence weighting, status exclusion), write tools (wiki_write, wiki_append), session logging (sync_turn), and result shaping for LLM context
- QMD manages its own index at `~/.cache/qmd/index.sqlite` — the plugin calls `qmd update` and `qmd embed` to keep it in sync

## Capabilities

### New Capabilities
- `qmd-bridge-search`: Delegates search to QMD CLI for hybrid BM25 + vector + LLM reranking. Supports fast keyword search (`qmd search`), full hybrid search (`qmd query`), and document retrieval (`qmd get`).

### Removed Capabilities
- `fts5-search`: The hand-rolled SQLite FTS5 database is removed. QMD handles its own indexing internally.
- `keyword-fallback`: No longer needed — QMD provides BM25 as its fast path.

### Modified Capabilities
- `qmd-wiki-indexing`: Index building now delegates to `qmd collection add` + `qmd update` + `qmd embed`. The plugin still manages _-prefix exclusion during file discovery for write operations.
- `wiki-refresh`: Now calls `qmd update` instead of rebuilding the custom FTS5/keyword index.

## Impact

- **Files modified**: `hermes-plugins/qmd-wiki/__init__.py` — stripped from ~1050 lines to ~700 lines of focused bridge code
- **Dependency added**: QMD CLI at `/home/tlhanken/workspace/tools/qmd/bin/qmd` (already built)
- **Performance**: Search quality improves significantly (BM25 + vector similarity + LLM reranking vs word-matching). Index building is slower (QMD indexes into SQLite, generates vectors) but is done once at init and on explicit refresh.
- **No breaking changes**: Tool interfaces (wiki_search, wiki_read, wiki_write, wiki_append, wiki_refresh) unchanged. Config format unchanged. Search results gain QMD's relevance scores.
