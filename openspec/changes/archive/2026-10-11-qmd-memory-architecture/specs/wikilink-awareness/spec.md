## ADDED Requirements

### Requirement: Wiki pages SHALL expose wikilink cross-references
The parser SHALL extract `[[wikilink]]` references from page markdown and store them as a list on the `WikiPage` dataclass. The `wiki_read` tool SHALL include outbound wikilinks in its response.

#### Scenario: Wikilinks extracted during parsing
- **WHEN** a page contains `See [[cognitive-science]] and [[episodic-memory]]`
- **THEN** the parsed `WikiPage` SHALL have `wikilinks: ["cognitive-science", "episodic-memory"]`

#### Scenario: wiki_read surfaces wikilinks
- **WHEN** `wiki_read` is called for a page with outbound wikilinks
- **THEN** the response SHALL include a `wikilinks` field listing all extracted link targets

#### Scenario: Page with no wikilinks
- **WHEN** a page contains no `[[wikilink]]` syntax
- **THEN** the parsed `WikiPage` SHALL have an empty `wikilinks` list
