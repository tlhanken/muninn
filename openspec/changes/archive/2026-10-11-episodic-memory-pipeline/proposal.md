# Episodic Memory Pipeline

## Why

The QMD bridge refactor established the search backend, but the memory pipeline around it is incomplete. Two immediate problems:

1. **sync_turn truncates to 200 chars** — The session log only stores truncated user/assistant content, making it useless for recall or downstream processing. The "whole history in markdown" design intent is not met.

2. **Session logs pollute search results** — Raw session logs are indexed by QMD alongside curated wiki pages. Every `wiki_search` returns session artifacts alongside reference material. They have different signal profiles (dozens of reference pages vs hundreds of session files) and should be separated.

## What Changes

### Change 1: sync_turn writes full content with turn cap
- Remove the 200-char truncation from `_log_session_turn()`
- Write complete `user_content` and `assistant_content` to the session file
- Add a turn cap: when a session file exceeds 200 turns, strip the oldest entries to keep growth bounded

### Change 2: Session logs excluded from default QMD search
- On `_init_collections()`, add `Episodic/sessions/` as a separate QMD collection
- Run `qmd collection exclude sessions` to exclude it from default queries
- The dreaming cron and explicit queries can still access sessions with `-c sessions`
- Episodic memories (`Episodic/events/`, `Episodic/decisions/`, etc.) remain in default search

## Capabilities

### Modified Capabilities
- `sync_turn`: Now writes full conversation content instead of 200-char summaries. Files are capped at 200 turns.
- `QMD collection initialization`: Session logs are added as an excluded collection, not part of the default index.

## Impact

- **Files modified**: `hermes-plugins/qmd-wiki/__init__.py` — `_log_session_turn()` and `_init_collections()`
- **Storage**: Session files grow from ~50KB to ~200KB (200 turns × ~1KB/turn). Acceptable.
- **No breaking changes**: Tool interfaces unchanged. Config unchanged. Existing session files unaffected (new writes only).
