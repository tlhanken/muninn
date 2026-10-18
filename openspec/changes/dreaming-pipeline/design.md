# Dreaming Pipeline: Design

## Architecture Decisions

### Decision 1: Two LLM passes + one logic-only pass

**Chosen:** Three passes — Pass A (session review, LLM), Pass B (knowledge
synthesis, LLM), Pass C (janitorial, pure logic).

**Rationale:** The spec's four properties require LLM inference for properties
2 (state-transforming) and 4 (selective). A Python script cannot exercise
judgment about what's worth remembering or how concepts connect. Janitorial
work (file age checks, moves, cleanup) needs no judgment and should not burn
token budget.

The three-pass boundary aligns with the three gaps (consolidation, synthesis,
forgetting) — each pass has a single responsibility.

**Cost:**
- Pass A: ~30K tokens per session (read log, cross-reference, write candidates)
- Pass B: ~50K tokens per run (read multiple pages, synthesize, generate proposals)
- Pass C: Zero LLM, <2s runtime

### Decision 2: One LLM call per session (Pass A)

**Chosen:** Single LLM call processes an entire session log and returns all
candidates for that session.

**Rationale:** The LLM sees the full conversation context in one shot and can
produce all candidate types — decisions, events, insights, preferences, open
items, contradictions, gaps — in a single pass. Per-candidate calls would lose
cross-type awareness (e.g., a decision and an insight from the same turn are
related) and cost 5-10x more tokens.

**Alternative considered:** One LLM call per candidate type (7 calls per
session). More thorough per-type extraction but loses the relational context
that makes the dreaming useful. 7x the cost for marginal quality gain.

### Decision 3: Pass B includes creative generation

**Chosen:** The synthesis pass (daily) both connects existing knowledge AND
generates novel ideas and proposals.

**Rationale:** The same reading of the knowledge base that finds cross-references
and duplicates also surfaces gaps and creative opportunities. Splitting into two
passes would require re-reading the same pages twice. The LLM prompt handles
both modes: "find connections between existing pages AND propose new ideas based
on what you've read."

### Decision 4: `_Dreaming/` fully excluded from QMD

**Chosen:** Entire `_Dreaming/` directory is underscore-prefixed and excluded
from QMD indexing, including `Dream Log.md`.

**Rationale:** Everything in the dreaming pipeline is internal working state.
`Dream Log.md` is a processing audit trail, not knowledge worth searching.
If you need to check it, you read it directly via `read_file`. Consistency
with the `_` = working state convention.

### Decision 5: Promotion reminders in system_prompt_block

**Chosen:** The plugin's `system_prompt_block()` checks `_Dreaming/_Candidates/`
for pending files and injects a count into the system prompt.

```python
# In system_prompt_block(), after catalog listing:
candidates_dir = self._get_candidates_dir()
if candidates_dir:
    count = len([f for f in os.listdir(candidates_dir) if f.endswith('.md')])
    if count:
        reminder = f"\n⚠️ {count} candidate(s) awaiting review in _Dreaming/_Candidates/"
        # Insert after the catalog header, before topic listing
```

**Why not a separate check:** Every session start already calls
`system_prompt_block()`. Adding a filesystem check (<1ms) is free.
No extra cron, no separate tool, no polling.

**Alternative considered:** A dedicated `_queue_size` tool. Unnecessary —
`system_prompt_block()` already runs every turn and has access to
filesystem state.

### Decision 6: Manual cron setup for V1

**Chosen:** Document exact `hermes cron create` commands in tasks.md. User
runs them once.

**Rationale:** Cron definitions live in Hermes state.db, not in the plugin.
Adding `get_cron_definitions()` to the MemoryProvider interface would require
a Hermes core change. For a single-machine setup, manual creation is simpler
and equally durable (crons survive restarts).

**Bootstrapping future:** When Hermes core supports it, the plugin can expose
a `get_cron_definitions()` method returning `[{schedule, prompt, skills}]`.
Then `hermes cron setup` auto-installs them.

## Architecture

### Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                        Hermes Agent Session                       │
│  sync_turn() → writes full content to Episodic/sessions/         │
│  on_session_end() → injects summary into session file frontmatter│
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Pass A – Session Review (every 4h)                              │
│  LLM agent reads next unprocessed session → extracts → writes    │
│  _Candidates/ entries + updates Dream Log.md                     │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Pass B – Knowledge Synthesis (daily 2am)                        │
│  LLM agent reads full knowledge base → connects, synthesizes,    │
│  generates → writes _Candidates/ entries + updates Dream Log.md  │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Pass C – Janitorial (daily 3am)                                 │
│  Python script → archive old sessions, prune stale candidates,   │
│  clean empty dirs, run qmd update, update Dream Log.md           │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  system_prompt_block() (every turn)                              │
│  Checks _Candidates/ count → shows "⚠️ N candidates"             │
│  if non-zero                                                     │
└──────────────────────────────────────────────────────────────────┘
```

### Directory Layout

```
04 - AI/
├── _Dreaming/                       [FULLY EXCLUDED FROM QMD]
│   ├── _Queue/                      Future multi-source queue
│   ├── _Candidates/                 Dreamed results awaiting review
│   ├── _Archive/                    Rejected/superseded candidates
│   └── Dream Log.md                 Processing audit trail
├── Episodic/
│   ├── sessions/                    Full-content session logs (excluded)
│   ├── events/                      Per-event milestone records (NEW)
│   ├── decisions/                   Decision records (exists, empty)
│   └── insights/                    Cross-domain insights (NEW)
├── Executive/
│   ├── AI To Do List.md             Existing
│   └── open-items/                  One file per unresolved thread (NEW)
├── Wiki/                            Semantic memory (unchanged)
├── Control/                         Identity memory (unchanged)
├── Procedures/                      Procedural memory (unchanged)
├── User/                            User model (unchanged)
└── Research/                        Working output (unchanged)
```

### Candidate File Format

Every candidate in `_Candidates/` follows OKF-compliant frontmatter:

```yaml
---
title: Short descriptive title
type: dream-candidate
timestamp: 2026-07-06T22:43:00Z
tags: [decision, agent:sera]
created: 2026-07-06
confidence: high
source_session: session-2026-07-06-72c2a5eb.md
source_profile: default
target_path: Episodic/decisions/dreaming-pipeline-architecture.md
target_action: create
status: candidate
---

# Body

Full extracted content with context and rationale.
```

Fields:
- `type: dream-candidate` — OKF-compliant (non-empty type field)
- `timestamp` — ISO-8601 (OKF SHOULD S5)
- `tags` — list including candidate type + agent provenance (OKF SHOULD S5)
- `source_session` — which session produced this
- `source_profile` — which agent profile
- `target_path` — proposed final location for promotion
- `target_action` — `create`, `update`, `merge`, `prune`, `link`, `improve`
- `status` — `candidate` (default), `promoted`, `rejected`
- Any additional OKF MAY fields

### Plugin Changes

Minimal — the dreaming pipeline is external, using Hermes cron + agent prompts:

| File | Change |
|------|--------|
| `__init__.py` | Update `_DEFAULT_WIKI_DIRS` path (done) |
| `__init__.py` | Add `_get_candidates_count()` + promotion reminder in `system_prompt_block()` |
| `__init__.py` | `on_session_end()` (already built) |
| Config files | Update vault paths (done) |

No new tools, no new lifecycle hooks, no new dependencies.

## What Stays Unchanged

- All tool interfaces (wiki_search, wiki_read, wiki_write, wiki_append, wiki_refresh)
- Config format (qmd-wiki.json)
- Per-profile isolation
- Underscore exclusion
- Session log format (Option 2, per-speaker h3)
- on_session_end summary injection
- Everything else
