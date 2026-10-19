## ADDED Requirements

### Requirement: Pass B synthesises the knowledge base into candidates
The Pass B dreaming job SHALL examine the indexed knowledge base via `wiki_search` and `wiki_read`, checking for cross-references, recurring patterns, duplicates, staleness, orphans, quality problems, gaps, novel ideas, consolidation opportunities, and contradictions, and SHALL write each finding as a candidate in `_Dreaming/_Candidates/` named `{action}-{slug}.md` using the shared dream-candidate format.

#### Scenario: A synthesis run produces candidates
- **WHEN** a Pass B run completes
- **THEN** each finding is written to `_Dreaming/_Candidates/` with the same frontmatter contract as Pass A

#### Scenario: Every run yields at least one idea
- **WHEN** a Pass B run finds no gaps, duplicates, or orphans
- **THEN** it still produces at least one novel idea or proposal

#### Scenario: Findings are verified novel
- **WHEN** a finding duplicates something already documented, or already sitting in `_Candidates/`
- **THEN** no candidate is written for it

#### Scenario: Pass B never writes to live directories
- **WHEN** a Pass B run writes output
- **THEN** all output goes to `_Dreaming/_Candidates/`; nothing is written directly to `Wiki/`, `Episodic/`, or other live directories

#### Scenario: Dream log records the run
- **WHEN** a Pass B run completes
- **THEN** Dream Log.md gains an entry with the pages scanned, the candidate count, and a one-line summary
