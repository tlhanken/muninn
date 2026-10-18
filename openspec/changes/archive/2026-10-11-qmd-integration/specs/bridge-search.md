# QMD Bridge Search Specification

## Requirement: Hybrid search via QMD CLI

The system SHALL delegate search and retrieval to the QMD CLI tool at `/home/tlhanken/workspace/tools/qmd/bin/qmd`. The plugin provides directory orchestration, OKF metadata filtering, and result shaping for LLM context; QMD handles indexing, BM25 search, vector similarity, and reranking.

### Scenario: Collection setup on initialization
- **WHEN** a new agent session begins and no QMD collections exist for the configured `wiki_dirs`
- **THEN** the system runs `qmd collection add <wiki_dir> --name <name>` for each directory, then `qmd update` and `qmd embed` to build the index
- **NOTE**: Collection setup requires user approval per QMD guidelines. The plugin SHOULD log what it's doing and respect existing collections.

### Scenario: Fast keyword search
- **WHEN** `wiki_search` is called with a query string
- **THEN** the system runs `qmd search "<query>" --json -n <top_k>` and parses the JSON results into page metadata
- **AND** BM25 relevance scores from QMD are preserved in search results

### Scenario: Hybrid search
- **WHEN** the agent needs higher quality search
- **THEN** the system MAY use `qmd query "<query>" --json -n <top_k>` for hybrid BM25 + vector + reranking

### Scenario: Type-filtered search
- **WHEN** `wiki_search` is called with a `type` parameter
- **THEN** the system delegates to QMD first, then filters results by frontmatter `type` field as a post-processing step

### Scenario: Confidence-weighted ranking
- **WHEN** search results are ranked
- **THEN** the system applies confidence multipliers (high: 1.5x, medium: 1.0x, low: 0.7x) as a post-processing adjustment

### Scenario: Status exclusion
- **WHEN** a page has `status: superseded` or `status: rejected`
- **THEN** the page is excluded from search results via post-processing

### Scenario: Read by title
- **WHEN** a user calls `wiki_read` with a page title
- **THEN** the system reads the file directly from disk using the parser (not QMD), returning full content, summary, tags, type, confidence, status, and wikilinks

### Scenario: Index refresh
- **WHEN** `wiki_refresh` is called (or after write operations)
- **THEN** the system runs `qmd update` to re-index, and optionally `qmd embed` to regenerate vectors

## Requirement: Configurable wiki directories

Unchanged from previous spec: the system SHALL resolve wiki directories from (in priority order): `QMD_WIKI_DIR` environment variable, `~/.hermes/qmd-wiki.json` config file, or auto-detection from default paths.

## Requirement: OKF-aware search

Unchanged: the system SHALL parse frontmatter `type`, `confidence`, and `status` fields and use them for search filtering, ranking, and exclusion as post-processing on QMD results.

## Requirement: Write support

Unchanged: `wiki_write`, `wiki_append` tools manage file I/O with frontmatter generation. After writes, `qmd update` is called to re-index.

## Requirement: Session logging via sync_turn

Unchanged: session activity logged to `Episodic/sessions/`.
