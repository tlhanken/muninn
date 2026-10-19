# Session Log Uncapped

## Why

Session logs are meant to be the complete record of every conversation: the raw
evidence everything else in memory is derived from. Today they are not. When a session
file reaches 200 entries (about 100 turns), `_log_session_turn` deletes the oldest 25,
so long sessions silently lose their beginning. The cap was added by
`episodic-memory-pipeline` to bound file growth, but "keep everything" is now an
explicit requirement, and a lost transcript cannot be rebuilt.

The write path has a second problem: each turn reads the whole file, rebuilds it in
memory and rewrites it. The cost of a turn grows with the log, and a failure part-way
through the rewrite can truncate the file, losing more than the turn being written.

The living spec also contradicts itself: the requirement text says entries are truncated
to 200 characters, while its scenarios say content is written in full.

## What Changes

- Remove the 200-entry cap; no entry is ever removed from a session log.
- Append each turn in append mode instead of rewriting the file. The only remaining
  whole-file rewrite of a session log is the one-time `summary` injection at session end.
- Rewrite the `Session logging via sync_turn` requirement: full content, append-only,
  format owned by `memory-interfaces`, and the truncation contradiction removed.

## Non-Goals

- Splitting or rotating long session files. Logs are excluded from default search, so a
  large file adds no noise to recall; rotation can come with the redesign.
- Changing the session-log format (owned by `memory-interfaces`).

## Impact

- **Code:** `_log_session_turn` appends through `parser.append_session_turn`.
- **Storage:** session files grow without bound, roughly 1 KB per turn. A year of daily
  200-turn sessions is about 73 MB, the figure `episodic-memory-pipeline` already
  judged acceptable.
- **Specs:** one requirement in `qmd-wiki-memory-provider` rewritten.
- **Tests:** Tier 1 tests that 250 turns keep all 500 entries and that appends leave
  earlier bytes unchanged.
