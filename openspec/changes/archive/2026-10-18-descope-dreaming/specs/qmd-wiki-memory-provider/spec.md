## MODIFIED Requirements

### Requirement: Exclude special directories from index
The system SHALL skip files in paths containing `node_modules`, `.git`, or any directory component starting with `_` during catalog file discovery.

#### Scenario: Underscore-prefixed directory
- **WHEN** a markdown file exists in a `_Drafts/` subdirectory
- **THEN** the file is not in the catalog and does not appear in search results

#### Scenario: Non-underscore file in parent
- **WHEN** a markdown file exists directly in `Archive/` (no underscore on the file or its path components)
- **THEN** the file IS in the catalog even though `Archive/` contains `_Drafts/` subdirectories

### Requirement: Session logs excluded from default QMD search
The system SHALL add `Episodic/sessions/` as a QMD collection on init and exclude it from default queries. Session logs remain indexed for explicit `-c sessions` queries, but do not appear in unscoped `wiki_search` results.

#### Scenario: Sessions collection created and excluded on init
- **WHEN** `Episodic/sessions/` exists and `_init_collections()` runs
- **THEN** the system creates a QMD collection named `sessions` and runs `qmd collection exclude sessions`
- **AND** unscoped `wiki_search` queries no longer return session log files
- **AND** scoped queries with `-c sessions` still return them
