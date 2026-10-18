# Design — QMD Wiki Contract Fixes

## Context

The provider is a Bridge: search/index/vectors/rerank are delegated to the `qmd` CLI; the
plugin owns orchestration, the in-memory catalog, write tools, OKF post-filtering, session
logging, and the system-prompt catalog. The fixes below correct the boundary between the
plugin and the Hermes `MemoryProvider` contract, and between the plugin and QMD's storage.

## Decision 1: Availability gate loads config first

`is_available()` is the activation gate and runs before `initialize()`. It must read the
config file itself (or `_load_config()` must run in `__init__`) rather than rely on state
populated by `initialize()`. The gate must stay cheap: check that at least one configured
dir exists and contains a `.md`/`.qmd` file, without walking the whole tree twice.

## Decision 2: prefetch is cache-only

`prefetch()` SHALL return `self._prefetch_cache` (or empty) and perform no subprocess call.
All searching happens in `queue_prefetch()`, which the manager already runs on a background
worker. This matches the contract and eliminates the daemon-thread-timeout skip.

## Decision 3: gate writes on agent_context

`initialize()` receives `agent_context` ∈ {primary, subagent, cron, flush}. Store it and
skip `_log_session_turn()`, `on_session_end()` frontmatter writes, and `_index_changed()`
when the context is not `primary`.

## Decision 4: sessions excluded at the storage layer

Overlapping collections defeat exclusion. Two acceptable fixes:

- Give the `episodic` collection a pattern that excludes `sessions/` (e.g. index
  `Episodic/**` minus `Episodic/sessions/**`), or
- Keep session logs entirely outside every indexed `wiki_dir`.

Preferred: keep session transcripts outside the indexed set, so exclusion is not
load-bearing. A requirement scenario must prove a session file never appears in an unscoped
query.

## Decision 5: YAML-safe frontmatter

`generate_frontmatter` quotes and escapes `title`, and emits `tags` as quoted items
(`tags: ["a", "b"]`) or a block list, so a title/tag containing `"`, `,`, `:` or `[` cannot
corrupt the document. Round-trip with `parse_frontmatter` must be lossless.

## Decision 6: backup_paths

Return the resolved `wiki_dirs` so `hermes backup`/`import` capture the knowledge base,
which lives outside HERMES_HOME. Must work without `initialize()` or network.

## Decision 7: correct qmd invocations

`qmd embed` accepts `--max-docs-per-batch` and `--max-batch-mb`, not `--timeout`. Use the
supported flags; surface non-zero exits at debug level instead of silently swallowing.

## Decision 8: code-cell execution semantics

Only a Quarto-style fence (```` ```{python} ````) is an executable cell. Plain
```` ```python ```` remains documentation. With `execute_cells` enabled, cells from
externally-synced vault files still execute unsandboxed — document this and default off.

## Risks / Trade-offs

- [Sessions-exclusion change requires a rebuild] → Documented migration step: re-run
  `wiki_refresh` after upgrade.
- [Unicode slugify] → Choose transliteration vs. percent-safe naming; collision must never
  silently overwrite an unrelated page.
- [Backup scope grows] → `hermes backup` now includes the vault; document the size change.

## Migration Plan

1. Land code fixes with unit tests that do not require the network.
2. Rebuild each profile's QMD index (`wiki_refresh`).
3. Verify a session file does not appear in an unscoped `wiki_search`.
4. Verify a `wiki_write` with a quote/comma in the title round-trips.