# Tasks — Memory Interfaces

## 1. Contract
- [ ] 1.1 Write `openspec/specs/memory-interfaces/spec.md` with the artifact table and per-artifact requirements
- [ ] 1.2 Land this change's `specs/memory-interfaces/spec.md` delta

## 2. Reconcile conflicts
- [ ] 2.1 Candidate schema (D1): update vault `04 - AI/SCHEMA.md` candidate block; widen Pass A enum
- [ ] 2.2 Directory/indexing (D2): confirm `_Dreaming/` rename; correct "Dream Log.md indexed" lines
- [ ] 2.3 Session log format (D3): align plugin + vault SCHEMA
- [ ] 2.4 Type set (D4): extend `_OKF_TYPES`; document candidate write path
- [ ] 2.5 Truncation (D5): fix the contradictory scenario in `qmd-wiki-memory-provider`

## 3. Downstream alignment
- [ ] 3.1 Update `dreaming-pipeline` specs to reference the agreed candidate fields
- [ ] 3.2 Update `episodic-memory-pipeline` specs to reference the agreed session format
- [ ] 3.3 Verify Pass A can parse a freshly written session log end-to-end

## 4. Verification
- [ ] 4.1 A written session log parses with the agreed fields
- [ ] 4.2 A written candidate parses with the agreed fields
- [ ] 4.3 No two specs disagree on a field name or path