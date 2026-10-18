# Design — QMD Wiki Isolation & Write Gating

## Context

The plugin is a Bridge: search/index/vectors/rerank are delegated to the QMD CLI
(`~/.cache/qmd/index.sqlite` is the single global store today). The plugin owns
orchestration, write tools, OKF filtering, session logging, and the catalog.

The fundamental gap: **isolation and freshness live in the wrong layer.** Isolation
is enforced by a Python catalog filter (bypassable); freshness requires a manual
full reindex (writes don't reach QMD).

## Per-Profile QMD Index (A1)

QMD resolves its index via env / config. To give each profile its own index:

- Resolve an index root from the profile (e.g. `~/.hermes/profiles/<name>/qmd` or
  a per-profile `QMD_HOME`/index path passed to QMD).
- Each profile's `_init_collections()` creates collections **from that profile's
  `wiki_dirs` only**, under that profile's index.
- `_run_qmd()` passes the profile-scoped index/environment so `qmd search/query`
  targets the right store.

Fail-closed property: even if a code path mishandles a path, a file that isn't in
the profile's index cannot be returned by QMD.

### Collection Isolation (A2)

Per-profile QMD indexes make collection names naturally isolated: `wiki`,
`control`, etc. live *inside* each profile's own sqlite, so they cannot collide
across profiles. The legacy shared `index` store (with dead `Restructured`
collections) is abandoned; new profile-named stores are built from each profile's
allowlisted `wiki_dirs`.

### Migration

On upgrade, per-profile `qmd-wiki.json` is updated so each profile's `wiki_dirs`
is the explicit allowlist. The default (Sera) profile drops the bare `04 - AI`
root entry; root-level files like `SCHEMA.md` are handled explicitly. The old
global `index.sqlite` collections are cleaned up.

## API-Gated Writes, Soft Enforcement (A3)

- Direct reads remain available to the agent (it must read pages).
- Agent writes go through `wiki_write` / `wiki_append`, which generate
  schema-conformant files (slug, frontmatter, dates, tag merge, wikilinks).
- The raw-edit bypass (`patch`/`write_file`/`terminal`) cannot be reliably removed
  from the toolset for a solo setup. Instead it is governed by:
  - **Convention** documented in AGENTS.md: "memory files are edited via
    wiki_write/wiki_append."
  - **Validator / lint**: the janitorial scan flags raw mutations of managed dirs
    (files written outside the API that don't conform to schema).

## Schema Validation on Write (C1)

`_handle_wiki_write` gains validation before writing:

- `type` must be in the known OKF set
  (`concept, entity, comparison, query, summary, decision, episodic, procedural,
   executive, identity, user, dream-candidate, ...`).
- `confidence` must be `high|medium|low`.
- `directory` must resolve to one of the profile's `wiki_dirs` (allowlist check,
  already partially present via traversal guard — strengthened to explicit
  membership).

Invalid input → reject with a clear error, nothing written.

## Incremental + Periodic Freshness (D1/D2)

- **On write:** after `wiki_write`/`wiki_append`, update that file in QMD
  (incremental, file-scoped) so new content is immediately searchable.
- **Session start:** full `qmd update` to catch external edits / renames / drift.
- **`wiki_refresh`:** full reindex (existing behavior, now the explicit
  "rebuild from scratch" path).

## Isolation Decision (per Trevor)

- **Model:** shared base (`Control, Wiki, Research, Procedures, Executive,
  Episodic, Users, Dreaming`) + isolated `Agents/<name>`. Sera does **not** see
  the other agents' memories by default.
- **Sharing channel:** `Agents/Shared/` opt-in per profile (default closed).

## Open Questions / Approvals Needed

1. Per-profile QMD index — confirm each profile owning its own index (~tens of MB
   total) is acceptable.
2. Incremental QMD update on every write — confirm the per-write cost is
   acceptable.
3. Sera config drops the bare root entry.
4. `Agents/Shared/` as the opt-in sharing channel.
