## ADDED Requirements

### Requirement: Formats are defined once, in code
The provider SHALL define its page types, confidence levels, statuses and session-log format as named constants in `parser.py` and nowhere else. `__init__.py` SHALL import them rather than redefine them, this spec SHALL document them, and the vault `SCHEMA.md` SHALL defer to this spec instead of restating them.

#### Scenario: No second definition
- **WHEN** a module needs the set of page types, confidence levels or statuses
- **THEN** it uses the constants exported by `parser.py`

#### Scenario: Spec and code cannot drift
- **WHEN** the Tier 1 contract tests run
- **THEN** they compare each value list in this spec with the matching constant in `parser.py` and fail on any difference

### Requirement: Page types are a closed set
The provider SHALL accept exactly the page types listed below on `wiki_write` and SHALL reject every other type, writing nothing and naming the allowed types in the error. Reading SHALL NOT reject a type: a page already on disk with an unlisted type still parses.

Page types: `concept`, `entity`, `comparison`, `query`, `summary`, `decision`, `episodic`, `procedural`, `executive`, `identity`, `user`, `self-model`, `strategy`, `note`

#### Scenario: Listed type accepted
- **WHEN** `wiki_write` is called with `type: self-model`
- **THEN** the page is written

#### Scenario: Unlisted type rejected
- **WHEN** `wiki_write` is called with `type: dream-candidate`
- **THEN** nothing is written and the error lists the allowed types

#### Scenario: Retired type still readable
- **WHEN** an existing page has `type: dream-candidate`
- **THEN** it parses, keeping that type

### Requirement: Confidence levels
The provider SHALL recognise exactly the confidence levels listed below, with `medium` as the default. An unlisted value SHALL be coerced to the default on read and on write rather than failing.

Confidence levels: `high`, `medium`, `low`

#### Scenario: Unlisted confidence coerced
- **WHEN** a page or a `wiki_write` call carries `confidence: certain`
- **THEN** the confidence is treated as `medium`

### Requirement: Page statuses
The provider SHALL recognise exactly the statuses listed below, with `active` as the default; an unlisted value SHALL be read as the default. Pages whose status is search-excluded SHALL NOT appear in search results. `candidate` has no current writer and is retained so existing pages keep their meaning.

Statuses: `active`, `superseded`, `rejected`, `candidate`

Search-excluded statuses: `superseded`, `rejected`

#### Scenario: Superseded page hidden from search
- **WHEN** a matching page has `status: superseded`
- **THEN** it does not appear in `wiki_search` results

#### Scenario: Unlisted status read as active
- **WHEN** a page carries `status: draft`
- **THEN** it is treated as `active`

### Requirement: Session log location
Session logs SHALL be written to `Episodic/sessions/session-<YYYY-MM-DD>-<sid8>.md`, where the date is the UTC date of the turn and `sid8` is the first 8 hex digits of the SHA-256 of the session id. Without a session id the file stem SHALL be `session-<YYYY-MM-DD-HHMM>`.

#### Scenario: Same session, same day
- **WHEN** two turns of one session happen on the same UTC date
- **THEN** both are logged to the same file

#### Scenario: Session crosses UTC midnight
- **WHEN** a session continues past UTC midnight
- **THEN** later turns are logged to a new file named for the new date

### Requirement: Session log contents
A session log's frontmatter SHALL carry exactly the fields listed below, with `type: episodic` and tags `session`, `log` and `agent:<profile>`; `summary` SHALL be added only when the session ends. The body SHALL hold one entry per speaker per turn, headed `### <YYYY-MM-DD HH:MM UTC> | User` or `| Assistant` and followed by the full message.

Session log fields: `title`, `tags`, `type`, `confidence`, `status`, `created`, `updated`, `agent`, `summary`

#### Scenario: New session file
- **WHEN** `sync_turn` runs for a session with no file yet
- **THEN** a file is created whose frontmatter has every listed field except `summary`, and whose body holds a User entry and an Assistant entry

#### Scenario: Message containing a heading
- **WHEN** a message itself contains a line starting with `### `
- **THEN** it is not counted as an entry, because entries are identified only by the timestamped header

### Requirement: Vault schema defers to this spec
The vault's `04 - AI/SCHEMA.md` SHALL NOT define page types, confidence levels, statuses or session-log fields itself. It SHALL point to this spec and MAY include the table generated from code by `just schema-doc`.

#### Scenario: Schema table regenerated
- **WHEN** a constant in `parser.py` changes
- **THEN** `just schema-doc` prints the updated table for the vault, and the contract test forces this spec to change in the same commit
