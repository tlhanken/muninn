## Why

The QMD wiki memory provider is currently read-only — the agent can search and read wiki pages but cannot create or update them. This means every piece of knowledge the agent generates or discovers must be manually transcribed to the vault by the user. The episodic memory class (Episodic/sessions/) is empty because sync_turn is a no-op. The agent has no way to record decisions, log session activity, or save extracted knowledge without leaving the conversation.

## What Changes

- Add `wiki_write` tool: create or update a wiki page with auto-generated frontmatter. The agent specifies title, content, tags, type, confidence, and which configured directory to write to. File names are slugified per SCHEMA convention (lowercase, hyphens). Wikilinks are auto-extracted and stored.
- Add `wiki_append` tool: append content to an existing wiki page, optionally under a new section header. Useful for logs, decision records, and incremental knowledge accumulation.
- Implement `sync_turn()`: lightweight session logging to `Episodic/sessions/`. On first call per session, creates a session file with frontmatter. On subsequent calls, appends a timestamped entry with a truncated summary of the turn. This populates episodic memory and makes session history searchable.
- Add incremental index update: after wiki_write or wiki_append, the affected page is re-parsed and the in-memory index is updated without a full rebuild.
- Add `_slugify()` helper: converts titles to SCHEMA-compliant filenames (lowercase, hyphens, no spaces or special chars).
- Add `_generate_frontmatter()` helper: builds YAML frontmatter with title, tags, type, confidence, status, created, updated dates.

## Capabilities

### New Capabilities
- `wiki-write-tool`: Create or update wiki pages with auto-generated frontmatter, slugified filenames, and automatic index refresh
- `session-logging`: sync_turn writes timestamped session entries to Episodic/sessions/, creating episodic memory that is searchable via wiki_search
- `incremental-index-update`: After writes, the affected page is re-parsed and the index updated in-place without a full directory rescan

### Modified Capabilities
- `qmd-wiki-indexing`: The index now supports incremental updates from write operations, not just full rebuilds from wiki_refresh

## Impact

- **Code**: `hermes-plugins/qmd-wiki/__init__.py` — wiki_write, wiki_append, sync_turn, incremental index update, slugify/frontmatter helpers. `hermes-plugins/qmd-wiki/parser.py` — add `write_wiki_file()` and `append_to_wiki_file()` functions for file I/O with frontmatter generation.
- **Config**: No config changes needed. Writes go to directories already in `wiki_dirs`.
- **Tools**: Two new tools (`wiki_write`, `wiki_append`) added to `get_tool_schemas()`.
- **No breaking changes**: Existing tools (`wiki_search`, `wiki_read`, `wiki_refresh`) unchanged. sync_turn going from no-op to active logging is additive — new files in Episodic/sessions/ will be indexed on next refresh.
- **File safety**: wiki_write refuses to write outside configured wiki_dirs. wiki_append refuses to modify files that aren't already in the index. Both validate paths against directory traversal.
