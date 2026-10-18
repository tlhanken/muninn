## ADDED Requirements

### Requirement: Underscore-prefixed directories SHALL be excluded from index
The QMD wiki plugin SHALL skip any file whose path contains a directory component starting with `_` during index building in `_rebuild_index()`.

#### Scenario: File in underscore directory is not indexed
- **WHEN** a markdown file exists at `Dreaming/_Queue/item.md`
- **THEN** the file SHALL NOT appear in `wiki_search` results

#### Scenario: File in nested underscore directory is not indexed
- **WHEN** a markdown file exists at `Dreaming/_Candidates/deep/nested.md`
- **THEN** the file SHALL NOT appear in `wiki_search` results

#### Scenario: File outside underscore directory IS indexed
- **WHEN** a markdown file exists at `Dreaming/Dream Log.md` (no underscore on the file or its parent directory)
- **THEN** the file SHALL appear in `wiki_search` results when query matches

#### Scenario: Existing exclusions still work
- **WHEN** a markdown file exists in a path containing `node_modules` or `.git`
- **THEN** the file SHALL NOT appear in `wiki_search` results
