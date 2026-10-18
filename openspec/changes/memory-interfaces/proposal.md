# Memory Interfaces

## Why

The AI memory system is a set of cooperating nodes — the `qmd-wiki` plugin (writes,
reads, search), the dreaming pipeline (Pass A/B/C cron jobs), and the episodic pipeline —
that exchange files. Today the formats of those files are defined in at least three places
that disagree:

- the vault's `04 - AI/SCHEMA.md` (marked authoritative) and `04 - AI/Wiki/SCHEMA.md`,
- the plugin's `parser.py` / `_OKF_TYPES` and write paths,
- the OpenSpec changes `dreaming-pipeline`, `episodic-memory-pipeline`,
  `qmd-wiki-write-back`.

Concrete conflicts found in review:

- **Candidate frontmatter disagrees.** Vault SCHEMA uses `dream_date`, `source_queue`,
  `action`; `dreaming-pipeline` uses `timestamp`, `source_session`, `source_profile`,
  `target_action`. `candidate-file-format` allows `target_action` ∈
  {create,update,merge,prune,link,improve}; Pass A R-A6 lists only {create,update,merge}.
- **Directory + indexing disagrees.** Vault SCHEMA: `Dreaming/{_Queue,_Candidates,_Archive,
  Dream Log.md}` with **Dream Log.md indexed**. `dreaming-pipeline`: rename to `_Dreaming/`
  with **Dream Log.md not indexed**.
- **Session frontmatter disagrees.** Vault SCHEMA "Session Summary" expects `participants`,
  `topics`, `open_items`, title `Session YYYYMMDD_HHMMSS`; the plugin writes `agent`,
  `summary`, tags, title `Session <date>`.
- **Type set disagrees.** `_OKF_TYPES` omits vault types `self-model`, `strategy`,
  `dream-queue`, so `wiki_write` would reject pages the vault schema defines.
- **Truncation contradicts.** The living spec says "truncated 200 chars" in one scenario and
  "full content" in another; the code writes full content.

Without one contract, the dreaming pipeline reads formats the plugin does not write and
vice versa.

## What Changes

- Define a single `memory-interfaces` capability that pins each artifact's path, frontmatter
  fields, body format, writer, and readers.
- Resolve the conflicts above and align the vault `SCHEMA.md` with the promoted format.
- State ownership: which node writes each artifact and which may read/mutate it.

## Non-Goals

- Designing the dreaming pipeline's extraction logic (that stays in `dreaming-pipeline`).
- Per-user scoping.
- Changing the search engine.

## Impact

- **Docs/specs**: new living spec `openspec/specs/memory-interfaces/spec.md`; edits to
  `qmd-wiki-memory-provider`, `dreaming-pipeline`, `episodic-memory-pipeline`, and the vault
  `SCHEMA.md`.
- **Code**: plugin `generate_frontmatter` must produce the agreed session/candidate fields
  where it is the writer; no interface-breaking changes.
- **Coordination**: the vault SCHEMA is co-owned by the repo; both must change together.