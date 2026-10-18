# QMD Wiki Contract Fixes

## Why

A design-and-code review of the `qmd-wiki` Hermes memory provider found places where
the implementation does not honour the `MemoryProvider` contract or its own documented
behaviour. The highest-impact items make the provider silently unreliable:

- **Availability gate ignores config.** `is_available()` runs before `initialize()`, so
  `_load_config()` has not populated `wiki_dirs`; the gate falls back to hardcoded default
  dirs and can report the provider unavailable for a correctly configured profile
  (`__init__.py:266-276, 469-473`).
- **Prefetch blocks.** `prefetch()` runs a live `qmd search` (60s) with a `qmd query`
  fallback (120s) whenever its cache is empty, violating the contract that prefetch returns
  cached results and recalls in the background. The manager bounds prefetch on a daemon
  thread and skips the provider on overrun (`memory_provider.py:111-113`,
  `memory_manager.py:404-433`).
- **Writes leak into non-primary contexts.** `initialize()` ignores `agent_context`, so
  subagent and cron runs append session logs and trigger reindexing
  (`memory_provider.py:98-100`).
- **Sessions are not reliably excluded.** The `sessions` collection lives under the
  `episodic` collection, whose `**/*.md` pattern already covers it; excluding one
  collection cannot hide files reachable via the overlapping one (`__init__.py:402-465`).
  Verified live: `qmd collection show episodic` and `... sessions` share pattern `**/*.md`.
- **Frontmatter is not escaping-safe.** `generate_frontmatter` emits `title: "{title}"` and
  unquoted `tags: [...]`; a quote, comma, or colon in a title or tag corrupts every file the
  provider writes (`parser.py:396-398`).
- **Backups miss the knowledge base.** `backup_paths()` is not implemented, so
  `hermes backup` does not capture the vault directories that live outside HERMES_HOME
  (`memory_provider.py:189-192`).
- **Embed never runs as intended.** `_run_qmd("embed", ..., "--timeout", "10")` passes an
  unsupported option; the resulting error is swallowed (`__init__.py:442`).
- **Unicode titles collapse.** `slugify()` strips all non-ASCII, so CJK/accented titles
  become `untitled` and collide (`parser.py:358-372`).
- **Doc examples become executable.** Plain ```` ```python ```` / ```` ```bash ```` fences
  are treated as executable cells and removed from the page body (`parser.py:139-187`).

## What Changes

- Load config before the availability gate; make `is_available()` cheap and correct.
- `prefetch()` returns the cached recall only; move all live search into `queue_prefetch()`.
- Read `agent_context` in `initialize()`; skip session logging and index writes for
  non-`primary` contexts.
- Make session-log exclusion correct at the storage layer (non-overlapping collection, or a
  path outside every indexed `wiki_dir`).
- Emit YAML-safe `title`/`tags` in `generate_frontmatter` (quote + escape).
- Implement `backup_paths()` returning the configured `wiki_dirs`.
- Fix the `qmd embed` invocation to use supported flags (`--max-docs-per-batch`,
  `--max-batch-mb`).
- Preserve Unicode in `slugify()` (transliterate or percent-safe), or fail loudly on
  collision.
- Treat a fenced block as executable only with the Quarto `{lang}` form; keep plain
  code fences as documentation.
- Override `unavailable_reason()` with a configuration hint.

## Non-Goals

- Replacing the Bridge architecture (QMD CLI as backend) — that stays.
- Changing tool interfaces (`wiki_search`, `wiki_read`, `wiki_write`, `wiki_append`,
  `wiki_refresh`).
- Per-user memory scoping (still deferred).
- Semantic re-ranking changes beyond the existing OKF post-filter.

## Impact

- **Code**: `hermes-plugins/qmd-wiki/__init__.py`, `hermes-plugins/qmd-wiki/parser.py`.
- **Config**: no new keys; existing `wiki_dirs` / limits unchanged.
- **Behaviour**: fixes are backward-compatible for well-formed pages; pages with quotes in
  titles/tags are written correctly instead of corrupting their frontmatter.
- **Risk**: the sessions-exclusion fix changes collection layout for existing indexes and
  requires a rebuild.