# Tasks — Session Log Uncapped

## 1. Code
- [x] 1.1 Add `append_session_turn` to `parser.py`: append mode, separator from the file's last bytes
- [x] 1.2 `_log_session_turn` appends through it; remove the cap and the read-and-rewrite path
- [x] 1.3 Fix the `sync_turn` and `_log_session_turn` docstrings (no truncation, no cap)

## 2. Spec
- [x] 2.1 Rewrite `Session logging via sync_turn` in `qmd-wiki-memory-provider`

## 3. Verification
- [x] 3.1 Tier 1: 250 turns keep all 500 entries, first turn included
- [x] 3.2 Tier 1: an append leaves the bytes already logged unchanged
- [x] 3.3 `openspec validate --all --no-interactive` passes
