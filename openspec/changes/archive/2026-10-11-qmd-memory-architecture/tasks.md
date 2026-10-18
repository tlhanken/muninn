## 1. Parser Changes

- [x] 1.1 Add `type`, `confidence`, `status`, `wikilinks` fields to `WikiPage` dataclass in `parser.py`
- [x] 1.2 Extract `type`, `confidence`, `status` from frontmatter in `parse_wiki_file()`
- [x] 1.3 Add wikilink extraction: regex `\[\[([^\]]+)\]\]` on markdown body, store as list on `WikiPage`
- [x] 1.4 Add `wikilinks` to `search_text` property so wikilink targets are searchable

## 2. Plugin — Multi-Directory Indexing

- [x] 2.1 Replace `wiki_dir` (string) with `wiki_dirs` (list) in `_load_config()` and `get_config_schema()`. Backward compatible: if legacy `wiki_dir` is set, wrap into single-element list.
- [x] 2.2 Rewrite `_rebuild_index()` to loop over all dirs in `wiki_dirs` instead of globbing one root
- [x] 2.3 Add underscore-prefix exclusion in scan loop: `if any(part.startswith("_") for part in path.parts): continue`
- [x] 2.4 Verify existing `node_modules` and `.git` exclusions still work alongside the new rule
- [x] 2.5 Update `_resolve_wiki_dir()` → `_resolve_wiki_dirs()` to return a list

## 3. Plugin — OKF-Aware Search

- [x] 3.1 Add optional `type` parameter to `WIKI_SEARCH_SCHEMA`
- [x] 3.2 In `_search()`: if `type` is provided, filter page list to matching types before scoring
- [x] 3.3 In `_search()`: apply confidence multiplier to scores (high=1.5x, medium=1.0x, low=0.7x)
- [x] 3.4 In `_search()`: exclude pages with `status: superseded` or `status: rejected` from results
- [x] 3.5 Update `handle_tool_call()` for `wiki_search` to pass `type` through to `_search()`

## 4. Plugin — Wikilink Awareness

- [x] 4.1 Update `WIKI_READ_SCHEMA` response to include `wikilinks` field
- [x] 4.2 In `handle_tool_call()` for `wiki_read`: include `page.wikilinks` in JSON response
- [x] 4.3 In `format_page_for_context()`: append wikilink list if non-empty

## 5. Plugin — System Prompt Catalog

- [x] 5.1 Rewrite `system_prompt_block()` to show per-directory page counts
- [x] 5.2 Include directory names in catalog: "[QMD Wiki] N pages across M directories"
- [x] 5.3 List top 20 page titles across all directories

## 6. Config Files

- [x] 6.1 Verify plugin installation path (symlink at ~/.hermes/plugins/qmd-wiki → workspace/tools/hermes-plugins/qmd-wiki)
- [x] 6.2 Default profile config at ~/.hermes/qmd-wiki.json serves as Sera's config (includes Agents/Sera/)
- [x] 6.3 Create `~/.hermes/profiles/lyra/qmd-wiki.json` (shared dirs + Agents/Lyra/)
- [x] 6.4 Create `~/.hermes/profiles/omen/qmd-wiki.json` (shared dirs + Agents/Omen/)
- [x] 6.5 Create `~/.hermes/profiles/vex/qmd-wiki.json` (shared dirs + Agents/Vex/)
- [x] 6.6 Default profile config at `~/.hermes/qmd-wiki.json` updated with wiki_dirs list + bumped limits

## 7. Vault Inventory and Preparation

- [x] 7.1 Inventory existing 04-AI/ contents — all CoALA dirs present
- [x] 7.2 Create missing directories: Episodic/sessions/, Episodic/decisions/, Procedures/workflows/, Procedures/scripts/, Agents/Sera/, Agents/Lyra/, Agents/Omen/, Agents/Vex/, Users/trevor/, Dreaming/_Queue/, Dreaming/_Candidates/, Dreaming/_Archive/
- [x] 7.3 Control/Souls/ content stays in place (SOUL files managed separately)
- [x] 7.4 Create Dreaming/Dream Log.md (initialized)
- [x] 7.5 .gitkeep files in _-prefixed directories (dir existence is sufficient)

## 8. Verification

- [x] 8.1 Run wiki_refresh and verify index builds from all wiki_dirs — 45 pages across 8 dirs
- [x] 8.2 Search for a term in Wiki/ — verify it appears in results — "narrative" returns 7 Wiki/ hits
- [x] 8.3 Search for a term in Research/ — verify it appears in results — "memory architecture" returns 3 Research/ hits
- [x] 8.4 Create test file in Dreaming/_Queue/ — verify it does NOT appear in search
- [x] 8.5 Create test file in Dreaming/_Candidates/ — verify it does NOT appear in search
- [x] 8.6 Verify Dreaming/Dream Log.md (no underscore) DOES appear in search
- [x] 8.7 Search with type filter — verify only matching types returned — type='comparison' returns 1 result
- [x] 8.8 Verify wiki_read response includes wikilinks field
- [x] 8.9 Verify system prompt shows per-directory catalog
- [x] 8.10 Clean up test files

## 9. Cleanup

- [x] 9.1 Old docs/proposals/qmd-memory-architecture.md superseded by OpenSpec change (no separate file to delete)
- [ ] 9.2 Update AI Memory Architecture Spec.md in vault to reflect final design decisions (deferred to after Phase 2/3)