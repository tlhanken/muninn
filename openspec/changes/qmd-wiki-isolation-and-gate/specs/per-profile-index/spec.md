## ADDED Requirements

### Requirement: Each profile indexes only its own directories
The plugin SHALL run the QMD CLI against a per-profile index (`qmd --index <profile>`), populated only from that profile's configured `wiki_dirs`. Isolation SHALL be enforced at the index layer and SHALL fail closed: a directory that is not on the profile's allowlist is not in its index and cannot surface in search.

#### Scenario: Profile index is selected
- **WHEN** a memory provider initializes in a profile
- **THEN** every `qmd` invocation is passed `--index <profile-name>`, derived from the profile path (`~/.hermes/profiles/<name>/`), with `default` used when no named profile is active

#### Scenario: Directory outside the allowlist is invisible
- **WHEN** profile A's `wiki_dirs` does not list `Agents/B/`
- **THEN** `Agents/B/` is never added to profile A's index, so no query run by profile A can return its pages

#### Scenario: Collection names do not collide across profiles
- **WHEN** two profiles each initialize collections named `wiki` or `control`
- **THEN** the names stay distinct because each lives in its own profile index
