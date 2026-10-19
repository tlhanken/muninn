# Tasks — Memory Interfaces

## 1. Single source in code
- [x] 1.1 Add the contract constants to `parser.py` (D1)
- [x] 1.2 Move session-log path, formatting and creation into `parser.py` helpers (D1, D5)
- [x] 1.3 `__init__.py` imports the constants; remove its `_OKF_TYPES` literal and the
      hardcoded confidence and status sets
- [x] 1.4 `wiki_write`'s tool description lists the allowed types from `PAGE_TYPES`

## 2. Reconcile the values
- [x] 2.1 Type set: add `self-model`, `strategy`; drop `dream-candidate` from writable (D3)
- [x] 2.2 Document statuses, confidence and search exclusion as implemented (D4)
- [x] 2.3 Replace `qmd-wiki-isolation-and-gate`'s inline type list with a spec reference

## 3. Keep the copies honest
- [x] 3.1 Write the `memory-interfaces` spec delta with machine-checkable value lines (D2)
- [x] 3.2 Add `tests/test_memory_interfaces_contract.py` (Tier 1): spec ⇔ code parity,
      type acceptance, session-log format
- [x] 3.3 Add `scripts/schema_doc.py` and the `just schema-doc` recipe (D6)
- [ ] 3.4 Paste the pointer text and generated table into the vault `04 - AI/SCHEMA.md`
      (manual; outside this repo)

## 4. Verification
- [x] 4.1 Tier 1 tests pass
- [x] 4.2 `openspec validate --all --no-interactive` passes
