# QMD Bridge Integration: Design

## Architecture Overview

The QMD wiki plugin becomes a thin "Bridge" between Hermes Agent and the QMD CLI tool.

```
┌─────────────────────────────────────────────────────┐
│  Hermes Agent                                       │
│  ┌────────────────────────────────────────────────┐ │
│  │  QMDWikiMemoryProvider (Bridge)                │ │
│  │                                                │ │
│  │  keep:   Config loading (wiki_dirs, per-profile)│ │
│  │          Per-agent isolation (underscore excl.) │ │
│  │          Write tools (write, append, sync_turn) │ │
│  │          OKF filter (type, confidence, status)  │ │
│  │          Result shaping (LLM context format)    │ │
│  │          Lifecycle (init, prefetch, refresh)    │ │
│  │                                                │ │
│  │  +new:   _QMD_BIN constant → qmd CLI path      │ │
│  │          _run_qmd() → subprocess wrapper        │ │
│  │          _search() → qmd search --json          │ │
│  │          _query()  → qmd query --json           │ │
│  │          _get()    → qmd get --full-path        │ │
│  │          _init_collections() → qmd collection   │ │
│  └──────────┬─────────────────────────────────────┘ │
│             │ subprocess calls                        │
└─────────────┼───────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────┐
│  QMD CLI (/workspace/tools/  │
│    qmd/bin/qmd)              │
│                              │
│  - SQLite FTS5 BM25 (fast)  │
│  - sqlite-vec (vectors)     │
│  - LLM reranking (Qwen3)    │   ← Doing what we tried to hand-roll
│  - Query expansion (LLM)    │
│  - RRF fusion               │
└──────────────────────────────┘
```

## Design Decisions

### Decision 1: CLI subprocess vs MCP server

**Chosen:** CLI subprocess via `subprocess.run()`.

**Alternatives considered:**
- **MCP server (stdio or HTTP):** Would give structured tool calls and persistent state. But adds a daemon management layer, port conflicts, and startup coordination. The current requirement is simple: index management + search queries.
- **Python library import:** QMD is a TypeScript project — no Python bindings exist.
- **Direct SQLite access:** QMD's `~/.cache/qmd/index.sqlite` schema is internal and could change between versions. Never read another tool's database directly.

**Why CLI subprocess wins:** Minimal complexity. Each call is a self-contained process that QMD handles. The overhead of spawning a Node process for search queries (~100-200ms) is negligible compared to LLM response times (seconds).

### Decision 2: When to call qmd update

**Chosen:** On explicit `wiki_refresh` only, plus on `initialize()` if no collections exist.

**Rationale:** QMD's own docs say "Never run qmd collection add, qmd embed, or qmd update automatically." The plugin should respect this. On init, if no QMD collections exist for the configured wiki_dirs, we add them and run an initial update. After write operations (wiki_write, wiki_append), the plugin calls `qmd update` to trigger reindexing of just the affected collection.

### Decision 3: OKF filtering

**Chosen:** Post-processing on QMD JSON output.

QMD returns results ranked by relevance (BM25 + vectors + reranking). The plugin applies OKF metadata (type filter, confidence weighting, status exclusion) as a post-processing step on the JSON results. This ensures we don't override QMD's relevance ordering unnecessarily — only filter by type/status, and re-rank by confidence if needed.

### Decision 4: File discovery for system prompt catalog

**Chosen:** Keep lightweight file walking for catalog generation only.

The system prompt block lists available pages — this doesn't need QMD search. The plugin still walks `wiki_dirs` to build a lightweight page list (title, tags, source_dir) for the catalog. This is fast (<50ms for 100 pages) and avoids QMD overhead for what's essentially a directory listing.

### Decision 5: wiki_read implementation

**Chosen:** Read directly from filesystem, not via QMD.

QMD's `qmd get` returns file content, but it's formatted with line numbers and qmd:// URIs. For clean content, the plugin reads files directly using the existing parser.py. QMD's `qmd get --full-path` is used as a fallback to locate files by fuzzy title/path.

## QMD Integration Points

### Collection Setup (on initialize)
```python
# For each wiki_dir, create a QMD collection
QMD_BIN = "/home/tlhanken/workspace/tools/qmd/bin/qmd"
subprocess.run([QMD_BIN, "collection", "add", wiki_dir, "--name", name])
# Then update and embed
subprocess.run([QMD_BIN, "update"])
subprocess.run([QMD_BIN, "embed", "--max-docs-per-batch", "100", "--timeout", "10"])
```

### Search Delegation
```python
# Fast path (BM25 only)
result = subprocess.run(
    [QMD_BIN, "search", query, "--json", "-n", str(top_k)],
    capture_output=True, text=True
)
results = json.loads(result.stdout)  # list of {docid, score, file, ...}

# Enhanced path (hybrid + reranking)
result = subprocess.run(
    [QMD_BIN, "query", query, "--json", "-n", str(top_k), "--no-rerank"],
    capture_output=True, text=True
)
```

### Document Retrieval
```python
result = subprocess.run(
    [QMD_BIN, "get", "--full-path", file_path],
    capture_output=True, text=True
)
```

### Index Refresh
```python
subprocess.run([QMD_BIN, "update"])
```

## What Stays Unchanged

- **parser.py**: WikiPage dataclass, frontmatter parsing, write_wiki_file, append_to_wiki_file, slugify, code cell execution
- **Config format**: `~/.hermes/qmd-wiki.json` (wiki_dirs list, max_context_chars, max_pages)
- **Per-profile configs**: Separate qmd-wiki.json for each profile (Sera, Lyra, Omen, Vex)
- **Tool interfaces**: wiki_search, wiki_read, wiki_write, wiki_append, wiki_refresh — same names, same parameters
- **Underscore exclusion**: Files in _-prefixed directories are excluded (still enforced during file discovery for catalog and writes)

## What Gets Removed

- `_index` (keyword dict: `Dict[str, List[int]]`)
- `_fts5_db` (in-memory SQLite FTS5 database)
- `_fts5_available` flag
- `_build_fts5_index()`, `_fts5_insert()`, `_fts5_upsert()`, `_fts5_delete()`
- `_search_keyword()`, `_search_fts5()`, `_search_detailed()`
- `_incremental_update()` for search indices
- `sqlite3`, `hashlib`, `textwrap` imports (no longer needed)
