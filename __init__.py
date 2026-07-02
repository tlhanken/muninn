"""QMD Wiki memory provider — Bridge wrapper around the QMD CLI search engine.

A thin "Bridge" between Hermes Agent and the QMD (github.com/tobi/qmd) CLI tool.
QMD handles all search and indexing (BM25 full-text + vector similarity + LLM
reranking). This plugin provides:

  - Directory orchestration via wiki_dirs config (per-agent isolation)
  - Write tools (wiki_write, wiki_append) with frontmatter management
  - Session logging via sync_turn (Episodic/sessions/)
  - OKF-aware search filtering (type, confidence, status) as post-processing
  - System prompt catalog (lightweight page listing)
  - Result shaping for LLM context injection

Config (~/.hermes/qmd-wiki.json):
  wiki_dirs:          List of directories to index (default: auto-detect)
  wiki_dir:           Legacy single directory (wrapped into wiki_dirs list)
  execute_cells:      Whether to execute code cells on refresh (default: false)
  max_context_chars:  Max chars of wiki content to inject per turn (default: 2000)
  max_pages:          Max pages to return in prefetch (default: 3)

Or via env vars:
  QMD_WIKI_DIR        (legacy — wrapped into single-element wiki_dirs)
  QMD_EXECUTE_CELLS=true/false
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Resolve parser relative to this file — register in sys.modules BEFORE
# exec_module so Python 3.13+ dataclass annotation resolution works.
import importlib.util
import sys as _sys
_parser_path = Path(__file__).parent / "parser.py"
_spec = importlib.util.spec_from_file_location("qmd_wiki_parser", str(_parser_path))
_parser_mod = importlib.util.module_from_spec(_spec)
_sys.modules["qmd_wiki_parser"] = _parser_mod
_spec.loader.exec_module(_parser_mod)

WikiPage = _parser_mod.WikiPage
parse_wiki_file = _parser_mod.parse_wiki_file
format_page_for_context = _parser_mod.format_page_for_context
slugify = _parser_mod.slugify
write_wiki_file = _parser_mod.write_wiki_file
append_to_wiki_file = _parser_mod.append_to_wiki_file

# Try to import MemoryProvider — may not be available during discovery
try:
    from agent.memory_provider import MemoryProvider
except Exception:
    class MemoryProvider:  # type: ignore
        """Fallback stub for discovery outside agent process."""
        pass


# QMD binary path (not in global PATH — built locally)
_QMD_BIN = os.path.expanduser("~/workspace/tools/qmd/bin/qmd")

# Default wiki directories to check (first existing wins, used when no config)
_DEFAULT_WIKI_DIRS = [
    os.path.expanduser("~/SynologyDrive/Obsidian Vault (Restructured)/04 - AI/Wiki"),
    os.path.expanduser("~/.hermes/wiki"),
]

# Confidence multipliers for search ranking (post-processing on QMD results)
_CONFIDENCE_WEIGHTS = {
    "high": 1.5,
    "medium": 1.0,
    "low": 0.7,
}

# Tool schemas
WIKI_SEARCH_SCHEMA = {
    "name": "wiki_search",
    "description": (
        "Search the QMD wiki knowledge base. Returns matching pages with "
        "titles, tags, and excerpts. Use for recalling documented knowledge, "
        "concepts, comparisons, and entity information. "
        "Optional type filter restricts results to a specific OKF page type "
        "(e.g., 'decision', 'episodic', 'concept', 'entity')."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for in the wiki.",
            },
            "top_k": {
                "type": "integer",
                "description": "Max results (default: 5, max: 15).",
            },
            "type": {
                "type": "string",
                "description": (
                    "Filter results by frontmatter type field "
                    "(e.g., 'decision', 'episodic', 'concept'). "
                    "Omit to search all types."
                ),
            },
        },
        "required": ["query"],
    },
}

WIKI_READ_SCHEMA = {
    "name": "wiki_read",
    "description": (
        "Read a full wiki page by title or path. Returns the complete content "
        "including any executed code cell outputs and extracted wikilinks."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Page title or partial path to read.",
            },
        },
        "required": ["title"],
    },
}

WIKI_REFRESH_SCHEMA = {
    "name": "wiki_refresh",
    "description": (
        "Re-scan the wiki directories and rebuild the QMD index. Also optionally "
        "executes code cells to verify wiki content is current."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "execute_cells": {
                "type": "boolean",
                "description": "Also execute Python code cells (default: false).",
            },
        },
        "required": [],
    },
}

WIKI_WRITE_SCHEMA = {
    "name": "wiki_write",
    "description": (
        "Create or update a wiki page. Auto-generates frontmatter with title, "
        "tags, type, confidence, and dates. File is named by slugifying the title. "
        "If the page already exists, preserves created date and merges tags. "
        "Wikilinks ([[target]]) in content are auto-extracted and indexed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Page title (human-readable, used in frontmatter).",
            },
            "content": {
                "type": "string",
                "description": "Markdown body content (without frontmatter — auto-generated).",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags for the page (merged with existing on update).",
            },
            "type": {
                "type": "string",
                "description": "OKF page type (e.g., 'concept', 'entity', 'decision', 'episodic').",
            },
            "confidence": {
                "type": "string",
                "description": "Confidence level: 'high', 'medium' (default), or 'low'.",
            },
            "directory": {
                "type": "string",
                "description": (
                    "Which directory to write to (basename of a configured wiki_dir, "
                    "e.g., 'Wiki', 'Episodic', 'Procedures'). "
                    "Default: first configured directory."
                ),
            },
        },
        "required": ["title", "content"],
    },
}

WIKI_APPEND_SCHEMA = {
    "name": "wiki_append",
    "description": (
        "Append content to an existing wiki page. Optionally adds a section "
        "header. Bumps the 'updated' date in frontmatter."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Title of the page to append to (fuzzy match).",
            },
            "content": {
                "type": "string",
                "description": "Content to append to the page.",
            },
            "section": {
                "type": "string",
                "description": "Optional section header to insert content under (e.g., 'Update 2024-01-15').",
            },
        },
        "required": ["title", "content"],
    },
}


class QMDWikiMemoryProvider(MemoryProvider):
    """Memory provider — thin Bridge wrapper around QMD CLI for search + indexing.

    QMD handles all search and indexing (BM25, vectors, reranking). This plugin:
      1. Orchestrates directories via wiki_dirs config
      2. Manages QMD collections (add, update, embed) on init/refresh
      3. Delegates search to 'qmd search --json' / 'qmd query --json'
      4. Applies OKF filtering (type, confidence, status) as post-processing
      5. Handles write operations (wiki_write, wiki_append) with frontmatter
      6. Logs session activity to Episodic/sessions/ via sync_turn
    """

    def __init__(self):
        self._wiki_dirs: List[str] = []
        self._execute_cells: bool = False
        self._max_context_chars: int = 2000
        self._max_pages: int = 3
        self._pages: List[WikiPage] = []
        self._collections_initialized: bool = False
        self._lock = threading.Lock()
        self._session_id: str = ""
        self._prefetch_cache: str = ""

    # -- Core identity --------------------------------------------------------

    @property
    def name(self) -> str:
        return "qmd-wiki"

    def is_available(self) -> bool:
        dirs = self._resolve_wiki_dirs()
        if not dirs:
            return False
        # Check for at least one .qmd or .md file across all dirs
        for d in dirs:
            if os.path.isdir(d):
                for ext in ("*.qmd", "*.md"):
                    if list(Path(d).rglob(ext)):
                        return True
        return False

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "wiki_dirs",
                "description": "List of directories to index (default: auto-detect)",
                "required": False,
            },
            {
                "key": "wiki_dir",
                "description": "Legacy single directory (wrapped into wiki_dirs list)",
                "required": False,
                "env_var": "QMD_WIKI_DIR",
            },
            {
                "key": "execute_cells",
                "description": "Execute Python code cells on refresh for verification",
                "required": False,
                "default": False,
                "env_var": "QMD_EXECUTE_CELLS",
            },
            {
                "key": "max_context_chars",
                "description": "Max chars of wiki content to inject per turn",
                "required": False,
                "default": 2000,
            },
            {
                "key": "max_pages",
                "description": "Max pages to return in prefetch",
                "required": False,
                "default": 3,
            },
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        """Write config to the provider's native location."""
        config_path = Path(hermes_home) / "qmd-wiki.json"
        config = {k: v for k, v in values.items() if not k.endswith("api_key")}
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    def _load_config(self):
        """Load config from env vars or config file."""
        # Env vars take priority (legacy single-dir)
        env_wiki_dir = os.environ.get("QMD_WIKI_DIR")
        self._execute_cells = os.environ.get("QMD_EXECUTE_CELLS", "").lower() in ("true", "1", "yes")

        # Try loading config file
        try:
            from hermes_constants import get_hermes_home
            config_path = Path(get_hermes_home()) / "qmd-wiki.json"
            if config_path.exists():
                with open(config_path) as f:
                    cfg = json.load(f)
                if cfg.get("wiki_dirs"):
                    self._wiki_dirs = [os.path.expanduser(d) for d in cfg["wiki_dirs"]]
                elif cfg.get("wiki_dir"):
                    # Legacy single dir
                    self._wiki_dirs = [os.path.expanduser(cfg["wiki_dir"])]
                if cfg.get("execute_cells"):
                    self._execute_cells = bool(cfg["execute_cells"])
                if cfg.get("max_context_chars"):
                    self._max_context_chars = int(cfg["max_context_chars"])
                if cfg.get("max_pages"):
                    self._max_pages = int(cfg["max_pages"])
        except Exception as e:
            logger.warning("QMD Wiki: failed to load config: %s", e)

        # Env var overrides config file (legacy)
        if env_wiki_dir:
            self._wiki_dirs = [os.path.expanduser(env_wiki_dir)]

    def _resolve_wiki_dirs(self) -> List[str]:
        """Find the wiki directories to index."""
        if self._wiki_dirs:
            # Filter to only dirs that exist
            return [d for d in self._wiki_dirs if os.path.isdir(d)]
        # Fallback to auto-detection (first existing default dir)
        for d in _DEFAULT_WIKI_DIRS:
            if os.path.isdir(d):
                return [d]
        return []

    # -- QMD CLI bridge -------------------------------------------------------

    def _run_qmd(self, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
        """Run a QMD CLI command and return the result.

        Args:
            *args: Command arguments (e.g. "search", "query", "--json")
            timeout: Max seconds to wait (default 60, longer for embed)

        Returns:
            subprocess.CompletedProcess with stdout/stderr captured
        """
        cmd = [_QMD_BIN] + list(args)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                logger.warning("QMD Wiki: qmd %s exit code %d: %s",
                               args[0] if args else "", result.returncode,
                               result.stderr.strip()[:200])
            return result
        except FileNotFoundError:
            logger.error("QMD Wiki: QMD binary not found at %s", _QMD_BIN)
            raise
        except subprocess.TimeoutExpired:
            logger.error("QMD Wiki: qmd %s timed out after %ds",
                         args[0] if args else "", timeout)
            raise

    def _collection_name(self, wiki_dir: str) -> str:
        """Derive a QMD collection name from a wiki directory path."""
        # Use the directory basename, sanitized for QMD
        return os.path.basename(wiki_dir).lower().replace(" ", "-")

    def _init_collections(self) -> None:
        """Ensure QMD collections exist for all configured wiki_dirs.

        Tries 'qmd collection add' for each dir. If the collection already
        exists, QMD exits non-zero with 'already exists' — that's fine.
        After adding, runs 'qmd update' to index files.
        Only runs 'qmd embed' on first-time setup (new collections added).
        """
        if self._collections_initialized:
            return

        dirs = self._resolve_wiki_dirs()
        if not dirs:
            return

        # Try adding each collection; track if any are new
        added_any = False
        for wiki_dir in dirs:
            name = self._collection_name(wiki_dir)
            try:
                result = self._run_qmd("collection", "add", wiki_dir, "--name", name)
                if result.returncode == 0:
                    logger.info("QMD Wiki: added collection '%s' for %s", name, wiki_dir)
                    added_any = True
                else:
                    # "already exists" or other error — skip
                    logger.debug("QMD Wiki: collection '%s' already exists", name)
            except Exception as e:
                logger.warning("QMD Wiki: error adding collection '%s': %s", name, e)

        # Update index (always — picks up any changes)
        try:
            self._run_qmd("update")
            logger.info("QMD Wiki: collections updated")
        except Exception as e:
            logger.warning("QMD Wiki: update failed: %s", e)

        # Embed on first setup only (new collections need vectors)
        if added_any:
            try:
                self._run_qmd("embed", "--max-docs-per-batch", "100", "--timeout", "10")
                logger.info("QMD Wiki: vectors generated")
            except Exception as e:
                logger.warning("QMD Wiki: embed failed (non-fatal): %s", e)
                logger.info("QMD Wiki: search will use BM25-only until embed runs")

        self._collections_initialized = True

        # Exclude session logs from default QMD search
        # They're still indexed but won't appear in unscoped wiki_search queries.
        # The dreaming cron and explicit -c sessions queries still work.
        for wiki_dir in dirs:
            sessions_dir = os.path.join(wiki_dir, "sessions")
            if os.path.isdir(sessions_dir) and os.path.basename(wiki_dir) == "Episodic":
                try:
                    # Ensure sessions collection exists
                    self._run_qmd("collection", "add", sessions_dir, "--name", "sessions")
                except Exception:
                    pass  # already exists or other — non-fatal
                try:
                    self._run_qmd("collection", "exclude", "sessions")
                    logger.info("QMD Wiki: session logs excluded from default search")
                except Exception as e:
                    logger.debug("QMD Wiki: could not exclude sessions collection: %s", e)

    # -- Lifecycle ------------------------------------------------------------

    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id
        self._load_config()
        self._scan_pages_for_catalog()
        self._init_collections()

    def _scan_pages_for_catalog(self, execute_cells: bool = False):
        """Lightweight file scan for the system prompt catalog.

        Walks wiki_dirs and parses files for title/tags/source_dir metadata.
        Does NOT build search indices — that's QMD's job. The catalog only
        shows the agent what pages exist so it can decide what to search for.
        """
        dirs = self._resolve_wiki_dirs()
        if not dirs:
            logger.warning("QMD Wiki: no wiki directories found")
            return

        exec_cells = execute_cells or self._execute_cells
        pages = []

        for wiki_dir in dirs:
            if not os.path.isdir(wiki_dir):
                logger.warning("QMD Wiki: directory not found: %s", wiki_dir)
                continue

            for ext in ("*.qmd", "*.md"):
                for path in sorted(Path(wiki_dir).rglob(ext)):
                    # Skip files in special directories
                    path_str = str(path)
                    if "node_modules" in path_str or ".git" in path_str:
                        continue
                    # Skip underscore-prefixed directories (working state)
                    if any(part.startswith("_") for part in path.parts):
                        continue
                    try:
                        page = parse_wiki_file(str(path), execute_cells=exec_cells)
                        page.source_dir = wiki_dir
                        pages.append(page)
                    except Exception as e:
                        logger.warning("QMD Wiki: failed to parse %s: %s", path, e)

        with self._lock:
            self._pages = pages

        logger.info("QMD Wiki: catalog has %d pages from %d directories",
                     len(pages), len(dirs))

    # -- System prompt --------------------------------------------------------

    def system_prompt_block(self) -> str:
        if not self._pages:
            return ""

        # Count pages per source directory
        dir_counts: Dict[str, int] = {}
        for page in self._pages:
            dir_name = os.path.basename(page.source_dir) if page.source_dir else "unknown"
            dir_counts[dir_name] = dir_counts.get(dir_name, 0) + 1

        lines = [
            f"[QMD Wiki] {len(self._pages)} pages indexed across {len(dir_counts)} directories.",
            "Use wiki_search to find knowledge, wiki_read to read full pages.",
            "Wiki topics:",
        ]

        # Show per-directory counts
        for dir_name, count in sorted(dir_counts.items()):
            lines.append(f"  {dir_name}/ ({count})")

        lines.append("")

        # List page titles as a catalog
        for page in self._pages[:20]:
            tag_str = f" [{', '.join(page.tags)}]" if page.tags else ""
            summary_str = ""
            if page.summary:
                summary_trunc = page.summary[:80]
                if len(page.summary) > 80:
                    summary_trunc += "..."
                summary_str = f" — {summary_trunc}"
            lines.append(f"  - {page.title}{tag_str}{summary_str}")

        if len(self._pages) > 20:
            lines.append(f"  ...and {len(self._pages) - 20} more (use wiki_search)")

        return "\n".join(lines)

    # -- Prefetch -------------------------------------------------------------

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Return relevant wiki content for the upcoming turn."""
        if not self._pages:
            return self._prefetch_cache if self._prefetch_cache else ""

        # Return cached prefetch from previous queue_prefetch if available
        if self._prefetch_cache:
            return self._prefetch_cache

        results = self._search(query, top_k=self._max_pages)
        if not results:
            return ""

        return self._format_results(results, max_chars=self._max_context_chars)

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        """Background recall for the next turn."""
        if not self._pages:
            return
        results = self._search(query, top_k=self._max_pages)
        self._prefetch_cache = self._format_results(results, max_chars=self._max_context_chars) if results else ""

    # -- Turn sync ------------------------------------------------------------

    def sync_turn(
        self,
        user_content: str,
        assistant_content: str,
        *,
        session_id: str = "",
        messages=None,
    ) -> None:
        """Lightweight session logging — append a timestamped entry to Episodic/sessions/.

        On first call per session, creates a session file with frontmatter.
        On subsequent calls, appends a truncated entry. No LLM processing.
        If Episodic/ is not in wiki_dirs, skips silently.
        """
        try:
            self._log_session_turn(session_id, user_content, assistant_content)
        except Exception as e:
            logger.debug("QMD Wiki: sync_turn logging failed: %s", e)

    def _log_session_turn(self, session_id: str, user_content: str, assistant_content: str) -> None:
        """Write a session log entry to Episodic/sessions/.

        Writes full user and assistant content (no truncation).
        Caps at 200 entries per file — oldest 25 stripped when exceeded.
        Tags each session file with the agent profile name.
        """
        # Find Episodic/ in wiki_dirs
        dirs = self._resolve_wiki_dirs()
        episodic_dir = None
        for d in dirs:
            if os.path.basename(d) == "Episodic":
                episodic_dir = d
                break
        if not episodic_dir:
            return  # Episodic/ not configured — skip silently

        sessions_dir = os.path.join(episodic_dir, "sessions")
        os.makedirs(sessions_dir, exist_ok=True)

        # Generate session slug
        now = datetime.now(timezone.utc)
        if session_id:
            sid_hash = hashlib.sha256(session_id.encode()).hexdigest()[:8]
            session_slug = f"session-{now.strftime('%Y-%m-%d')}-{sid_hash}"
        else:
            session_slug = f"session-{now.strftime('%Y-%m-%d-%H%M')}"

        session_path = os.path.join(sessions_dir, f"{session_slug}.md")
        timestamp = now.strftime("%Y-%m-%d %H:%M UTC")

        # Detect agent profile name from hermes_home path
        agent_name = self._detect_profile_name()

        # Format full content entry (preserve multi-line)
        # Break triple backticks to avoid nesting in markdown
        user_clean = user_content.replace("```", "`\u200b`\u200b`")
        asst_clean = assistant_content.replace("```", "`\u200b`\u200b`")
        entry = (
            f"### {timestamp}\n\n"
            f"**User:**\n\n{user_clean}\n\n"
            f"**Assistant:**\n\n{asst_clean}\n\n"
        )

        if not os.path.exists(session_path):
            # Create new session file (first turn) with agent metadata
            tags = ["session", "log", f"agent:{agent_name}"]
            write_wiki_file(
                path=session_path,
                title=f"Session {now.strftime('%Y-%m-%d')}",
                content=entry,
                tags=tags,
                page_type="episodic",
                confidence="medium",
            )
            # Inject agent field into frontmatter
            try:
                self._inject_frontmatter_field(session_path, "agent", agent_name)
            except Exception:
                pass  # non-fatal
            return

        # Existing file — read current content, check cap, append
        try:
            with open(session_path, "r", encoding="utf-8") as f:
                current_content = f.read()

            # Separate frontmatter from body
            if current_content.startswith("---"):
                _, fm, body = current_content.split("---", 2)
                frontmatter_block = f"---{fm}---"
            else:
                frontmatter_block = ""
                body = current_content

            # Count entries by timestamp-patterned ### headers only
            # Using regex to match ### <ISO-date> — this prevents markdown
            # ### headers inside messages from being counted as entries.
            entry_boundary = re.compile(r'^### \d{4}-\d{2}-\d{2}', re.MULTILINE)
            entry_matches = list(entry_boundary.finditer(body))
            max_entries = 200

            if len(entry_matches) >= max_entries:
                # Strip oldest 25 entries (find the 26th-oldest boundary)
                strip_index = entry_matches[24].start() if len(entry_matches) > 24 else 0
                body = body[strip_index:]

            # Append new entry
            new_body = body.rstrip() + "\n\n" + entry

            if frontmatter_block:
                full_content = frontmatter_block + "\n" + new_body
            else:
                full_content = new_body

            with open(session_path, "w", encoding="utf-8") as f:
                f.write(full_content)
        except Exception as e:
            logger.warning("QMD Wiki: failed to append session turn: %s", e)
            # Fallback: use append_to_wiki_file
            append_to_wiki_file(session_path, entry)

    def _detect_profile_name(self) -> str:
        """Detect the current Hermes profile name from hermes_home path.

        Returns 'default' if no named profile is active.
        """
        try:
            from hermes_constants import get_hermes_home
            home = get_hermes_home()
            # Path pattern: ~/.hermes/profiles/<name>/
            m = re.search(r'/profiles/([^/]+)', home)
            if m:
                return m.group(1)
        except Exception:
            pass
        return "default"

    def _inject_frontmatter_field(self, file_path: str, field: str, value: str) -> None:
        """Inject a field into the YAML frontmatter of a markdown file.

        Opens the file, finds the frontmatter block, inserts the field
        after the 'tags:' line (or at the end of frontmatter), and rewrites.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if not content.startswith("---"):
            return

        _, fm, body = content.split("---", 2)
        # Check if field already exists as its own line (not inside tags)
        if re.search(rf'^{re.escape(field)}:', fm, re.MULTILINE):
            return  # already present

        lines = fm.split("\n")
        # Find insertion point: after tags or after status
        insert_after = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("tags:"):
                insert_after = i
            elif line.strip().startswith("status:"):
                insert_after = i

        if insert_after >= 0:
            lines.insert(insert_after + 1, f"{field}: {value}")
        else:
            # Insert before the last line (---)
            lines.insert(-1, f"{field}: {value}")

        new_fm = "\n".join(lines)
        new_content = f"---{new_fm}---{body}"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    # -- Tools ----------------------------------------------------------------

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [WIKI_SEARCH_SCHEMA, WIKI_READ_SCHEMA, WIKI_REFRESH_SCHEMA,
                WIKI_WRITE_SCHEMA, WIKI_APPEND_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        try:
            if tool_name == "wiki_search":
                query = args.get("query", "")
                top_k = min(args.get("top_k", 5), 15)
                page_type = args.get("type")
                results = self._search(query, top_k=top_k, page_type=page_type)
                return json.dumps({
                    "success": True,
                    "results": [
                        {
                            "title": p.title,
                            "path": p.path,
                            "tags": p.tags,
                            "type": p.page_type,
                            "confidence": p.confidence,
                            "summary": p.summary,
                            "excerpt": p.markdown[:200] + "..." if len(p.markdown) > 200 else p.markdown,
                        }
                        for p in results
                    ],
                    "total": len(results),
                })
            elif tool_name == "wiki_read":
                title = args.get("title", "")
                page = self._find_page(title)
                if page:
                    return json.dumps({
                        "success": True,
                        "title": page.title,
                        "tags": page.tags,
                        "type": page.page_type,
                        "confidence": page.confidence,
                        "status": page.status,
                        "summary": page.summary,
                        "content": format_page_for_context(page, max_chars=8000),
                        "has_code": page.has_executable_code,
                        "wikilinks": page.wikilinks,
                    })
                return json.dumps({"success": False, "error": f"No wiki page matching '{title}'"})
            elif tool_name == "wiki_refresh":
                exec_cells = args.get("execute_cells", False)
                self._scan_pages_for_catalog(execute_cells=exec_cells)
                # Also tell QMD to re-index
                try:
                    self._run_qmd("update")
                except Exception as e:
                    logger.warning("QMD Wiki: refresh update failed: %s", e)
                return json.dumps({
                    "success": True,
                    "pages_indexed": len(self._pages),
                    "cells_executed": sum(1 for p in self._pages for c in p.code_cells if c.output or c.error) if exec_cells else 0,
                })
            elif tool_name == "wiki_write":
                return self._handle_wiki_write(args)
            elif tool_name == "wiki_append":
                return self._handle_wiki_append(args)
            return json.dumps({"success": False, "error": f"Unknown tool: {tool_name}"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # -- Search (QMD delegation) ----------------------------------------------

    def _search(self, query: str, top_k: int = 5, page_type: Optional[str] = None) -> List[WikiPage]:
        """Search via QMD CLI delegation.

        Uses 'qmd search --json --full-path' for BM25 full-text search (fast path).
        Falls back to 'qmd query' for hybrid search if BM25 returns nothing.

        Applies OKF filtering (type, confidence, status) as post-processing.
        """
        if not self._pages:
            return []

        dirs = self._resolve_wiki_dirs()
        qmd_paths: List[str] = []

        # Fast path: BM25 keyword search
        try:
            result = self._run_qmd("search", query, "--json", "-n", str(top_k * 3),
                                   "--full-path", "--min-score", "0.1")
            qmd_results = json.loads(result.stdout) if result.stdout else []
            qmd_paths = [r.get("file", "") for r in qmd_results if isinstance(r, dict) and r.get("file")]
        except Exception as e:
            logger.debug("QMD Wiki: BM25 search failed (%s), trying query...", e)

        # Fallback: hybrid query (slower but better quality)
        if not qmd_paths:
            try:
                result = self._run_qmd("query", query, "--json", "-n", str(top_k * 3),
                                       "--no-rerank", "--full-path", "--min-score", "0.1",
                                       timeout=120)
                qmd_results = json.loads(result.stdout) if result.stdout else []
                qmd_paths = [r.get("file", "") for r in qmd_results if isinstance(r, dict) and r.get("file")]
            except Exception as e:
                logger.debug("QMD Wiki: hybrid query failed: %s", e)
                return []

        # Map QMD file paths to our WikiPage objects (absolute path matching)
        abs_pages = {os.path.abspath(p.path): p for p in self._pages}
        matched: List[WikiPage] = []
        seen_paths: set = set()

        for match_path in qmd_paths:
            match_abs = os.path.abspath(os.path.expanduser(match_path))
            if match_abs in seen_paths:
                continue
            seen_paths.add(match_abs)

            page = abs_pages.get(match_abs)
            if page:
                matched.append(page)
            else:
                # Not in our catalog — try parsing it on the fly
                if os.path.isfile(match_abs):
                    try:
                        page = parse_wiki_file(match_abs)
                        for d in dirs:
                            if match_abs.startswith(os.path.abspath(d)):
                                page.source_dir = d
                                break
                        matched.append(page)
                    except Exception:
                        pass

        # Apply OKF filtering (type, confidence, status) as post-processing
        filtered = []
        for page in matched:
            if page.status in ("superseded", "rejected"):
                continue
            if page_type and page.page_type != page_type:
                continue
            filtered.append(page)

        # Apply confidence re-weighting (tiebreaker within QMD's ordering)
        confidence_order = {"high": 0, "medium": 1, "low": 2}
        filtered.sort(key=lambda p: (confidence_order.get(p.confidence, 1), p.title))

        return filtered[:top_k]

    def _find_page(self, title_or_path: str) -> Optional[WikiPage]:
        """Find a page by title (fuzzy), path (partial), or wikilink target.

        Tries: exact title, partial title, path substring, wikilink target.
        Falls back to reading from filesystem if not in catalog.
        """
        query_lower = title_or_path.lower()

        # Search our catalog first
        for page in self._pages:
            if page.title.lower() == query_lower:
                return page
        for page in self._pages:
            if query_lower in page.title.lower():
                return page
        for page in self._pages:
            if query_lower in page.path.lower():
                return page
        # Wikilink match
        for page in self._pages:
            for wl in page.wikilinks:
                if query_lower == wl.lower():
                    target = self._find_page_by_title(wl)
                    return target or page

        # Not in catalog — try reading directly from filesystem
        dirs = self._resolve_wiki_dirs()
        for d in dirs:
            for root, _, files in os.walk(d):
                for fname in files:
                    if fname.endswith((".md", ".qmd")):
                        fpath = os.path.join(root, fname)
                        fname_lower = fname.lower()
                        slug = slugify(title_or_path)
                        if slug in fname_lower or query_lower in fname_lower:
                            try:
                                page = parse_wiki_file(fpath)
                                page.source_dir = d
                                return page
                            except Exception:
                                continue

        # Final fallback: try QMD get
        try:
            result = self._run_qmd("get", "--full-path", title_or_path)
            if result.returncode == 0 and result.stdout.strip():
                # QMD returns the file path in the header
                for line in result.stdout.split("\n"):
                    if ":" in line:
                        potential_path = line.split(":")[0].strip()
                        if os.path.isfile(potential_path):
                            return parse_wiki_file(potential_path)
        except Exception:
            pass

        return None

    def _find_page_by_title(self, title: str) -> Optional[WikiPage]:
        """Find a page by exact title match (case-insensitive)."""
        title_lower = title.lower()
        for page in self._pages:
            if page.title.lower() == title_lower:
                return page
        for page in self._pages:
            if title_lower in page.title.lower():
                return page
        return None

    def _format_results(self, pages: List[WikiPage], max_chars: int = 2000) -> str:
        """Format search results for context injection."""
        if not pages:
            return ""

        lines = ["[QMD Wiki Context]"]
        budget = max_chars
        for page in pages:
            page_text = format_page_for_context(page, max_chars=min(budget, 1000))
            if len(page_text) > budget:
                page_text = page_text[:budget] + "...[truncated]"
            lines.append(page_text)
            budget -= len(page_text)
            if budget <= 0:
                break
        return "\n\n".join(lines)

    # -- Write handlers -------------------------------------------------------

    def _resolve_write_dir(self, directory: Optional[str]) -> Optional[str]:
        """Resolve a directory basename to a full path from wiki_dirs.

        Returns None if no match found. If directory is None, returns the
        first configured wiki_dir.
        """
        dirs = self._resolve_wiki_dirs()
        if not dirs:
            return None
        if not directory:
            return dirs[0]
        for d in dirs:
            if os.path.basename(d) == directory:
                return d
        return None

    def _handle_wiki_write(self, args: Dict[str, Any]) -> str:
        """Handle wiki_write tool call — create or update a wiki page."""
        title = args.get("title", "").strip()
        content = args.get("content", "").strip()
        if not title or not content:
            return json.dumps({"success": False, "error": "title and content are required"})

        tags = args.get("tags", [])
        page_type = args.get("type")
        confidence = args.get("confidence")
        if confidence is not None and confidence not in ("high", "medium", "low"):
            confidence = "medium"
        directory = args.get("directory")

        # Resolve write directory
        write_dir = self._resolve_write_dir(directory)
        if not write_dir:
            return json.dumps({
                "success": False,
                "error": f"Directory '{directory}' not found in wiki_dirs. Available: {[os.path.basename(d) for d in self._resolve_wiki_dirs()]}"
            })

        # Slugify title and build path
        filename = slugify(title) + ".md"
        file_path = os.path.join(write_dir, filename)

        # Path safety: verify resolved path is under write_dir
        if not os.path.abspath(file_path).startswith(os.path.abspath(write_dir)):
            return json.dumps({"success": False, "error": "Path traversal detected — write rejected"})

        # On update: preserve existing type/confidence if not explicitly provided
        if page_type is None or confidence is None:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    existing_content = f.read()
                existing_meta, _ = _parser_mod.parse_frontmatter(existing_content)
                if page_type is None:
                    page_type = existing_meta.get("type")
                if confidence is None:
                    confidence = existing_meta.get("confidence", "medium")
                    if confidence not in ("high", "medium", "low"):
                        confidence = "medium"

        if confidence is None:
            confidence = "medium"

        # Write the file
        result = write_wiki_file(
            path=file_path,
            title=title,
            content=content,
            tags=tags,
            page_type=page_type,
            confidence=confidence,
        )

        # Reflect the change in our catalog
        self._catalog_update(file_path)

        return json.dumps({
            "success": True,
            "action": result["action"],
            "path": file_path,
            "title": title,
            "tags": result["tags"],
            "wikilinks": result["wikilinks"],
            "message": f"Page {'created' if result['action'] == 'created' else 'updated'}: {title}",
        })

    def _handle_wiki_append(self, args: Dict[str, Any]) -> str:
        """Handle wiki_append tool call — append to an existing wiki page."""
        title = args.get("title", "").strip()
        content = args.get("content", "").strip()
        if not title or not content:
            return json.dumps({"success": False, "error": "title and content are required"})

        section = args.get("section")

        # Find the page by title
        page = self._find_page(title)
        if not page:
            return json.dumps({"success": False, "error": f"No wiki page matching '{title}' to append to"})

        # Append to the file
        append_to_wiki_file(page.path, content, section=section)

        # Reflect the change in our catalog
        self._catalog_update(page.path)

        return json.dumps({
            "success": True,
            "path": page.path,
            "title": page.title,
            "section": section,
            "message": f"Content appended to '{page.title}'" + (f" under section '{section}'" if section else ""),
        })

    def _catalog_update(self, path: str) -> None:
        """Re-parse a single file and update the catalog.

        A lightweight version of the old incremental update — just re-parses
        the file and swaps it in self._pages. QMD handles its own indexing
        via 'qmd update' called externally.
        """
        if not os.path.exists(path):
            # File was deleted — remove from catalog
            with self._lock:
                self._pages = [p for p in self._pages
                               if os.path.abspath(p.path) != os.path.abspath(path)]
            return

        try:
            new_page = parse_wiki_file(path)
            # Determine source_dir
            for d in self._resolve_wiki_dirs():
                if os.path.abspath(path).startswith(os.path.abspath(d)):
                    new_page.source_dir = d
                    break
        except Exception as e:
            logger.warning("QMD Wiki: catalog update failed for %s: %s", path, e)
            return

        with self._lock:
            # Find and replace existing page, or append
            for i, p in enumerate(self._pages):
                if os.path.abspath(p.path) == os.path.abspath(path):
                    self._pages[i] = new_page
                    return
            self._pages.append(new_page)

    # -- Shutdown -------------------------------------------------------------

    def shutdown(self) -> None:
        pass


# -- Plugin registration ----------------------------------------------------

def register(ctx):
    """Plugin registration entry point."""
    ctx.register_memory_provider(QMDWikiMemoryProvider())
