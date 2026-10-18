## ADDED Requirements

### Requirement: Search SHALL support OKF type filtering
The `wiki_search` tool SHALL accept an optional `type` parameter that filters results to pages whose frontmatter `type` field matches the specified value. When no `type` is provided, all page types SHALL be searched.

#### Scenario: Search with type filter
- **WHEN** `wiki_search` is called with `type: "decision"`
- **THEN** only pages with frontmatter `type: decision` SHALL be returned

#### Scenario: Search without type filter
- **WHEN** `wiki_search` is called without a `type` parameter
- **THEN** pages of all types SHALL be searched and returned

#### Scenario: File without frontmatter type
- **WHEN** a file has no frontmatter or no `type` field
- **THEN** the file SHALL be treated as `type: None` and appear in unfiltered searches only

### Requirement: Search SHALL weight results by OKF confidence
The search ranking SHALL boost pages with `confidence: high` and demote pages with `confidence: low` relative to `confidence: medium` (the default for pages without a confidence field).

#### Scenario: High-confidence page ranked above medium
- **WHEN** two pages match the same query with equal keyword scores
- **AND** one has `confidence: high` and the other has `confidence: medium`
- **THEN** the high-confidence page SHALL rank higher

#### Scenario: File without confidence field
- **WHEN** a file has no `confidence` field in frontmatter
- **THEN** the file SHALL be treated as `confidence: medium`

### Requirement: Search SHALL exclude superseded and rejected pages by default
Pages with frontmatter `status: superseded` or `status: rejected` SHALL be excluded from `wiki_search` results by default.

#### Scenario: Superseded page excluded
- **WHEN** a page has `status: superseded` in frontmatter
- **THEN** the page SHALL NOT appear in `wiki_search` results

#### Scenario: Active page included
- **WHEN** a page has `status: active` or no `status` field
- **THEN** the page SHALL appear in `wiki_search` results when query matches
