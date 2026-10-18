## Why

The QMD wiki memory provider currently indexes a single directory (`04 - AI/Wiki/`) using a single `wiki_dir` config key. This limits search to semantic memory only, leaves the other six CoALA memory classes unsearchable, and provides no mechanism for per-agent isolation when multiple Hermes profiles share one vault.

Additionally, the plugin ignores OKF frontmatter metadata (type, confidence, status) that is already present in every wiki file, missing an opportunity for type-filtered and confidence-weighted search. The dreaming pipeline introduces underscore-prefixed working-state directories (`_Queue/`, `_Candidates/`, `_Archive/`) that must never surface as established knowledge in search results.

## What Changes

- Replace single `wiki_dir` (string) with `wiki_dirs` (list of strings) — the plugin indexes all listed directories into one unified index. Backward compatible: a legacy `wiki_dir` is wrapped into a single-element list.
- Add underscore-prefix directory exclusion to the file scan loop — any path component starting with `_` is skipped during indexing.
- Add OKF-aware search: parse frontmatter `type`, `confidence`, and `status` fields. `wiki_search` gains an optional `type` filter. Confidence weighting boosts high-confidence pages and demotes low-confidence ones. Pages with `status: superseded` or `status: rejected` are excluded from search by default.
- Add wikilink extraction: `[[wikilinks]]` are parsed and stored on each `WikiPage`. `wiki_read` surfaces outbound links in results.
- Update `system_prompt_block()` to show a directory-level catalog with per-directory page counts.
- Per-profile config: each profile's `qmd-wiki.json` lists shared directories plus its own `Agents/<name>/` directory. Other agents' private directories are invisible by omission (fail-closed whitelist).
- Bump default config limits: `max_context_chars` 2000 → 3000, `max_pages` 3 → 5 (config-file override, not code change).

## Capabilities

### New Capabilities
- `underscore-directory-exclusion`: Skip directories prefixed with `_` during QMD index building, preventing unreviewed working-state material from polluting search results
- `okf-aware-search`: Parse and use OKF frontmatter metadata (type, confidence, status) for search filtering, ranking, and result exclusion
- `wikilink-awareness`: Extract and surface `[[wikilink]]` cross-references in wiki pages

### Modified Capabilities
- `qmd-wiki-indexing`: The scope of indexed content expands from a single wiki subdirectory to multiple configured directories. The scan loop gains underscore-prefix exclusion. The search algorithm gains OKF metadata awareness.

## Impact

- **Code**: `hermes-plugins/qmd-wiki/__init__.py` — multi-dir indexing, OKF-aware search, wikilink extraction, system prompt catalog. `hermes-plugins/qmd-wiki/parser.py` — wikilink extraction, frontmatter type/confidence/status parsing.
- **Config**: `~/.hermes/profiles/<name>/qmd-wiki.json` — per-profile config with `wiki_dirs` list and bumped limits
- **No breaking changes**: Existing `wiki_dir` config still works (wrapped into list). Existing wiki pages continue to index and search identically. Tools (`wiki_search`, `wiki_read`, `wiki_refresh`) keep the same interface with backward-compatible optional parameters.
- **Search scope**: QMD search now returns results from all configured memory classes (Control/, Wiki/, Research/, Procedures/, Executive/, Episodic/, Users/, Agents/<name>/) instead of only Wiki/
- **Excluded paths**: `_Queue/`, `_Candidates/`, `_Archive/` are excluded from the index via underscore-prefix rule. `Dream Log.md` (no underscore on file or parent dir) remains indexed.
- **Per-agent isolation**: Each profile sees shared directories + its own `Agents/<name>/`. Other agents' private directories are not in the scan list and do not exist in the index.
