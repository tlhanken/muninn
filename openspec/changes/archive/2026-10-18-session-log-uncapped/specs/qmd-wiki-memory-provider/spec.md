## MODIFIED Requirements

### Requirement: Session logging via sync_turn
The system SHALL log session activity to `Episodic/sessions/` on each turn, in the format defined by the `memory-interfaces` spec. On the first call per session it SHALL create a session file with frontmatter; on later calls it SHALL append the turn. Every turn SHALL be logged in full, with no truncation, and no entry SHALL ever be removed from a session log. If Episodic/ is not in wiki_dirs, logging SHALL be skipped silently.

#### Scenario: First turn of session
- **WHEN** `sync_turn` is called for the first time in a session
- **THEN** a new session file is created in `Episodic/sessions/` with frontmatter (type: episodic)
- **AND** the full user and assistant content is written (no truncation)

#### Scenario: Subsequent turns
- **WHEN** `sync_turn` is called again in the same session
- **THEN** the turn is appended to the end of the session file in full
- **AND** the file is not rewritten, so the entries already logged are left byte-for-byte unchanged

#### Scenario: Long session keeps every entry
- **WHEN** a session reaches 250 turns
- **THEN** its log holds all 500 entries, the first turn included

#### Scenario: Agent identity in session metadata
- **WHEN** a new session file is created
- **THEN** the frontmatter includes `agent: <profile_name>` and tags include `agent:<profile_name>`
- **AND** the profile name is derived from `get_hermes_home()` path (e.g., `profiles/sera/` → `sera`, no profile → `default`)

#### Scenario: No Episodic directory configured
- **WHEN** `Episodic/` is not in `wiki_dirs`
- **THEN** `sync_turn` silently skips (no error, no file creation)
