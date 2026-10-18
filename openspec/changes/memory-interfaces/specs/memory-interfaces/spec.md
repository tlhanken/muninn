## ADDED Requirements

### Requirement: Session log format is fixed
Session logs SHALL live at `Episodic/sessions/session-<YYYY-MM-DD>-<sid8>.md` with
frontmatter `title`, `type: episodic`, `created`, `updated`, `tags:
[session, log, agent:<profile>]`, `agent: <profile>`, `summary`, `status: active`, and a
body of repeating `### <ISO-timestamp> | User` / `| Assistant` blocks containing full
content, capped at 200 entries.

#### Scenario: New session file
- **WHEN** `sync_turn` runs for a new session
- **THEN** a file is created at the agreed path with the agreed frontmatter

#### Scenario: Entry cap
- **WHEN** a session file reaches 200 entries
- **THEN** the oldest 25 are removed before the new entry is appended

### Requirement: Dream candidate format is fixed
Candidates SHALL live at `_Dreaming/_Candidates/<type>-<slug>.md` with frontmatter
`title`, `type: dream-candidate`, `timestamp`, `tags`, `created`, `confidence`,
`source_session`, `source_profile`, `target_path`, `target_action`, `status`.

#### Scenario: Pass A writes a candidate
- **WHEN** the session-review pass extracts an artifact
- **THEN** the file uses the agreed fields and one of the agreed `target_action` values

### Requirement: Wiki page type set is complete and enforced
The provider SHALL accept the vault's page types (`concept`, `entity`, `comparison`,
`query`, `summary`, `self-model`, `strategy`, `decision`, `episodic`, `procedural`,
`executive`, `identity`, `user`) and SHALL reject unknown types on `wiki_write`.

#### Scenario: Known type accepted
- **WHEN** `wiki_write` is called with `type: self-model`
- **THEN** the write succeeds

#### Scenario: Unknown type rejected
- **WHEN** `wiki_write` is called with `type: nonsense`
- **THEN** nothing is written and an error lists the allowed types

### Requirement: Write ownership is exclusive
Each artifact SHALL be written by exactly one owner: wiki pages by `wiki_write`/`append`
and dreaming promotions, session logs by `sync_turn`, candidates and the dream log by the
dreaming pipeline.

#### Scenario: No cross-writes
- **WHEN** any node runs
- **THEN** it does not write an artifact it does not own