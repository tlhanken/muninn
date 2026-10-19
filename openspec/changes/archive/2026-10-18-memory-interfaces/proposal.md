# Memory Interfaces

## Why

Muninn's file formats are defined in three places that disagree:

- the vault's `04 - AI/SCHEMA.md` (marked authoritative, and outside this repo),
- the code: `_OKF_TYPES` in `__init__.py`, plus separate status and confidence sets
  hardcoded in `parser.py`,
- the OpenSpec corpus, where `qmd-wiki-isolation-and-gate` carries yet another inline
  type list.

Concrete disagreements: `_OKF_TYPES` accepts `dream-candidate` and `note` but not the
vault's `self-model` and `strategy`; the status set (`active`, `superseded`, `rejected`,
`candidate`) appears in no spec; and the session-log frontmatter the code writes differs
from the vault's "Session Summary" block.

Agreeing on the values once is not enough — they drifted because nothing stops them
from drifting. This change gives each format exactly one definition and a test that
fails when the documentation and the code disagree.

This change was first drafted to also pin dream-candidate and dream-log formats. Those
parts are dropped: the dreaming pipeline was descoped by `descope-dreaming`.

## What Changes

- **Code is the single source.** Page types, confidence levels, statuses, search-excluded
  statuses and the session-log format become named constants (and small helpers) in
  `parser.py`. `__init__.py` imports them; its own `_OKF_TYPES` literal goes away.
- **The type set is reconciled:** add `self-model` and `strategy`, drop `dream-candidate`
  from the writable set, keep `note`. Existing pages of any type still parse.
- **A new living spec, `memory-interfaces`,** documents every value list in a
  machine-checkable line, and a Tier 1 test compares each line with its constant.
- **`just schema-doc`** prints the contract as a markdown table generated from code, for
  the vault.
- **The vault `SCHEMA.md` stops defining formats** and points to the spec. The replacement
  text is in `design.md`; it has to be pasted into the vault by hand.
- `qmd-wiki-isolation-and-gate`'s inline type list is replaced by a reference to the spec.

## Non-Goals

- Changing search behaviour or the session-log cap (the cap is `session-log-uncapped`).
- Per-user scoping, and anything to do with the dreaming pipeline.

## Impact

- **Code:** `parser.py` gains the constants and session-log helpers; `__init__.py`
  imports them. `wiki_write` now accepts `self-model` and `strategy` and rejects
  `dream-candidate`. Session files gain no new fields; `agent` is written with the
  frontmatter instead of injected afterwards.
- **Specs:** new living spec `openspec/specs/memory-interfaces/spec.md`.
- **Tests:** new Tier 1 file `tests/test_memory_interfaces_contract.py`.
- **Coordination:** the vault `SCHEMA.md` must be updated to the pointer text.
