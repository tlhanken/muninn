## Context

The QMD wiki plugin (`hermes-plugins/qmd-wiki/`) is a Hermes memory provider that indexes markdown files and makes them searchable via `wiki_search`. It currently takes a single `wiki_dir` path and recursively globs all `.qmd`/`.md` files from it. There is no include/exclude mechanism beyond hardcoded `node_modules` and `.git` skips.

The Obsidian vault's `04 - AI/` folder contains 7 CoALA memory classes (identity, user model, semantic, episodic, procedural, executive, dreaming) but only semantic memory (`Wiki/`) is currently searchable. The broader design (specified in `04 - AI/Research/AI Memory Architecture Spec.md`) calls for all memory classes to be searchable, with per-agent private directories and per-user memory.

Research into the broader ecosystem (Honcho, OpenViking, Mem0, Hindsight, mimir.works isolation patterns) and the Hermes MemoryProvider interface revealed:

1. The plugin receives `user_id`, `agent_identity`, and `agent_workspace` as kwargs to `initialize()`.
2. Only one external memory provider runs at a time — QMD replaces Honcho, not complements it.
3. The mimir.works isolation principle: scope filtering belongs in the storage/query layer, below retrieval. A path not in the scan list literally doesn't exist in the index.
4. For a single-user setup with secure bot access (Hermes pairing), per-user scoping adds complexity without value. Per-agent isolation via config is sufficient.

## Goals / Non-Goals

**Goals:**
- Make all memory classes in `04 - AI/` searchable via QMD, not just `Wiki/`
- Provide per-agent isolation — each profile sees shared dirs + its own `Agents/<name>/`, other agents' dirs are invisible
- Prevent unreviewed dreaming working-state material from polluting the search index
- Exploit OKF frontmatter metadata for type-filtered, confidence-weighted search
- Surface wikilink cross-references in wiki_read results
- Maintain backward compatibility — existing `wiki_dir` config still works

**Non-Goals:**
- Per-user memory isolation (deferred — additive when needed, not foreclosed)
- User identity resolution / alias maps (deferred)
- Write-back / sync_turn extraction (Phase 2, separate change)
- File watcher / auto-reindex on disk changes
- FTS5 search upgrade (Phase 3)
- Changes to the dreaming pipeline itself (vault-side concern)
- Changes to the parser's code cell execution logic

## Decisions

### Decision 1: Multiple source directories instead of single root

**Choice**: Replace `wiki_dir` (string) with `wiki_dirs` (list of strings). The plugin loops over all listed directories and indexes their contents into one unified index.

**Alternatives considered**:
- Keep single `wiki_dir` pointing at `04 - AI/` root, add include/exclude lists (rejected: the plugin has no include mechanism. Adding one is more code than multi-dir, and exclusion lists are blacklists that fail open.)
- Separate QMD instances per directory (rejected: one external provider limit. Can't run multiple QMD instances.)
- Per-profile symlink views (rejected: adds operational complexity, symlink breakage risk, Obsidian confusion.)

**Rationale**: Multi-dir is the simplest change that enables per-agent isolation. Each profile's config lists exactly the directories it should see. Isolation is structural — a path not listed doesn't get scanned. Misconfiguration means seeing less, not more (fail-closed whitelist). Backward compatible: legacy `wiki_dir` wraps into a single-element list.

### Decision 2: Per-agent isolation via config, not code

**Choice**: Each profile's `qmd-wiki.json` lists shared directories plus `Agents/<own-name>/`. No code-level agent detection.

**Alternatives considered**:
- Use `agent_identity` kwarg to dynamically resolve which `Agents/` subdir to include (rejected: couples plugin to Hermes identity system. Config is simpler and self-documenting.)
- Put all `Agents/` in the scan list and filter by agent at search time (rejected: post-hoc filtering. Other agents' data would be in the index, just filtered out. Violates the structural isolation principle.)

**Rationale**: Config-driven isolation is the mimir.works pattern applied at the file layer. The config file is the whitelist — you can read it and know exactly what an agent can see. Adding a new agent means creating its config, not modifying existing ones. No cross-contamination possible through misconfiguration of one profile affecting another.

### Decision 3: Underscore-prefix exclusion

**Choice**: Skip any file whose path contains a directory component starting with `_` during the file scan.

**Alternatives considered**:
- Frontmatter-based filtering (`type: dream-candidate` → exclude) — rejected: philosophically wrong. Unreviewed candidates shouldn't be in the index at all, not filtered post-hoc.
- Hardcode `_Queue/`, `_Candidates/`, `_Archive/` names — rejected: not generalizable, and the `_` prefix already means "not active content" in the existing wiki convention.

**Rationale**: One line of code, consistent with existing `_archive/` convention. The primary isolation for `Dreaming/` working-state dirs is omission from the `wiki_dirs` config — they're simply not listed. The `_`-prefix rule is defense-in-depth for the case where a parent directory (like `Dreaming/`) IS listed but contains `_`-prefixed children (`Dreaming/_Queue/`). This allows `Dreaming/Dream Log.md` to be indexed while `Dreaming/_Queue/` is not.

### Decision 4: OKF-aware search

**Choice**: Parse frontmatter `type`, `confidence`, and `status` fields during indexing. Use them for search filtering, ranking, and exclusion.

**Alternatives considered**:
- Flat keyword search only (current behavior) — rejected: wastes structured metadata already in every file. With a larger index spanning all memory classes, type filtering becomes essential for precision.
- Full FTS5 migration — rejected for now: adds SQLite dependency, migration complexity. Keyword search is fine for dozens of files. FTS5 is Phase 3.

**Rationale**: The parser already extracts frontmatter. Storing three additional fields (`type`, `confidence`, `status`) on `WikiPage` is a small change. Pre-filtering by type before keyword scoring is cheap (filter the page list). Confidence weighting is a multiplier on the match score. Status exclusion is a filter on the result set. All three improve search precision without changing the search algorithm's core.

### Decision 5: Shared Users/ directory, no per-user scoping

**Choice**: `Users/` is a shared directory in all profiles' `wiki_dirs`. The plugin ignores `user_id`. Bot access (Hermes pairing) is the security boundary.

**Alternatives considered**:
- Per-user scoping via `user_id` kwarg with identity resolution and alias maps (rejected for now: solves a problem that doesn't exist in a single-user setup with secure bot access. Adds significant complexity — identity resolution, alias management, per-user scan lists, write classification, dreaming user-blindness.)
- No `Users/` directory at all (rejected: the directory should exist for future use. Having it in the scan list is harmless when there's one user, and adding per-user scoping later is purely additive.)

**Rationale**: Four agents, one human, CLI and Telegram. The `user_id` kwarg is always the same person. Per-user scoping machinery (alias maps, identity resolution, per-user write routing, dreaming user-blindness) is deferred complexity. The simplified design doesn't foreclose any of it — adding per-user isolation later means scoping `Users/` to `Users/<resolved_id>/` in the scan list. Config change + plugin code for identity resolution. Additive, not structural.

### Decision 6: Config-file limits, not code defaults

**Choice**: Bump `max_context_chars` and `max_pages` via per-profile `qmd-wiki.json`, not in the plugin's default values.

**Rationale**: The larger searchable space may return more relevant pages. Changing code defaults affects all users. Config-file override is scoped to this deployment.

## Risks / Trade-offs

- [Larger index → slower session-start reindex] → The index is still small (dozens to low hundreds of files). Reindex takes <1s. Not a concern at this scale.
- [OKF metadata missing on some files] → Files without frontmatter type/confidence/status are treated as `type=None, confidence=medium, status=active`. They appear in all searches. No degradation from current behavior.
- [Per-agent isolation depends on config correctness] → Each profile must list `Agents/<own-name>/` and not list others. The config is self-documenting. Adding a new agent is a new config file, not a modification of existing ones.
- [Multi-dir config maintenance] → Adding a new shared directory requires updating all profile configs. With 4 profiles, this is trivial. If it grows, extract shared dirs to an include mechanism.
- [Underscore convention violation] → If someone creates a non-underscore directory with unreviewed content, it would be indexed. Mitigated by: SCHEMA.md documents the convention, janitorial cron lints for violations.

## Migration Plan

1. Patch `parser.py` — add `type`, `confidence`, `status`, `wikilinks` to `WikiPage` dataclass and `parse_wiki_file()`
2. Patch `__init__.py` — multi-dir indexing, _-prefix exclusion, OKF-aware search, wikilink surfacing, system prompt catalog
3. Create per-profile `qmd-wiki.json` configs with `wiki_dirs` lists
4. Run `wiki_refresh` to rebuild index with new config
5. Verify search returns results from multiple memory classes
6. Verify `_Queue/` and `_Candidates/` are excluded
7. Verify `Dreaming/Dream Log.md` IS indexed
8. Verify type-filtered search works
9. Verify per-agent isolation (Sera's config doesn't index Lyra's dir)
10. Rollback: delete `qmd-wiki.json` files (reverts to default wiki_dir) and revert plugin code changes
