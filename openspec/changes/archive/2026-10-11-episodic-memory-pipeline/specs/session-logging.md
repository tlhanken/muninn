# Episodic Memory Pipeline: Specs

## Spec: Session Logging

### Requirement: Full-content session logs
The system SHALL write complete user and assistant conversation content to session log files without truncation.

#### Scenario: Full content written
- **WHEN** `sync_turn` is called with user and assistant content
- **THEN** the full content of both messages is written to the session file (no 200-char truncation)

#### Scenario: Turn cap enforced
- **WHEN** a session file reaches 200 entries
- **THEN** the oldest 25 entries are removed before the new entry is appended
- **AND** the file always contains at most 200 entries

#### Scenario: New session file created
- **WHEN** `sync_turn` is called for a new session_id
- **THEN** a new session file is created in `Episodic/sessions/` with frontmatter (type: episodic)

#### Scenario: Subsequent turns appended
- **WHEN** `sync_turn` is called again for the same session
- **THEN** a timestamped entry is appended to the existing session file

#### Scenario: Episodic/ not configured
- **WHEN** `Episodic/` is not in `wiki_dirs`
- **THEN** `sync_turn` silently skips (no error)

## Spec: Session Log QMD Exclusion

### Requirement: Session logs excluded from default search
The system SHALL add `Episodic/sessions/` as a QMD collection on init and exclude it from default queries.

#### Scenario: Sessions collection created on init
- **WHEN** `Episodic/sessions/` exists in a configured wiki_dir
- **THEN** the system creates a QMD collection named `sessions` pointing to that directory

#### Scenario: Sessions excluded from default search
- **WHEN** the sessions collection exists
- **THEN** `qmd collection exclude sessions` is called so default wiki_search queries do not return session files

#### Scenario: Explicit session search still works
- **WHEN** an LLM queries with `-c sessions`
- **THEN** session log files ARE returned (the exclusion only affects unscoped queries)
