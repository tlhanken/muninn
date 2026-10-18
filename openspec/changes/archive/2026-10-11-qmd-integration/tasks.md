# QMD Bridge Integration — Tasks

## 1. OpenSpec Change

- [x] 1.1 proposal.md — written
- [x] 1.2 design.md — written
- [x] 1.3 specs/bridge-search.md — written
- [x] 1.4 tasks.md — this file

## 2. Rewrite `__init__.py` — QMD Bridge

- [x] 2.1 Strip FTS5 imports, FTS5 methods, keyword index, all search methods
- [x] 2.2 Add `_QMD_BIN` constant, `_run_qmd()` subprocess wrapper
- [x] 2.3 Add `_init_collections()` — QMD collection setup for wiki_dirs
- [x] 2.4 Rewrite `_search()` — delegates to `qmd search --json`
- [x] 2.5 Rewrite `_rebuild_index()` → `_scan_pages_for_catalog()` — lightweight file discovery, delegates to `qmd update`
- [x] 2.6 Rewrite `_find_page()` — reads directly from filesystem with fallback to qmd get
- [x] 2.7 Update `wiki_refresh` — calls `qmd update`
- [x] 2.8 Update `handle_tool_call` — use new search layer
- [x] 2.9 Update `prefetch/queue_prefetch` — use new search layer
- [x] 2.10 Update `system_prompt_block` — use lightweight catalog

## 3. Update parser.py

- [x] 3.1 Verify compatibility with QMD — parser produces valid markdown that QMD can index
- [x] 3.2 No changes needed — parser is pure file I/O and frontmatter handling

## 4. Testing

- [x] 4.1 Plugin loads without errors (no sqlite3 import issues)
- [x] 4.2 Provider initializes and sets up QMD collections
- [x] 4.3 wiki_search returns results from QMD (BM25 fast path)
- [x] 4.4 OKF type filter works as post-processing
- [x] 4.5 wiki_write creates files on disk
- [x] 4.6 wiki_read returns page content
- [x] 4.7 Old config loads correctly
- [x] 4.8 Prefetch returns context
- [x] 4.9 Cleanup test files

## 5. Closeout

- [x] 5.1 Update living spec at `openspec/specs/qmd-wiki-memory-provider/spec.md`
- [x] 5.2 Mark FTS5 change as superseded (`openspec/changes/qmd-wiki-fts5-search/proposal.md`)
- [x] 5.3 Mark qmd-integration tasks complete
- [x] 5.4 Update `qmd-wiki-development` skill with completed architecture
