> This change covers fixes discovered during review of the initial implementation.

# Episodic Memory Pipeline: Design

## Architecture Decisions

### Decision 1: Full content vs summary in session logs

**Chosen:** Full content, no truncation.

**Rationale:** The "whole history in markdown" design intent requires complete records. 200-char truncation made logs useless for:
- Browsing past conversations in Obsidian
- Downstream processing by the dreaming cron (needs full context to extract moments)
- Wiki_read by path for reference

**Cost:** ~1KB per turn × 200 turns = ~200KB per session file. Acceptable on modern filesystems. A year of daily sessions at 200 turns each = ~73MB.

**Mitigation:** Turn cap of 200 prevents unbounded growth. Oldest entries are stripped from the file when new ones exceed the cap. The file always contains the most recent 200 turns.

### Decision 2: Turn cap mechanism

**Chosen:** When the session file would exceed 200 entries, strip the oldest block (oldest 25 entries at a time) before appending the new one.

**Alternatives considered:**
- **Archive to _Archive/ instead of stripping:** Would preserve history but create many small files. Better handled by the janitorial cron (Phase 6).
- **Soft truncation (first N chars of each turn):** Loses the "whole history" property.
- **No cap at all:** Would allow unbounded growth for long-running sessions.

### Decision 3: QMD collection exclusion mechanism

**Chosen:** Add `Episodic/sessions/` as a separate collection, then run `qmd collection exclude sessions`.

**How it works:**
- QMD's `collection exclude` flag means the collection is not included in default (unscoped) queries
- The collection and its index remain intact
- Queries scoped to `-c sessions` still work
- The dreaming cron and explicit agent queries can access sessions by including the `sessions` collection

**Alternative considered:**
- **Don't add sessions to QMD at all:** Would require separate directory scanning for the dreaming cron. Adding them as excluded gives us the best of both: indexed for the cron, hidden from the agent.

### Decision 4: Episodic subdirectories

**Not implementing yet.** The convention (`Episodic/events/`, `Episodic/decisions/`, `Episodic/insights/`) is documented in the plan but the actual structure will be created by the dreaming cron (Phase 5). For now, `Episodic/sessions/` is the only subdirectory.

### Decision 5: Entry delimiter for turn cap

**Bug discovered:** The initial implementation split on `\n### ` to count entries. If an assistant message contained `### ` at the start of a line (e.g., markdown headers in the response), the split produced incorrect boundaries, corrupting the entry structure.

**Chosen:** Split on a regex pattern matching `^### \d{4}-\d{2}-\d{2}` (timestamp pattern) instead of bare `### `. Entry boundaries are only recognized at lines matching the timestamp format `### 2026-07-02`.

**Why this works:** Every entry starts with `### <ISO-date>`. No natural language message starts with that exact pattern. The timestamp prefix is unique enough to be a reliable boundary while still being human-readable.

### Decision 6: Agent identity in session metadata

**Chosen:** Extract the profile name from `get_hermes_home()` and add `agent: <name>` to the session file frontmatter. Tags also gain `agent:<name>` for QMD indexability.

**How profile name is resolved:**
- `get_hermes_home()` returns the current profile's HERMES_HOME path
- If path contains `profiles/<name>/`, the profile name is `<name>`
- Otherwise, the profile is `default`
- Example: `~/.hermes/profiles/sera/` → `agent: sera`
- Example: `~/.hermes/` → `agent: default`

**Why frontmatter + tags:**
- Frontmatter `agent: sera` — clean, conventional OKF extension
- Tags `[agent:sera]` — indexed by QMD, searchable
- The dreaming cron can filter by agent to track per-profile patterns

**Alternative considered:**
- **Per-agent subdirectories:** `Episodic/sessions/sera/` etc. — cleaner isolation but requires config changes per profile. Adds complexity without clear benefit since the dreaming cron needs cross-agent access anyway.
- **Single profile-level field:** Only in frontmatter, not in tags. Wouldn't be QMD-indexed. Tags are needed for searchability.

## Implementation

### Entry delimiter fix
Replace the `\n### ` split with a regex match on `^### \d{4}-\d{2}-\d{2}`. When counting entries, only lines matching the timestamp pattern are counted as entry boundaries.

### Agent metadata
In `_log_session_turn()`, on first turn (file creation), detect the profile name from `hermes_home` and inject `agent: <name>` into both the frontmatter (as a field) and tags (as `agent:<name>`). Existing session files are not retroactively modified.

### sync_turn changes (`_log_session_turn`)

Current flow:
```
1. Truncate user_content to 200 chars
2. Truncate assistant_content to 200 chars
3. Format as markdown entry
4. Append to session file
```

New flow:
```
1. Format full user_content and assistant_content as markdown entry
2. Read current session file, count existing entries
3. If >= 200 entries, strip oldest 25 entries
4. Append new entry
5. Write back to file
```

### Session exclusion changes (`_init_collections`)

After the current collection setup loop, add:
```
if episodic_sessions_dir exists:
    qmd collection add <sessions_dir> --name sessions
    qmd collection exclude sessions
```

This runs on every `initialize()`. If the collection already exists, `collection add` errors with "already exists" — that's fine, it's idempotent. `collection exclude` is also idempotent.

## What Stays Unchanged

- All tool interfaces (wiki_search, wiki_read, wiki_write, wiki_append, wiki_refresh)
- Config format (qmd-wiki.json)
- Per-profile isolation
- Underscore exclusion
- System prompt catalog
- Prefetch/queue_prefetch
- Everything else
