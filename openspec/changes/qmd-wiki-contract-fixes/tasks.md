# Tasks — QMD Wiki Contract Fixes

## 1. Availability gate
- [ ] 1.1 Load config (or call `_load_config()`) before `is_available()` can run
- [ ] 1.2 Make `is_available()` cheap (no double full-tree `rglob`)
- [ ] 1.3 Test: profile with non-default `wiki_dirs` reports available; empty config reports unavailable

## 2. Prefetch / queue_prefetch
- [ ] 2.1 `prefetch()` returns `self._prefetch_cache` only; no subprocess
- [ ] 2.2 Move live search into `queue_prefetch()`
- [ ] 2.3 Test: prefetch never exceeds the manager timeout; recall still works next turn

## 3. Context gating
- [ ] 3.1 Store `agent_context` in `initialize()`
- [ ] 3.2 Skip session logging + index writes unless context == "primary"
- [ ] 3.3 Test: simulated subagent/cron context writes no session file and runs no `qmd update`

## 4. Session exclusion
- [ ] 4.1 Decide and implement non-overlapping exclusion (pattern or path)
- [ ] 4.2 Test: a session file does not appear in an unscoped `wiki_search`
- [ ] 4.3 Test: `-c sessions` scoped query still returns session files
- [ ] 4.4 Migration note + rebuild step documented

## 5. Frontmatter safety
- [x] 5.1 Quote/escape `title` and `tags` in `generate_frontmatter`
      Done on both sides of the contract: the writer emits YAML double-quoted
      scalars with backslash escapes, and `parse_frontmatter` now reverses those
      escapes and splits flow sequences on commas outside quotes. Escaping the
      writer alone would have broken the round-trip, since the reader stripped
      quotes without unescaping.
- [ ] 5.2 Test: title with `"` and tag with `,` round-trip through `parse_frontmatter`
      Verified by an ad-hoc probe (strict YAML parse + lossless round-trip for
      `"`, `\`, `:`, `#`, `[]` in a title and a comma inside a tag), but NOT yet
      by a committed test: `hermes-plugins/qmd-wiki/` has no test harness and no
      uv project, so where plugin tests live is an open decision.

## 6. Backup + misc
- [ ] 6.1 Implement `backup_paths()` returning resolved `wiki_dirs`
- [ ] 6.2 Fix `qmd embed` flags; log non-zero exits
- [ ] 6.3 Preserve Unicode in `slugify()`; detect collisions
      Partially done: `slugify()` now keeps Unicode word characters (CJK and
      accented titles no longer collapse to `untitled`), normalises to NFC so
      NFC/NFD inputs give one slug, and uses a digest-suffixed fallback when the
      slug would be empty so unrelated titles cannot share a filename. Write-time
      collision *detection* (two distinct titles still slugging to the same
      string, e.g. `A B` and `A-B`) remains open.
- [ ] 6.4 Require `{lang}` fence for executable cells
- [ ] 6.5 Override `unavailable_reason()`

## 7. Verification
- [ ] 7.1 Run the new tests offline
- [ ] 7.2 Rebuild index on one profile and smoke-test search