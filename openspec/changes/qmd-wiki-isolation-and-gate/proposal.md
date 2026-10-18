# QMD Wiki Isolation & Write Gating

## Why

A full review of the QMD wiki plugin surfaced structural weaknesses in three areas:

1. **Isolation is not structural.** Today QMD uses **one global index**
   (`~/.cache/qmd/index.sqlite`) shared by all four profiles. Per-agent
   isolation is enforced only at the plugin's catalog-filter layer. Because the
   default (Sera) profile lists the bare `04 - AI` root in `wiki_dirs`, its
   catalog (and the on-the-fly parse path in `_search`) pulls in
   `Agents/{Lyra,Omen,Vex}/` — so Sera can see other agents' private memory
   notes, contrary to the stated isolation model. Isolation must live in the
   *index contents*, not a runtime filter.

2. **Collection names collide and stale collections linger.** `_collection_name()`
   derives a name from the directory basename, so every profile produces the
   same names (`wiki`, `control`, `episodic`, …). In the shared index these
   collide, and the existing collections point at a dead
   `Obsidian Vault (Restructured)/` path (0 files each).

3. **Write path does not enforce schema or stay fresh.** `wiki_write` accepts any
   `type`/`confidence` (nothing validates against the OKF set), and writes update
   only the in-memory catalog — a newly written page is not searchable until a
   manual `wiki_refresh`. There is no file-level incremental index update and no
   per-profile index.

## What Changes

- **Per-profile QMD index (A1):** each profile runs QMD against its **own named
  index** (`qmd --index <profile>` → `~/.cache/qmd/<profile>.sqlite`), populated
  only from that profile's `wiki_dirs`. Isolation is fail-closed: a directory not
  on the profile's allowlist is not in its index and cannot surface in search.
- **Per-profile collection isolation (A2):** because each profile owns a separate
  QMD index, its collection names (`wiki`, `control`, …) are naturally isolated —
  they no longer collide across profiles. The legacy shared `index` store (with
  dead `Restructured` collections) is abandoned; new profile-named indexes are
  built from each profile's allowlisted `wiki_dirs`.
- **API-gated writes with soft enforcement (A3):** agent writes flow through
  `wiki_write`/`wiki_append` (schema, slug, dates, tag merge, wikilinks). The raw
  `patch`/`write_file` bypass is governed by convention + a validator, not by
  removing write tools.
- **Schema validation on write (C1):** `wiki_write` rejects/warns on `type` or
  `confidence` outside the OKF set and on writes to directories outside the
  profile's allowlist.
- **Incremental + periodic freshness (D1/D2):** after a write, update *that file*
  in QMD (incremental) rather than a full reindex every write; full reindex on
  session start and on `wiki_refresh`.

## Capabilities

### New Capabilities
- `per-profile-index`: Each profile owns a QMD index built only from its
  `wiki_dirs`. Fail-closed isolation at the index layer.
- `write-schema-validation`: `wiki_write` validates `type` / `confidence` against
  the OKF set and validates the write target is on the profile's allowlist.
- `incremental-index-update`: Writes trigger a per-file QMD index update so a new
  page is searchable immediately.

### Modified Capabilities
- `qmd-wiki-indexing`: Collection naming becomes per-profile and non-colliding;
  stale collections are re-pointed.
- `wiki_write` / `wiki_append`: Now schema-validated; still API-gated.
- `qmd-bridge-search`: Search now targets the profile's own index.
- `wiki-refresh`: Full reindex (unchanged behavior) still available and now the
  explicit "rebuild from scratch" path.

## Impact

- **Files modified:** `hermes-plugins/qmd-wiki/__init__.py`, `parser.py`,
  per-profile `qmd-wiki.json` configs, `AGENTS.md`.
- **Dependency unchanged:** QMD CLI remains the index backend.
- **Config change:** `wiki_dirs` becomes the source of truth for *both* index
  contents and per-profile isolation. Sera's config drops the bare root entry.
- **Behavior change:** writes refresh the index incrementally (previously required
  manual `wiki_refresh`); invalid schema is rejected at write time.

## Open Questions

- Confirm Sera's config drops the bare root entry (shared dirs + `Agents/Sera`).
- Confirm sharing channel: `Agents/Shared/` opt-in per profile.
