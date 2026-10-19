# Tasks — Descope Dreaming

## 1. Archive the pipeline unapplied
- [x] 1.1 Move `dreaming-pipeline` to `changes/archive/` without applying its deltas
- [x] 1.2 Add a deferral note at the top of its `proposal.md`

## 2. Remove dreaming from the rest of the corpus
- [x] 2.1 Rescope `memory-interfaces` to drop candidate, `_Dreaming/` and dream-log formats
- [x] 2.2 Reword the living spec's sessions-exclusion requirement (no "dreaming cron")
- [x] 2.3 Replace the `Dreaming/` example in the underscore-exclusion requirement
- [x] 2.4 Reword the sessions-exclusion comment in `__init__.py`

## 3. Verification
- [x] 3.1 `openspec validate --all --no-interactive` passes
- [x] 3.2 No living spec or open change mentions the dreaming cron as a dependency
