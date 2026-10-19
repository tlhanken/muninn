## ADDED Requirements

### Requirement: Prefetch returns cached recall only
The provider SHALL return only previously-queued recall from `prefetch()`. It SHALL NOT
invoke the `qmd` CLI (or perform any blocking work) inside `prefetch()`. All searching
SHALL occur in `queue_prefetch()`.

#### Scenario: Empty cache
- **WHEN** `prefetch()` is called and no recall has been queued
- **THEN** it returns an empty string and performs no subprocess call

#### Scenario: Cache populated by background recall
- **WHEN** `queue_prefetch()` has run for a query
- **THEN** the next `prefetch()` returns that cached context without re-searching

### Requirement: Provider writes are gated by agent context
The provider SHALL read `agent_context` in `initialize()` and SHALL skip session logging
and index-mutating calls unless the context is `primary`.

#### Scenario: Subagent context
- **WHEN** the provider is initialized with `agent_context="subagent"`
- **THEN** `sync_turn()` writes no session file and no `qmd update` is triggered

### Requirement: Session logs do not appear in unscoped search
Session log files SHALL NOT be returned by an unscoped `wiki_search`, and a session file
SHALL remain reachable by an explicit session-scoped query.

#### Scenario: Unscoped query excludes sessions
- **WHEN** a query is run against the default collection set
- **THEN** no file under the session-log directory is returned

#### Scenario: Scoped query includes sessions
- **WHEN** the session collection is queried explicitly
- **THEN** session files are returned