> **SUPERSEDED** by `qmd-integration` (OpenSpec change, `openspec/changes/qmd-integration/`). The hand-rolled FTS5 search engine has been replaced with delegation to the real QMD CLI (github.com/tobi/qmd), which provides BM25 full-text + vector similarity + LLM reranking.

## Why

The QMD wiki plugin uses hand-rolled keyword matching for search: exact word match (2.0 points) plus prefix match (1.0 point), with confidence multipliers. This works for 45 pages but has limitations: no phrase queries, no relevance ranking beyond raw match counts, no tokenization beyond `\w+`, and excerpts are just truncated raw content. As the wiki grows with session logs (Phase 2 sync_turn) and accumulated knowledge, search quality matters more.

Additionally, search results and the system prompt catalog show truncated raw content as "excerpts" — the first 200 characters of markdown. This is often unhelpful (may cut mid-sentence, include frontmatter artifacts, or miss the point of the page). A proper summary — either from frontmatter or auto-extracted from the first meaningful paragraph — gives the agent better context for deciding which page to read.
