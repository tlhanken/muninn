## MODIFIED Requirements

### Requirement: Frontmatter generation is escaping-safe
`generate_frontmatter` (and any writer) SHALL emit `title` and `tags` in a form that
survives values containing YAML-significant characters (`"`, `'`, `,`, `:`, `[`, `]`,
`#`). A written file SHALL round-trip through `parse_frontmatter` without loss.

#### Scenario: Title with a quote
- **WHEN** a page is written with title `He said "hi"`
- **THEN** the emitted frontmatter parses back to the same title

#### Scenario: Tag with a comma
- **WHEN** a page is written with a tag containing a comma
- **THEN** the tag is preserved as one item, not split

### Requirement: Filenames preserve Unicode
`slugify()` SHALL NOT reduce a non-ASCII title to `untitled`; it SHALL produce a stable,
filesystem-safe identifier and SHALL NOT silently overwrite an unrelated existing page.

#### Scenario: CJK title
- **WHEN** a page title is non-ASCII
- **THEN** the generated filename is deterministic and distinct from other titles

### Requirement: Only Quarto fences are executable cells
A fenced block SHALL be treated as an executable code cell only when it uses the Quarto
`{lang}` form. Plain language fences SHALL remain documentation in the page body.

#### Scenario: Plain python fence
- **WHEN** a page body contains ```` ```python ```` … ````
- **THEN** the block stays in the markdown body and is not executed