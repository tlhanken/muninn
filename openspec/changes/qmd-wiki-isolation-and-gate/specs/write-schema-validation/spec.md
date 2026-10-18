## ADDED Requirements

### Requirement: Writes are validated against the OKF schema and the profile allowlist
The `wiki_write` tool SHALL reject a page `type` outside the known OKF set, and SHALL reject a write target outside the profile's configured `wiki_dirs`. A `confidence` value outside `high`/`medium`/`low` SHALL be coerced to `medium` rather than failing the write.

#### Scenario: Unknown page type is rejected
- **WHEN** `wiki_write` is called with a `type` that is not in the OKF set
- **THEN** the write is refused with an error naming the allowed types, and no file is written

#### Scenario: Unknown confidence is coerced
- **WHEN** `wiki_write` is called with a `confidence` value outside the OKF set
- **THEN** the value is coerced to `medium` and the write proceeds

#### Scenario: Write outside the allowlist is rejected
- **WHEN** `wiki_write` targets a directory that is not in the profile's `wiki_dirs`
- **THEN** the write is refused and no file is created
