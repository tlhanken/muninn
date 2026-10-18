## ADDED Requirements

### Requirement: Dream candidates share one frontmatter contract
Every candidate written by Pass A or Pass B SHALL carry OKF frontmatter whose `type` is `dream-candidate`, with `timestamp` and `tags` (candidate type plus `agent:<profile>` provenance), and the plugin extensions `created`, `confidence`, `source_session`, `source_profile`, `target_path`, `target_action`, and `status`. `target_action` SHALL be one of `create`, `update`, `merge`, `prune`, `link`, `improve`, and `status` SHALL follow the lifecycle `candidate` → `promoted` | `rejected` → `archived`.

#### Scenario: Candidate frontmatter is written
- **WHEN** Pass A or Pass B writes a candidate
- **THEN** the file opens with frontmatter containing `type: dream-candidate`, the source session and profile, a `target_path`, a `target_action`, and `status: candidate`

#### Scenario: Lifecycle transitions
- **WHEN** a user reviews a candidate
- **THEN** `status` moves from `candidate` to `promoted` or `rejected`, and Pass C later archives candidates older than 14 days regardless

#### Scenario: Body carries the proposal
- **WHEN** a candidate proposes a create or update
- **THEN** its body states the context, the rationale, the proposed content, and wikilinks to related pages
