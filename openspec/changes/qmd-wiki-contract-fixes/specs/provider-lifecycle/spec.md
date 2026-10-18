## ADDED Requirements

### Requirement: Availability check reads configured directories
`is_available()` SHALL resolve directories from the provider's configuration (env or config
file) rather than only from state populated during `initialize()`, and SHALL report
available when at least one configured directory exists and contains a `.md`/`.qmd` file.

#### Scenario: Configured non-default directory
- **WHEN** the config lists only custom directories that exist and contain markdown
- **THEN** `is_available()` returns True

#### Scenario: No configured directory
- **WHEN** no configured or default directory exists
- **THEN** `is_available()` returns False

### Requirement: Unavailable reason is explained
The provider SHALL override `unavailable_reason()` with a hint describing what is missing
(no configured directory, no markdown files, qmd binary absent).

#### Scenario: Binary missing
- **WHEN** the `qmd` binary cannot be located
- **THEN** `unavailable_reason()` returns a message naming the missing binary