## Context

Phase 1 gave the QMD wiki plugin multi-directory indexing, OKF-aware search, wikilink extraction, and underscore-prefix exclusion. The plugin is read-only — it can search and read but not write. The `sync_turn()` method is a no-op, meaning episodic memory (Episodic/sessions/) is never populated automatically.

The vault has CoALA memory class directories ready: Wiki/, Research/, Procedures/, Executive/, Episodic/sessions/, Episodic/decisions/, Users/trevor/, Agents/Sera/, etc. All are in the `wiki_dirs` config and indexed for search. But no mechanism exists for the agent to add content to them.

## Goals / Non-Goals

**Goals:**
- Agent can create new wiki pages with proper frontmatter via `wiki_write` tool
- Agent can append to existing pages via `wiki_append` tool
- Session activity is logged to Episodic/sessions/ automatically via sync_turn
- Written pages appear in search immediately (incremental index update)
- File naming follows SCHEMA convention (lowercase, hyphens)
- Writes are confined to configured wiki_dirs (no path traversal)

**Non-Goals:**
- Automatic knowledge extraction from conversations (LLM-based summarization, concept detection) — deferred to Phase 3 / dreaming pipeline
- Conflict resolution for concurrent writes (single-agent assumption)
- File watching / auto-reindex on external changes
- Write permissions per-directory (all wiki_dirs are writable)
- Git versioning of wiki files (vault-side concern)

## Decisions

### Decision 1: wiki_write creates files; doesn't update in-place

**Choice**: wiki_write creates a new file if the slugified title doesn't exist. If it does exist, wiki_write updates the file (replaces content, preserves created date, bumps updated date, merges tags).

**Alternatives considered**:
- wiki_write only creates, never updates (rejected: agent would need a separate update tool, adds complexity)
- wiki_write always overwrites (rejected: loses created date and tag history)

**Rationale**: Create-or-update is the natural semantics for a knowledge base. The agent doesn't need to know if a page exists — it writes what it knows, and the tool handles the rest. Preserving created date and merging tags maintains provenance.

### Decision 2: Directory routing by basename

**Choice**: wiki_write takes an optional `directory` parameter (basename of one of wiki_dirs, e.g., "Wiki", "Episodic", "Procedures"). If not specified, defaults to the first wiki_dir. The plugin resolves this to the full path by matching against configured wiki_dirs.

**Alternatives considered**:
- Full path parameter (rejected: security risk — agent could write anywhere)
- Memory class enum (rejected: couples plugin to CoALA taxonomy; directory names are more flexible)
- Auto-routing by type field (rejected: type → directory mapping is a policy decision, not a plugin concern)

**Rationale**: Basename matching is simple and safe — the agent can only write to directories already in the config. No path traversal possible. The agent sees directory names in the system prompt catalog, so it knows what's available.

### Decision 3: sync_turn writes session logs, not extracted knowledge

**Choice**: sync_turn appends a timestamped entry to `Episodic/sessions/<session-slug>.md`. The entry contains a truncated summary of the user and assistant messages (first 200 chars each), not the full content. No LLM processing — pure file I/O.

**Alternatives considered**:
- sync_turn does nothing, rely on explicit wiki_write calls (rejected: episodic memory would remain empty unless agent proactively writes)
- sync_turn runs LLM extraction to identify knowledge worth saving (rejected: sync_turn must be non-blocking. LLM calls are blocking and expensive. This belongs in the dreaming pipeline.)
- sync_turn writes full conversation transcripts (rejected: too much data, pollutes search index with raw chat)

**Rationale**: A lightweight session log creates searchable episodic memory without LLM processing. The agent can later use wiki_write to save specific insights. The dreaming pipeline (Phase 3+) can process session logs for extraction. Truncation keeps entries compact — the log is an index of what happened, not a transcript.

### Decision 4: Incremental index update, not full rebuild

**Choice**: After wiki_write or wiki_append, the affected file is re-parsed and the index is updated for just that page. No full directory rescan.

**Alternatives considered**:
- Call _rebuild_index() after every write (rejected: O(n) for every write. With 45+ pages, this is fast now but won't scale.)
- Don't update index, rely on next wiki_refresh (rejected: written page won't appear in search until manual refresh — confusing UX)

**Rationale**: Incremental update is O(1) per write. The page is parsed once, its words are added/updated in the word index, and the page list is updated. This is simple to implement correctly because each write affects exactly one file.

### Decision 5: File naming via slugify

**Choice**: `_slugify(title)` converts page titles to SCHEMA-compliant filenames: lowercase, spaces → hyphens, strip non-alphanumeric (except hyphens), max 80 chars, append `.md`.

**Alternatives considered**:
- Use title as-is (rejected: spaces and special chars in filenames cause issues)
- Hash-based names (rejected: not human-readable in the filesystem)
- Manual filename parameter (rejected: agent shouldn't need to think about filenames)

**Rationale**: SCHEMA already specifies "lowercase, hyphens, no spaces." Slugify is a well-known pattern. The title field in frontmatter preserves the human-readable form.

### Decision 6: Frontmatter generation in parser.py

**Choice**: Add `write_wiki_file()` and `append_to_wiki_file()` to parser.py. These handle frontmatter generation, file I/O, and content formatting. The plugin calls these functions from the tool handlers.

**Alternatives considered**:
- Put file I/O in __init__.py (rejected: parser.py already owns the WikiPage data model and frontmatter parsing — writing is the inverse operation)
- Separate writer module (rejected: over-modularization for ~50 lines of code)

**Rationale**: parser.py is the right home — it already has `parse_frontmatter()` and `parse_wiki_file()`. Adding the inverse operations keeps file format logic in one place.

## Risks / Trade-offs

- [Agent writes garbage] → The agent could write low-quality pages. Mitigated by: confidence field (default medium), the dreaming pipeline (Phase 3) can review and demote, status field can mark pages as rejected.
- [Session log noise] → sync_turn writes a file every turn. With many turns, session files grow. Mitigated by: truncated entries (200 chars), session files are per-session (not one giant file), janitorial cron (future) can archive old sessions.
- [Concurrent writes] → If two agents write to the same file simultaneously, data could be lost. Not a concern in practice — each profile runs independently, and writes to shared directories are to different files (different topics). The threading lock in _rebuild_index protects the in-memory index.
- [Index drift] → If a file is modified externally (Obsidian), the in-memory index won't reflect changes until wiki_refresh. This is the same as Phase 1 behavior — not a regression.

## Migration Plan

1. Add `write_wiki_file()`, `append_to_wiki_file()`, `_slugify()` to parser.py
2. Add `wiki_write` and `wiki_append` tool schemas to __init__.py
3. Implement `handle_tool_call()` for wiki_write and wiki_append
4. Implement `_incremental_update()` in __init__.py
5. Implement `sync_turn()` with session logging
6. Test: write a page, verify it appears in search
7. Test: append to a page, verify content updated
8. Test: sync_turn creates session log, verify it's searchable
9. Test: path traversal attempt is rejected
10. Test: slugify produces SCHEMA-compliant filenames
