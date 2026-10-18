# QMD Wiki Memory Provider Specification

## Purpose
Hermes Agent memory provider that wraps the QMD CLI (github.com/tobi/qmd) as a search backend for `.qmd`/`.md` wiki files from an Obsidian vault or custom directories. QMD handles all search and indexing (BM25 full-text + vector similarity + LLM reranking). The plugin provides directory orchestration, OKF-aware search filtering, write tools (wiki_write, wiki_append), session logging via sync_turn, and result shaping for LLM context injection.

## Design lineage
The **Bridge** design is canonical: the plugin delegates search and indexing to the `qmd` CLI and owns only directory orchestration, OKF filtering, write tools, and session logging. An earlier proposal to hand-roll an FTS5 search engine inside the plugin (`qmd-wiki-fts5-search`) was superseded by this design and archived unapplied.

## Architecture

```
┌─────────────────────────────────────┐
│  QMDWikiMemoryProvider (Bridge)     │
│                                     │
│  Orchestrates: wiki_dirs, config    │
│  Manages: QMD collections           │
│  Delegates: search → qmd CLI        │
│  Owns: write tools, OKF filter,     │
│        sync_turn, catalog            │
└──────────┬──────────────────────────┘
           │ subprocess
           ▼
┌──────────────────────────────┐
│  QMD CLI (TypeScript)        │
│                              │
│  BM25 FTS5 search (fast)    │
│  Vector similarity           │
│  LLM reranking               │
│  Index management            │
└──────────────────────────────┘
```

## Requirements

### Requirement: Multi-directory indexing
The system SHALL scan all configured `wiki_dirs` (a list of directory paths) for `.qmd` and `.md` files to build a lightweight catalog. Search indexing is delegated to QMD via its own collection management.

#### Scenario: Index multiple directories at session start
- **WHEN** a new agent session begins
- **THEN** the system scans all directories in `wiki_dirs` for a catalog listing, and sets up QMD collections if they don't exist

#### Scenario: Manual reindex
- **WHEN** the `wiki_refresh` tool is called
- **THEN** the system re-scans all `wiki_dirs` for the catalog and calls `qmd update` to re-index

### Requirement: Exclude special directories from index
The system SHALL skip files in paths containing `node_modules`, `.git`, or any directory component starting with `_` during catalog file discovery.

#### Scenario: Underscore-prefixed directory
- **WHEN** a markdown file exists in a `_Queue/` subdirectory
- **THEN** the file is not in the catalog and does not appear in search results

#### Scenario: Non-underscore file in parent
- **WHEN** a markdown file exists directly in `Dreaming/` (no underscore on the file or its path components)
- **THEN** the file IS in the catalog even though `Dreaming/` contains `_Queue/` subdirectories

### Requirement: QMD hybrid search
The system SHALL delegate search to the QMD CLI tool. QMD provides BM25 full-text search (fast path) and hybrid search with vector similarity and LLM reranking (enhanced path).

#### Scenario: Fast keyword search
- **WHEN** `wiki_search` is called with a query
- **THEN** the system runs `qmd search "<query>" --json -n <top_k> --full-path` and parses the JSON results

#### Scenario: Hybrid search fallback
- **WHEN** BM25 search returns no results
- **THEN** the system falls back to `qmd query` for hybrid BM25 + vector + reranking over a longer timeout

#### Scenario: Type-filtered search
- **WHEN** `wiki_search` is called with a `type` parameter
- **THEN** the system delegates to QMD first, then filters results by frontmatter `type` field as a post-processing step

#### Scenario: Confidence-weighted ranking
- **WHEN** search results are ranked
- **THEN** the system applies confidence multipliers as a tiebreaker (high: 1.5x, medium: 1.0x, low: 0.7x)

#### Scenario: Status exclusion
- **WHEN** a page has `status: superseded` or `status: rejected`
- **THEN** the page is excluded from search results via post-processing

### Requirement: Page summaries
The system SHALL extract a summary for each page: from frontmatter `summary:` field if present, otherwise auto-generated from the first non-heading paragraph (truncated to 200 chars at word boundary). Summaries appear in search results and the system prompt catalog.

#### Scenario: Summary declared in frontmatter
- **WHEN** a page's frontmatter declares `summary:`
- **THEN** that value is used as the page summary

#### Scenario: Summary auto-extracted
- **WHEN** a page has no `summary:` frontmatter
- **THEN** the summary is taken from the first non-heading paragraph, truncated to 200 characters at a word boundary, and appears in search results and the system prompt catalog

### Requirement: Read full wiki pages
The system SHALL provide a `wiki_read` tool that returns the full content of a wiki page by title or path, including summary, OKF metadata, wikilinks, and executed code cell outputs.

#### Scenario: Read by title
- **WHEN** a user calls `wiki_read` with a page title
- **THEN** the system reads the file directly from disk using the parser, returning full content, summary, tags, type, confidence, status, and wikilinks
- **AND** if not found in the catalog, falls back to filesystem search and `qmd get --full-path`

### Requirement: Write wiki pages
The system SHALL provide a `wiki_write` tool that creates or updates wiki pages with auto-generated frontmatter. File names are slugified (lowercase, hyphens). On update, the created date is preserved and tags are merged.

#### Scenario: Create new page
- **WHEN** `wiki_write` is called with a title and content
- **THEN** a new file is created with generated frontmatter (title, tags, type, confidence, status, created, updated)

#### Scenario: Update existing page
- **WHEN** `wiki_write` is called with a title that already exists
- **THEN** the file is updated (created date preserved, updated date bumped, tags merged)

#### Scenario: Path traversal rejected
- **WHEN** `wiki_write` is called with a directory not in `wiki_dirs`
- **THEN** the write is rejected with a security error

### Requirement: Append to wiki pages
The system SHALL provide a `wiki_append` tool that appends content to an existing wiki page, optionally under a section header. Bumps the updated date.

#### Scenario: Append to an indexed page
- **WHEN** `wiki_append` is called for a page already in the index
- **THEN** the content is appended (optionally under a new section header) and the `updated` date is bumped

#### Scenario: Append to an unknown page
- **WHEN** `wiki_append` names a page that is not in the index
- **THEN** the call is refused

### Requirement: Session logging via sync_turn
The system SHALL log session activity to `Episodic/sessions/` on each turn. On first call per session, creates a session file with frontmatter. On subsequent calls, appends a timestamped entry with truncated user/assistant content (200 chars each). If Episodic/ is not in wiki_dirs, skips silently.

#### Scenario: First turn of session
- **WHEN** `sync_turn` is called for the first time in a session
- **THEN** a new session file is created in `Episodic/sessions/` with frontmatter (type: episodic)
- **AND** the full user and assistant content is written (no truncation)

#### Scenario: Subsequent turns
- **WHEN** `sync_turn` is called again in the same session
- **THEN** a timestamped entry is appended to the session file
- **AND** the entry boundary is identified by `### <ISO-date>` pattern, not raw `### ` (prevents markdown in message content from corrupting boundaries)
- **AND** the file is capped at 200 entries — oldest 25 stripped when exceeded
- **AND** the full content of each turn is preserved

#### Scenario: Agent identity in session metadata
- **WHEN** a new session file is created
- **THEN** the frontmatter includes `agent: <profile_name>` and tags include `agent:<profile_name>`
- **AND** the profile name is derived from `get_hermes_home()` path (e.g., `profiles/sera/` → `sera`, no profile → `default`)

#### Scenario: No Episodic directory configured
- **WHEN** `Episodic/` is not in `wiki_dirs`
- **THEN** `sync_turn` silently skips (no error, no file creation)

### Requirement: Catalog updates after writes
The system SHALL update the in-memory catalog (page list for system prompt) immediately after `wiki_write` or `wiki_append` operations via `_catalog_update()`, and SHALL run `qmd update` so the written page is searchable; `qmd update` reprocesses only changed files. `wiki_refresh` remains the full reindex path.

#### Scenario: Catalog updated without a rescan
- **WHEN** `wiki_write` or `wiki_append` succeeds
- **THEN** the in-memory catalog entry for that page is updated without rescanning the whole directory tree

#### Scenario: Written page becomes searchable
- **WHEN** a page is written
- **THEN** the plugin runs `qmd update`, which reprocesses only changed files, so the page is searchable without a full reindex

#### Scenario: Full reindex on demand
- **WHEN** `wiki_refresh` is called
- **THEN** the system rebuilds the catalog and runs a full `qmd update`

### Requirement: Wikilink awareness
The system SHALL extract `[[wikilink]]` targets from markdown body text and store them on each page. Wikilinks are included in search text, surfaced in `wiki_read` results, and displayed in formatted page context.

#### Scenario: Wikilinks extracted during parsing
- **WHEN** a page body contains `[[target]]`
- **THEN** the target is stored on the page, included in search text, surfaced by `wiki_read`, and shown in formatted page context

#### Scenario: Page without wikilinks
- **WHEN** a page contains no wikilinks
- **THEN** it parses normally with an empty wikilink set

### Requirement: Execute code cells for verification
The system SHALL optionally execute Python code cells in `.qmd` files during index refresh when `execute_cells` is enabled, storing outputs for retrieval.

#### Scenario: Cells executed when enabled
- **WHEN** `execute_cells` is enabled and a `.qmd` page contains an executable cell
- **THEN** the cell is executed during refresh and its output is stored for retrieval

#### Scenario: Cells skipped by default
- **WHEN** `execute_cells` is not enabled (the default)
- **THEN** cells are not executed and the page is parsed without cell outputs

### Requirement: Prefetch relevant context
The system SHALL inject relevant wiki content into the agent's context at session start, limited by `max_context_chars` and `max_pages` config values. Results come from QMD search.

#### Scenario: Prefetch injects bounded context
- **WHEN** a session starts and relevant pages are found
- **THEN** content is injected up to `max_context_chars` (default 2000) across at most `max_pages` (default 3) results

#### Scenario: No relevant pages
- **WHEN** search returns no results for the prefetch query
- **THEN** no context is injected

### Requirement: System prompt catalog
The system SHALL provide a system prompt block showing per-directory page counts and page titles with summaries (top 20), so the agent knows what knowledge is available. This is a lightweight listing — not a search index.

#### Scenario: Catalog block lists available knowledge
- **WHEN** the system prompt is built
- **THEN** it shows per-directory page counts and up to 20 page titles with summaries

#### Scenario: Empty configured directory
- **WHEN** a configured directory holds no pages
- **THEN** it is listed with a zero count rather than being omitted

### Requirement: Session logs excluded from default QMD search
The system SHALL add `Episodic/sessions/` as a QMD collection on init and exclude it from default queries. Session logs remain indexed for the dreaming cron and explicit `-c sessions` queries, but do not appear in unscoped `wiki_search` results.

#### Scenario: Sessions collection created and excluded on init
- **WHEN** `Episodic/sessions/` exists and `_init_collections()` runs
- **THEN** the system creates a QMD collection named `sessions` and runs `qmd collection exclude sessions`
- **AND** unscoped `wiki_search` queries no longer return session log files
- **AND** scoped queries with `-c sessions` still return them

### Requirement: Configurable wiki directories
The system SHALL resolve wiki directories from (in priority order): `QMD_WIKI_DIR` environment variable (legacy, wrapped into list), `~/.hermes/qmd-wiki.json` config file `wiki_dirs` key, or auto-detection from default paths.

#### Scenario: Per-profile config
- **WHEN** a profile's `qmd-wiki.json` lists `wiki_dirs` including `Agents/<name>/`
- **THEN** the system indexes shared directories plus that agent's private directory, and other agents' directories are invisible by omission

### Requirement: Per-agent isolation via config
Each profile's `qmd-wiki.json` SHALL list shared directories plus its own `Agents/<name>/` directory. Other agents' private directories SHALL NOT be in the scan list and SHALL NOT exist in the catalog. Isolation SHALL be structural (fail-closed whitelist).

#### Scenario: Profile scans only its own directories
- **WHEN** a profile whose `wiki_dirs` lists shared directories plus `Agents/<name>/` initializes
- **THEN** only those directories are scanned, and other agents' private directories are absent from the catalog

#### Scenario: Unlisted directory is invisible
- **WHEN** a directory is not listed in the profile's `wiki_dirs`
- **THEN** it cannot appear in catalog or search results

### Requirement: QMD bridge initialization
The system SHALL call `qmd collection add` for each wiki_dir on first initialization, then `qmd update` to index files, and optionally `qmd embed` for vector generation. QMD collections persist between sessions.

#### Scenario: First-time setup
- **WHEN** the provider initializes and a collection does not yet exist
- **THEN** it runs `qmd collection add` for each wiki_dir, runs `qmd update` to index files, and runs `qmd embed` for vector generation

#### Scenario: Collections persist between sessions
- **WHEN** the provider initializes again in a later session
- **THEN** existing collections are reused rather than recreated
