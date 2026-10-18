# Dreaming Pipeline

## Why

The QMD wiki plugin captures and indexes knowledge, but has no mechanism for
transforming raw conversation into structured memory. Session logs accumulate
in `Episodic/sessions/` but are never reviewed. Knowledge only enters the wiki
when the LLM explicitly calls `wiki_write` during a conversation — which is
unreliable because the LLM is focused on the task, not on maintaining a
knowledge base.

Three gaps exist:

1. **Consolidation** — Raw session logs contain decisions, events, insights,
   preferences, and open items that never become structured knowledge.

2. **Synthesis** — The knowledge base grows without cross-pollination.
   Related concepts across different sessions and wiki pages go unconnected.
   Creative opportunities from accumulated knowledge are missed.

3. **Janitorial** — Session files, stale candidates, and empty directories
   accumulate without automatic cleanup.

A dreaming pipeline (offline memory consolidation) fills all three gaps.
Inspired by Anthropic's Claude Dreaming (May 2026) and Ken Huang's
formalization (June 2026), with four required properties:
1. Asynchronous — not on critical path
2. State-transforming — merges, resolves, prunes, extracts
3. Reviewable — produces candidate artifacts with provenance
4. Selective — improves future decisions, not memorizes everything

## What Changes

### Structure: `Dreaming/` → `_Dreaming/`

The `Dreaming/` directory is renamed to `_Dreaming/` so the underscore prefix
excludes the entire directory from QMD indexing (consistent with the existing
`_` = working state convention). Internal structure stays:

```
_Dreaming/
  _Queue/              Future multi-source queue (currently unused)
  _Candidates/         Dreamed results awaiting review
  _Archive/            Rejected/superseded candidates
  Dream Log.md         Chronological record of dream runs (not indexed)
```

### New directories created

```
Episodic/events/       ← Per-event milestone records
Episodic/insights/     ← Cross-domain insights and patterns
Executive/open-items/  ← One file per unresolved thread
```

### Three cron jobs

**Pass A — Session Review (every 4 hours)**
Hermes agent reads unprocessed session logs and extracts:
- Decisions, events, insights, preferences, open items, contradictions, gaps

**Pass B — Knowledge Synthesis (daily 2am)**
Hermes agent reads the full knowledge base and produces:
- Cross-references, patterns, merge proposals, novel ideas, proposals,
  staleness flags, orphan detection, quality flags

**Pass C — Janitorial (daily 3am)**
Pure Python script (zero LLM) archives old sessions, prunes stale candidates,
removes empty directories, runs `qmd update`.

### Promotion reminders in system prompt

The plugin's `system_prompt_block()` checks `_Dreaming/_Candidates/` for
pending candidates and adds a reminder line to the catalog listing:
```
⚠️ N candidate entries awaiting review in _Dreaming/_Candidates/
```

### Vault path migration

All plugin defaults and profile configs updated from
`Obsidian Vault (Restructured)` to `Obsidian Vault`.

## No Breaking Changes

- All tool interfaces unchanged
- Config format unchanged
- Episodic/sessions/ logging unchanged (Option 2 format, on_session_end hook)
- Underscore exclusion unchanged (works automatically for `_Dreaming/`)
