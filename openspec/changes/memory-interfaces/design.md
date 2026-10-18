# Design — Memory Interfaces

## The artifacts

| Artifact | Path | Writer | Readers | Indexed |
|---|---|---|---|---|
| Wiki page | `Wiki/`, `Research/`, `Procedures/`, `Control/`, `Executive/`, `Users/` | `wiki_write`/`wiki_append`, dreaming promotions | `wiki_search`/`wiki_read`, Pass B | Yes |
| Session log | `Episodic/sessions/session-<date>-<sid8>.md` | plugin `sync_turn` | Pass A | No |
| Dream candidate | `_Dreaming/_Candidates/<type>-<slug>.md` | Pass A/B via `write_file` | reviewer, Pass B, Pass C | No |
| Dream log | `_Dreaming/Dream Log.md` | Pass A/B/C | Pass A (idempotency) | Per decision D2 |
| Config | `~/.hermes/qmd-wiki.json`, `~/.hermes/profiles/<name>/qmd-wiki.json` | human | plugin | n/a |

## Decision D1: Candidate frontmatter (single schema)

Adopt the `dreaming-pipeline` field names and reconcile the action enum:

```yaml
---
title: Short descriptive title
type: dream-candidate
timestamp: ISO-8601
tags: [candidate-type, agent:profile-name]
created: YYYY-MM-DD
confidence: high | medium | low
source_session: session-filename.md
source_profile: profile-name
target_path: proposed/final/location.md
target_action: create | update | merge | prune | link | improve
status: candidate | promoted | rejected | archived
---
```

The vault SCHEMA's candidate block is updated to this. The narrower Pass A enum is widened
to the full `target_action` set.

## Decision D2: `_Dreaming/` rename and indexing

Adopt the `_Dreaming/` rename (whole directory excluded from indexing, including
`Dream Log.md`). Rationale: unreviewed working state should never be searchable, and the
dream log is an operational record read by the cron, not knowledge the agent recalls. The
vault SCHEMA's "Dream Log.md indexed" line is corrected. The plugin's candidate-promotion
reminder reads `_Dreaming/_Candidates/` directly from disk (bypassing the index), which is
already how the task is specified.

## Decision D3: Session log format

Adopt the implemented format as canonical (full content, per-speaker headers):

- frontmatter: `title: Session <date>`, `type: episodic`, `created`, `updated`,
  `tags: [session, log, agent:<profile>]`, `agent: <profile>`, `summary: <one-liner>`,
  `status: active`.
- body: repeating `### <YYYY-MM-DD HH:MM UTC> | User` / `| Assistant` blocks, full content,
  capped at 200 entries (oldest 25 stripped when exceeded).

The vault SCHEMA's richer session-summary fields (`participants`, `topics`, `open_items`)
are dropped from the *log* contract; if needed they belong to the dreaming promotion step,
not the raw log.

## Decision D4: Type set

`_OKF_TYPES` is extended to the vault's page types (`self-model`, `strategy`) and the
plugin's `dream-queue`/`dream-candidate` handling is documented as "not written via
`wiki_write`" (candidates are written by the cron with `write_file` into an excluded dir).
The `note` entry is removed from the type set if it is only a tag.

## Decision D5: Truncation

Full content + 200-entry cap. The contradicting scenario in `qmd-wiki-memory-provider` is
corrected.

## Decision D6: Ownership rules

- Only `wiki_write`/`wiki_append` and dreaming promotions write wiki pages.
- Only `sync_turn` writes session logs.
- Only dreaming cron writes candidates and the dream log.
- No node writes another node's artifacts.

## Risks / Trade-offs

- [Vault SCHEMA is authoritative and externally referenced] → Change it deliberately, note
  the date, and keep the repo spec in sync.
- [Existing candidate files use the old fields] → Provide a one-time normaliser or accept
  both fields on read during a transition window.