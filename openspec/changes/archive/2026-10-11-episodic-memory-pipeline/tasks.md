# Episodic Memory Pipeline — Tasks

## 1. OpenSpec Change
- [x] 1.1 proposal.md — written
- [x] 1.2 design.md — written
- [x] 1.3 specs/session-logging.md — written
- [x] 1.4 tasks.md — this file
 
## 2. sync_turn — Full Content + Turn Cap
- [x] 2.1 Remove 200-char truncation from user_content and assistant_content
- [x] 2.2 Add turn cap logic: count entries, strip oldest 25 if >= 200
- [x] 2.3 Update `_log_session_turn()` to write using the new format
 
## 2b. Bug Fix: ### delimiter in turn cap
- [x] 2b.1 Replace raw `\n### ` split with regex pattern `^### \d{4}-\d{2}-\d{2}`
- [x] 2b.2 Test: assistant message containing `### ` doesn't corrupt file

## 2c. Agent Metadata in Session Files
- [x] 2c.1 Extract profile name from `get_hermes_home()` path
- [x] 2c.2 Add `agent: <name>` to frontmatter and `agent:<name>` to tags on new session file creation
- [x] 2c.3 Test: new session files have agent metadata
- [x] 2c.4 Test: existing files unaffected

## 3. Session QMD Exclusion
- [x] 3.1 In `_init_collections()`, add Episodic/sessions/ as excluded QMD collection
- [x] 3.2 Run `qmd collection exclude sessions` after setup

## 4. Testing
- [x] 4.1 sync_turn writes full content (verify no truncation)
- [x] 4.2 Turn cap works (write 210 entries, oldest stripped)
- [x] 4.3 Session logs not in default QMD search
- [x] 4.4 Session logs accessible with `-c sessions` scope
- [x] 4.5 Existing session files unaffected

## 5. Closeout
- [x] 5.1 Update living spec at `openspec/specs/qmd-wiki-memory-provider/spec.md`
- [x] 5.2 Mark tasks complete
- [x] 5.3 Update `qmd-wiki-development` skill
