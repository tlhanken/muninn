## 1. Parser — Write Functions

- [x] 1.1 Add `slugify(title: str) -> str` to parser.py: lowercase, spaces→hyphens, strip non-alphanumeric except hyphens, max 80 chars
- [x] 1.2 Add `generate_frontmatter(title, tags, page_type, confidence, status, created, updated) -> str` to parser.py
- [x] 1.3 Add `write_wiki_file(path: str, title: str, content: str, tags, page_type, confidence, status) -> None` to parser.py: generate frontmatter, write file
- [x] 1.4 Add `append_to_wiki_file(path: str, content: str, section: Optional[str] = None) -> None` to parser.py: read, append, write back
- [x] 1.5 Frontmatter updated field bumped on append (handled in append_to_wiki_file)

## 2. Plugin — wiki_write Tool

- [x] 2.1 Add `WIKI_WRITE_SCHEMA` with title, content, tags, type, confidence, directory parameters
- [x] 2.2 Implement `_resolve_write_dir(directory: str) -> Optional[str]`: match basename against wiki_dirs, return full path or None
- [x] 2.3 Implement handle_tool_call for wiki_write: resolve dir, slugify title, check if file exists (update vs create), call write_wiki_file, incremental index update
- [x] 2.4 Path safety: verify resolved path is under a configured wiki_dir (no traversal)
- [x] 2.5 Return JSON with success, path, title, action (created/updated), wikilinks extracted

## 3. Plugin — wiki_append Tool

- [x] 3.1 Add `WIKI_APPEND_SCHEMA` with title, content, section parameters
- [x] 3.2 Implement handle_tool_call for wiki_append: find page by title, call append_to_wiki_file, incremental index update
- [x] 3.3 Return JSON with success, path, title, section appended

## 4. Plugin — Incremental Index Update

- [x] 4.1 Implement `_incremental_update(path: str)`: parse file, find existing page in _pages by path, replace or append, rebuild word index for that page
- [x] 4.2 Handle new file (not in index): parse and append to _pages, add words to _index
- [x] 4.3 Handle updated file: replace page in _pages, remove old words from _index, add new words
- [x] 4.4 Thread safety: acquire self._lock during update

## 5. Plugin — sync_turn Session Logging

- [x] 5.1 Implement sync_turn: generate session slug from session_id (or timestamp fallback)
- [x] 5.2 Resolve Episodic/sessions/ directory from wiki_dirs
- [x] 5.3 On first call: create session file with frontmatter (title: "Session <date>", type: episodic, tags: [session, log])
- [x] 5.4 On subsequent calls: append timestamped entry with truncated user/assistant content (200 chars each)
- [x] 5.5 Incremental index update for the session file
- [x] 5.6 Guard: if Episodic/ not in wiki_dirs, skip silently (no error)

## 6. Plugin — Tool Registration

- [x] 6.1 Add WIKI_WRITE_SCHEMA and WIKI_APPEND_SCHEMA to get_tool_schemas()
- [x] 6.2 Update plugin docstring to mention write capabilities
- [x] 6.3 Update plugin.yaml description

## 7. Testing

- [x] 7.1 Test slugify: "My Cool Page!" → "my-cool-page.md", "AI/ML Concepts" → "ai-ml-concepts"
- [x] 7.2 Test wiki_write: create a new page, verify file exists with correct frontmatter
- [x] 7.3 Test wiki_write: update existing page, verify created date preserved, updated date bumped, tags merged
- [x] 7.4 Test wiki_write: verify page appears in search immediately after write (incremental index)
- [x] 7.5 Test wiki_append: append content to existing page, verify content updated
- [x] 7.6 Test wiki_append with section: verify section header added
- [x] 7.7 Test sync_turn: first call creates session file, verify frontmatter (type: episodic)
- [x] 7.8 Test sync_turn: second call appends entry, verify 2 timestamp entries
- [x] 7.9 Test sync_turn: session file is searchable via wiki_search
- [x] 7.10 Test path traversal: wiki_write with directory="../../../etc" is rejected
- [x] 7.11 Test directory routing: wiki_write to "Episodic" writes to Episodic/ dir
- [x] 7.12 Clean up test files — index back to 45 pages
