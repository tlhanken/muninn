## Context

Phase 1 gave us multi-directory indexing with OKF-aware keyword search. Phase 2 added write support (wiki_write, wiki_append) and session logging (sync_turn). The search engine is hand-rolled: a `Dict[str, List[int]]` word-to-page-indices map with exact match (2.0 pts) and prefix match (1.0 pt), plus confidence multipliers.

Python 3.13 on NixOS ships with SQLite 3.50.4, which includes FTS5. FTS5 provides BM25 ranking, MATCH queries (phrase, prefix, boolean), and snippet generation — all from stdlib `sqlite3`. No external dependencies.

## Goals / Non-Goals

**Goals:**
- Replace keyword search with FTS5 for better ranking and query capabilities
- Generate page summaries for search results and system prompt
- Use FTS5 snippets for excerpts instead of raw truncation
- Maintain OKF type/confidence/status filtering on top of FTS5
- Fall back to keyword search if FTS5 unavailable
- Keep incremental index updates working with FTS5

**Non-Goals:**
- Persistent on-disk FTS5 index (in-memory is fine — rebuilt on init, <1s)
- Embedding-based semantic search (different paradigm, different change)
- LLM-based summarization (summaries are frontmatter or first-paragraph extraction)
- Highlighting in wiki_read results (snippets only in search results)

## Decisions

### Decision 1: In-memory SQLite FTS5, not on-disk

**Choice**: Build FTS5 as an in-memory SQLite database (`:memory:`). Rebuild on `_rebuild_index()`. Update incrementally on writes.

**Alternatives considered**:
- On-disk SQLite database in `~/.hermes/qmd-wiki-fts5.db` (rejected: adds a cache file to manage, stale data risk, cleanup burden. In-memory rebuild is <1s for current scale.)
- Skip FTS5, improve keyword search (rejected: FTS5 is available, stdlib, and provides BM25 + snippets for free. Better to use it.)

**Rationale**: 45 pages, <1s to build. In-memory is simpler — no cache invalidation, no stale data, no file cleanup. If the index grows to thousands of pages and rebuild becomes slow, we can add on-disk persistence as a config option. The interface is the same either way.

### Decision 2: FTS5 table schema

**Choice**: Single FTS5 virtual table with columns: `path, title, tags, content, wikilinks, summary`. All columns are indexed for full-text search. The `path` column is the primary key for incremental updates (DELETE WHERE path = ? then INSERT).

**Rationale**: FTS5 searches across all columns simultaneously. Searching title + content + tags + summary gives better relevance than content-only. Wikilinks column makes `[[link targets]]` searchable. Path is used for row identification during incremental updates.

### Decision 3: BM25 + confidence multiplier for ranking

**Choice**: Use FTS5's `bm25()` function for base ranking. Apply confidence multiplier as a post-query adjustment: `final_score = bm25_score * confidence_weight`. Since BM25 returns negative scores (more negative = more relevant), multiply by the inverse weight: high confidence → less negative (boost), low confidence → more negative (demote).

**Alternatives considered**:
- Raw BM25 without confidence weighting (rejected: loses OKF metadata benefit from Phase 1)
- Custom rank function (rejected: FTS5's bm25 is well-tested and fast)

**Rationale**: BM25 handles term frequency and document length normalization. Confidence weighting is a simple post-query adjustment that preserves the OKF awareness from Phase 1. The math works out: BM25 scores are negative, so multiplying high-confidence results by 0.67 (1/1.5) makes them less negative (higher ranked), and low-confidence by 1.43 (1/0.7) makes them more negative (lower ranked).

### Decision 4: Summary from frontmatter or first paragraph

**Choice**: `WikiPage.summary` is set from frontmatter `summary:` field if present. Otherwise, auto-extract from the first non-heading, non-frontmatter paragraph in the markdown body, truncated to 200 chars at the nearest word boundary.

**Alternatives considered**:
- LLM-generated summaries (rejected: requires LLM call during indexing. Slow, expensive, non-deterministic. Belongs in the dreaming pipeline if anywhere.)
- No summaries, just use first 200 chars of content (rejected: this is the current behavior and it's bad — cuts mid-sentence, includes markdown artifacts)
- First sentence only (rejected: some pages have long first sentences, some have short ones. 200 chars at word boundary is more consistent.)

**Rationale**: First meaningful paragraph is a good approximation of a summary for knowledge base pages. Frontmatter `summary:` field allows manual override for pages where the first paragraph isn't representative. No LLM dependency.

### Decision 5: Fallback to keyword search

**Choice**: Check FTS5 availability at init time by creating a test FTS5 table. If it fails, set `_fts5_available = False` and fall back to the existing keyword search algorithm. Log a warning.

**Rationale**: Some minimal SQLite builds don't include FTS5. The fallback ensures the plugin works everywhere. The keyword search from Phase 1 is still functional — it's just not as good. The fallback is automatic and transparent to the agent.

### Decision 6: FTS5 query construction

**Choice**: Transform the agent's search query into an FTS5 MATCH query:
- Split into terms
- Add `*` suffix to each term for prefix matching (FTS5 prefix queries)
- Join with implicit AND (FTS5 default)
- Example: "memory architecture" → "memory* architecture*"

**Alternatives considered**:
- Pass raw query to FTS5 (rejected: FTS5 has its own query syntax which could break on special chars)
- Use FTS5 query syntax directly (rejected: agent doesn't know FTS5 syntax, and injection risk)

**Rationale**: Prefix matching (`term*`) replicates the Phase 1 behavior where partial matches scored. FTS5 AND is the same as Phase 1's implicit AND. Sanitizing the query (stripping FTS5 special chars) prevents injection. This gives the agent the same search experience with better ranking.

## Risks / Trade-offs

- [SQLite memory usage] → In-memory FTS5 for 45 pages is negligible (KB, not MB). At 1000+ pages, memory becomes noticeable but still manageable. Not a concern at current scale.
- [FTS5 not available] → Fallback to keyword search. Already handled. Warning logged.
- [Query parsing edge cases] → FTS5 has special characters (AND, OR, NOT, NEAR, ", *, (, )). The query sanitizer strips these. If a search term legitimately contains these chars (rare for wiki content), it won't match. Acceptable trade-off.
- [Summary quality] → First-paragraph extraction is a heuristic. Some pages start with metadata or context, not the core point. Frontmatter `summary:` field allows override. The dreaming pipeline (future) can generate better summaries.

## Migration Plan

1. Add `summary` field to `WikiPage` in parser.py, extract from frontmatter or first paragraph
2. Add `_build_fts5_index()` to __init__.py — create in-memory SQLite + FTS5 table, insert all pages
3. Update `_rebuild_index()` to call `_build_fts5_index()` after parsing all pages
4. Rewrite `_search()` to use FTS5 MATCH query with BM25 ranking + confidence weighting
5. Update `_incremental_update()` to DELETE + INSERT in FTS5 table
6. Add FTS5 availability check and keyword search fallback
7. Update search result formatting to use FTS5 snippets
8. Update system prompt catalog to use summaries
9. Test: FTS5 search returns relevant results with better ranking than keyword
10. Test: snippet generation produces useful excerpts
11. Test: summary field appears in search results and system prompt
12. Test: incremental update works with FTS5 (write → search → found)
13. Test: fallback activates when FTS5 unavailable (mock)
