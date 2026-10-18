# Dreaming Pipeline — Tasks

## 1. Directory Restructure
- [ ] 1.1 Rename `Dreaming/` to `_Dreaming/` (mv)
- [ ] 1.2 Create `Episodic/events/`
- [ ] 1.3 Create `Episodic/insights/`
- [ ] 1.4 Create `Executive/open-items/`

## 2. Plugin: Promotion Reminder in system_prompt_block
- [ ] 2.1 Add `_get_candidates_dir()` method — resolves `_Dreaming/_Candidates/` path
- [ ] 2.2 Add `_get_candidates_count()` method — counts `.md` files in candidates dir
- [ ] 2.3 Update `system_prompt_block()` to inject `⚠️ N candidates awaiting review`
      when count is non-zero
- [ ] 2.4 Test: empty candidates dir → no reminder line
- [ ] 2.5 Test: non-empty candidates dir → reminder line with correct count

## 3. Pass A — Session Review Cron
- [ ] 3.1 Write cron prompt for session review agent
- [ ] 3.2 Create cron job: `hermes cron create "every 4h" --prompt "..." --skills ...`
- [ ] 3.3 Test: cron processes an unprocessed session log
- [ ] 3.4 Test: cron skips already-processed sessions
- [ ] 3.5 Test: empty session produces `candidates: 0` log entry

## 4. Pass B — Knowledge Synthesis Cron
- [ ] 4.1 Write cron prompt for synthesis agent
- [ ] 4.2 Create cron job: `hermes cron create "0 2 * * *" --prompt "..." --skills ...`
- [ ] 4.3 Test: cron produces at least one candidate per run

## 5. Pass C — Janitorial Script
- [ ] 5.1 Write `scripts/janitorial.py`:
    - [ ] 5.1a Session archival (>30 days → `_Archive/sessions/`)
    - [ ] 5.1b Stale candidate archival (>14 days → `_Archive/candidates/`)
    - [ ] 5.1c Empty directory removal
    - [ ] 5.1d Stale lock file removal
    - [ ] 5.1e `qmd update` subprocess call
    - [ ] 5.1f Dream Log update
- [ ] 5.2 Create cron job: `hermes cron create "0 3 * * *" --script scripts/janitorial.py`
- [ ] 5.3 Test: script runs without errors on current state
- [ ] 5.4 Test: script is idempotent (no-op on second run with no new archives)

## 6. Dreaming/ → _Dreaming/ Directory Rename
- [ ] 6.1 Rename directory on disk
- [ ] 6.2 Verify plugin `_` exclusion handles it (no code change needed)
- [ ] 6.3 Verify QMD no longer indexes _Dreaming/

## 7. Closeout
- [ ] 7.1 Update living spec at `openspec/specs/qmd-wiki-memory-provider/spec.md`
- [ ] 7.2 Update `04 - AI/Wiki/AI Memory Architecture Spec.md` (Dreaming/ → _Dreaming/)
- [ ] 7.3 Archive completed changes (qmd-integration, episodic-memory-pipeline)
- [ ] 7.4 Mark all tasks complete

## Cron Setup Commands

```bash
# Pass A — Session Review (every 4 hours)
hermes cron create "every 4h" \
  --name "dreaming-pass-a-session-review" \
  --prompt "$(cat openspec/changes/dreaming-pipeline/cron-prompts/pass-a.md)" \
  --skills "qmd-wiki"

# Pass B — Knowledge Synthesis (daily 2am)
hermes cron create "0 2 * * *" \
  --name "dreaming-pass-b-synthesis" \
  --prompt "$(cat openspec/changes/dreaming-pipeline/cron-prompts/pass-b.md)" \
  --skills "qmd-wiki"

# Pass C — Janitorial (daily 3am)
hermes cron create "0 3 * * *" \
  --name "dreaming-pass-c-janitorial" \
  --script "scripts/janitorial.py"
```
