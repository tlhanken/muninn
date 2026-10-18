## MODIFIED Requirements

### Requirement: QMD wiki implements the Hermes MemoryProvider interface by delegating to the tobi/qmd engine
The plugin SHALL NOT implement its own indexing or search algorithms. Instead, it SHALL act as a "Bridge" between the Hermes Agent lifecycle and the `qmd` CLI.

**Lifecycle mapping (Hermes → QMD):**
- `initialize()` → `qmd collection add <wiki_dirs> --name <profile_id>`
- `prefetch(query)` → `qmd query "<query>" --format json`
- `sync_turn(...)` → `qmd update`
- `on_session_end(...)` → `qmd update`

**Core responsibilities:**
- **Directory/isolation orchestration:** resolve `wiki_dirs` from the profile config and ensure `qmd` only indexes the permitted paths.
- **Result shaping:** parse `qmd`'s JSON output into a structured `[QMD Wiki Context]` block, applying OKF metadata filters (type, status, confidence).
- **Error handling:** degrade gracefully when the `qmd` environment (Node/Bun) is missing or the CLI returns an error.

**Deployment/environment:**
- The plugin requires a local `qmd` installation in `workspace/tools/qmd`.
- It interfaces with `qmd` via `subprocess`.
- On NixOS the plugin manages a local Node.js/Bun runtime to avoid system-level dependency conflicts.

#### Scenario: Search results are returned
- **WHEN** `wiki_search` is called with a query
- **THEN** the plugin executes `qmd query "<query>" --format json`, parses the results, filters by `type` if specified, and returns a formatted list of matching pages and excerpts

#### Scenario: Agent isolation is maintained
- **WHEN** Sera's profile is active
- **THEN** the plugin passes only Sera's configured `wiki_dirs` (including `Agents/Sera/`) to the `qmd` command, so no other agent's data is surfaced
