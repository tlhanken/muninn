## ADDED Requirements

### Requirement: Pass A extracts knowledge candidates from unprocessed session logs
The Pass A dreaming job SHALL read `_Dreaming/Dream Log.md` to find the earliest session in `Episodic/sessions/` with no matching entry, read that session in full, and write each extracted artifact to `_Dreaming/_Candidates/` as its own `.md` file named `{candidate-type}-{slug}.md`. Extraction SHALL cover decisions, events, insights, preferences, procedural steps, open items, contradictions, and gaps, and SHALL be selective: a session with no actionable content produces zero candidates.

#### Scenario: Unprocessed session with extractable content
- **WHEN** a session file exists that Dream Log.md does not record as processed
- **THEN** the agent reads it in full and writes one candidate file per extracted artifact, each with OKF frontmatter (`type: dream-candidate`, `timestamp`, `tags`, `source_session`, `source_profile`, `target_path`, `target_action`, `status: candidate`)

#### Scenario: Session already processed
- **WHEN** Dream Log.md already records the session as processed
- **THEN** the agent skips it and moves to the next unprocessed session

#### Scenario: Session with no actionable content
- **WHEN** a session contains nothing worth extracting
- **THEN** no candidate files are written, and Dream Log.md still records the session with `candidates: 0` so it is not reprocessed

#### Scenario: Session cannot be read
- **WHEN** a session file cannot be read or parsed
- **THEN** Dream Log.md records `candidates: 0, error: <description>` and the job continues with the next session

#### Scenario: Dream log records the run
- **WHEN** a session has been processed
- **THEN** Dream Log.md gains an entry naming the session, the profile, the candidate count, and a one-line summary
