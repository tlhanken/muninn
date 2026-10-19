## ADDED Requirements

### Requirement: Pass C performs filesystem maintenance with no LLM calls
The Pass C job SHALL be a pure Python script that makes zero API calls and moves rather than deletes: sessions older than 30 days from `Episodic/sessions/` to `_Dreaming/_Archive/sessions/`, and `status: candidate` files in `_Dreaming/_Candidates/` older than 14 days to `_Dreaming/_Archive/candidates/`. It SHALL remove empty directories under the AI tree except the directories the architecture expects, delete `.~lock.*` files older than one hour, and run `qmd update` afterwards so the index follows the moves.

#### Scenario: Old sessions are archived
- **WHEN** a session file's mtime is older than 30 days
- **THEN** it is moved to `_Dreaming/_Archive/sessions/`, creating that directory if it does not exist

#### Scenario: Stale candidates are archived
- **WHEN** a candidate has `status: candidate` and a `created` date older than 14 days
- **THEN** it is moved to `_Dreaming/_Archive/candidates/`

#### Scenario: Empty directories are pruned
- **WHEN** a directory under the AI tree is empty and is not one the architecture expects to be empty
- **THEN** it is removed

#### Scenario: Content is never deleted
- **WHEN** any Pass C step would remove content
- **THEN** the content is moved to `_Archive/` instead; no file is deleted, and destructive operations remain the user's decision

#### Scenario: Index follows the moves
- **WHEN** files have been moved or directories removed
- **THEN** the script runs `qmd update`, records the outcome in Dream Log.md, and exits non-zero on error
