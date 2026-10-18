# Tasks — QMD Wiki Isolation & Write Gating

## T1. Per-profile QMD index (A1)
- [ ] Resolve a per-profile index root (per-profile QMD_HOME / env for `_run_qmd`)
- [ ] `_init_collections()` creates collections from that profile's `wiki_dirs` only
- [ ] `_run_qmd()` passes the profile-scoped index path
- [ ] Verify: Sera cannot search `Agents/Lyra/SOUL.md`

## T2. Per-profile collection naming (A2)
- [ ] `_collection_name()` → `<profile>-<basename>` namespace
- [ ] Clean up / re-point stale `Restructured` collections
- [ ] Verify collections no longer collide across profiles

## T3. Config migration (isolation decision)
- [ ] Sera's `qmd-wiki.json`: drop bare `04 - AI` root; keep shared + Agents/Sera
- [ ] Root-level files (SCHEMA.md) handled via explicit entry
- [ ] Document `Agents/Shared/` opt-in channel

## T4. Schema validation on write (C1)
- [ ] `_handle_wiki_write` validates `type`/`confidence` against OKF set
- [ ] Reject writes to directories outside the profile allowlist (strengthen guard)
- [ ] Tests: valid write passes; invalid type / bad dir rejected; nothing written

## T5. Incremental + periodic freshness (D1/D2)
- [ ] After `wiki_write`/`wiki_append`, incremental QMD update of that file
- [ ] Session-start full `qmd update`
- [ ] `wiki_refresh` remains full reindex
- [ ] Tests: write → immediately searchable; external edit caught on session start

## T6. API-gated writes documentation (A3)
- [ ] AGENTS.md: memory files edited via wiki_write/wiki_append
- [ ] Validator/lint notes for the janitorial scan (flag raw non-conforming edits)

## T7. Bug fixes (B-series) — ride along
- [ ] B1: default wiki_write dir → `Wiki/` not `dirs[0]`
- [ ] B2: confidence as true tiebreaker (not full re-sort)
- [ ] B3: `_find_page` lookup order tightened
- [ ] B4: consolidate summary extractors

## Verification
- [ ] Sera isolated from other agents' `Agents/` dirs (search + direct)
- [ ] Collection names non-colliding per profile
- [ ] Write → immediate searchability
- [ ] Invalid schema rejected on write