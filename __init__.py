"""QMD Wiki memory provider — first-class memory backed by .qmd/.md wiki files.

Turns a directory of Quarto markdown files (or plain .md) into a persistent,
searchable memory backend. Wiki pages are indexed on init, searched on
prefetch, and exposed via tools for on-demand retrieval.

Code cells in .qmd files can be executed for verification — the "living
knowledge" pattern where documentation proves itself.

Config (config.yaml under memory:):
  wiki_dir:           Path to wiki directory (default: auto-detect)
  execute_cells:      Whether to execute code cells on refresh (default: false)
  max_context_chars:  Max chars of wiki content to inject per turn (default: 2000)
  max_pages:          Max pages to return in prefetch (default: 3)

Or via env vars:
  QMD_WIKI_DIR
  QMD_EXECUTE_CELLS=true/false
"""

from __future__ import annotations

import logging
import os
import re
import threading
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

# Try to import MemoryProvider — may not be available during discovery
try:
    from agent.memory_provider import MemoryProvider
    _HAS_ABC = True
except Exception:
    _HAS_ABC = False
    class MemoryProvider:  # type: ignore
        """Fallback stub for discovery outside agent process."""
        pass


# Default wiki directories to check (first existing wins)
_DEFAULT_WIKI_DIRS = [
    os.path.expanduser("~/SynologyDrive/Obsidian Vault (Restructured)/04 - AI/Wiki"),
    os.path.expanduser("~/.hermes/wiki"),
]

# Tool schemas
WIKI_SEARCH_SCHEMA = {
    "name": "wiki_search",
    "description": (
        "Search the QMD wiki knowledge base. Returns matching pages with "
        "titles, tags, and excerpts. Use for recalling documented knowledge, "
        "concepts, comparisons, and entity information."
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
        },
        "required": ["query"],
    },
}

WIKI_READ_SCHEMA = {
    "name": "wiki_read",
    "description": (
        "Read a full wiki page by title or path. Returns the complete content "
        "including any executed code cell outputs."
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
        "Re-scan the wiki directory and rebuild the index. Also optionally "
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


class QMDWikiMemoryProvider(MemoryProvider):
    """Memory provider backed by .qmd/.md wiki files."""

    def __init__(self):
        self._wiki_dir: Optional[str] = None
        self._execute_cells: bool = False
        self._max_context_chars: int = 2000
        self._max_pages: int = 3
        self._pages: List[WikiPage] = []
        self._index: Dict[str, List[int]] = {}  # word -> [page indices]
        self._lock = threading.Lock()
        self._session_id: str = ""
        self._prefetch_cache: str = ""

    # -- Core identity --------------------------------------------------------

    @property
    def name(self) -> str:
        return "qmd-wiki"

    def is_available(self) -> bool:
        wiki_dir = self._resolve_wiki_dir()
        if not wiki_dir or not os.path.isdir(wiki_dir):
            return False
        # Check for at least one .qmd or .md file
        for ext in ("*.qmd", "*.md"):
            if list(Path(wiki_dir).rglob(ext)):
                return True
        return False

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "wiki_dir",
                "description": "Path to wiki directory (default: auto-detect from Obsidian vault or ~/.hermes/wiki)",
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
        import json
        config = {k: v for k, v in values.items() if not k.endswith("api_key")}
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

    def _load_config(self):
        """Load config from env vars or config file."""
        # Env vars take priority
        wiki_dir = os.environ.get("QMD_WIKI_DIR")
        if wiki_dir:
            self._wiki_dir = wiki_dir
        else:
            self._wiki_dir = self._resolve_wiki_dir()

        self._execute_cells = os.environ.get("QMD_EXECUTE_CELLS", "").lower() in ("true", "1", "yes")

        # Try loading config file
        try:
            from hermes_constants import get_hermes_home
            config_path = Path(get_hermes_home()) / "qmd-wiki.json"
            if config_path.exists():
                import json
                with open(config_path) as f:
                    cfg = json.load(f)
                if not wiki_dir and cfg.get("wiki_dir"):
                    self._wiki_dir = cfg["wiki_dir"]
                if cfg.get("execute_cells"):
                    self._execute_cells = bool(cfg["execute_cells"])
                if cfg.get("max_context_chars"):
                    self._max_context_chars = int(cfg["max_context_chars"])
                if cfg.get("max_pages"):
                    self._max_pages = int(cfg["max_pages"])
        except Exception:
            pass

    def _resolve_wiki_dir(self) -> Optional[str]:
        """Find the wiki directory."""
        if self._wiki_dir:
            return self._wiki_dir if os.path.isdir(self._wiki_dir) else None
        for d in _DEFAULT_WIKI_DIRS:
            if os.path.isdir(d):
                return d
        return None

    # -- Lifecycle -----------------------------------------------------------

    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id
        self._load_config()
        self._rebuild_index()

    def _rebuild_index(self, execute_cells: bool = False):
        """Scan wiki directory and build the search index."""
        wiki_dir = self._resolve_wiki_dir()
        if not wiki_dir:
            logger.warning("QMD Wiki: no wiki directory found")
            return

        exec_cells = execute_cells or self._execute_cells
        pages = []
        index: Dict[str, List[int]] = {}

        for ext in ("*.qmd", "*.md"):
            for path in sorted(Path(wiki_dir).rglob(ext)):
                # Skip files in special directories
                if "node_modules" in str(path) or ".git" in str(path):
                    continue
                try:
                    page = parse_wiki_file(str(path), execute_cells=exec_cells)
                    page_idx = len(pages)
                    pages.append(page)

                    # Index words from search_text
                    words = re.findall(r'\w+', page.search_text.lower())
                    for word in set(words):
                        if len(word) < 2:
                            continue
                        if word not in index:
                            index[word] = []
                        index[word].append(page_idx)
                except Exception as e:
                    logger.warning("QMD Wiki: failed to parse %s: %s", path, e)

        with self._lock:
            self._pages = pages
            self._index = index

        logger.info("QMD Wiki: indexed %d pages from %s", len(pages), wiki_dir)

    # -- System prompt -------------------------------------------------------

    def system_prompt_block(self) -> str:
        if not self._pages:
            return ""

        lines = [
            f"[QMD Wiki] {len(self._pages)} pages indexed.",
            "Use wiki_search to find knowledge, wiki_read to read full pages.",
            "Wiki topics:",
        ]

        # List page titles as a catalog
        for page in self._pages[:20]:
            tag_str = f" [{', '.join(page.tags)}]" if page.tags else ""
            lines.append(f"  - {page.title}{tag_str}")

        if len(self._pages) > 20:
            lines.append(f"  ...and {len(self._pages) - 20} more (use wiki_search)")

        return "\n".join(lines)

    # -- Prefetch ------------------------------------------------------------

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Return relevant wiki content for the upcoming turn."""
        if not self._pages:
            return self._prefetch_cache if self._prefetch_cache else ""

        results = self._search(query, top_k=self._max_pages)
        if not results:
            return ""

        # Also return cached prefetch from previous queue_prefetch
        if self._prefetch_cache:
            return self._prefetch_cache

        return self._format_results(results, max_chars=self._max_context_chars)

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        """Background recall for the next turn."""
        if not self._pages:
            return
        results = self._search(query, top_k=self._max_pages)
        self._prefetch_cache = self._format_results(results, max_chars=self._max_context_chars) if results else ""

    # -- Turn sync -----------------------------------------------------------

    def sync_turn(
        self,
        user_content: str,
        assistant_content: str,
        *,
        session_id: str = "",
        messages=None,
    ) -> None:
        """Non-blocking — nothing to write for a read-only wiki."""
        pass

    # -- Tools ---------------------------------------------------------------

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [WIKI_SEARCH_SCHEMA, WIKI_READ_SCHEMA, WIKI_REFRESH_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        import json
        try:
            if tool_name == "wiki_search":
                query = args.get("query", "")
                top_k = min(args.get("top_k", 5), 15)
                results = self._search(query, top_k=top_k)
                return json.dumps({
                    "success": True,
                    "results": [
                        {
                            "title": p.title,
                            "path": p.path,
                            "tags": p.tags,
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
                        "content": format_page_for_context(page, max_chars=8000),
                        "has_code": page.has_executable_code,
                    })
                return json.dumps({"success": False, "error": f"No wiki page matching '{title}'"})
            elif tool_name == "wiki_refresh":
                exec_cells = args.get("execute_cells", False)
                self._rebuild_index(execute_cells=exec_cells)
                return json.dumps({
                    "success": True,
                    "pages_indexed": len(self._pages),
                    "cells_executed": sum(1 for p in self._pages for c in p.code_cells if c.output or c.error) if exec_cells else 0,
                })
            return json.dumps({"success": False, "error": f"Unknown tool: {tool_name}"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # -- Search internals ----------------------------------------------------

    def _search(self, query: str, top_k: int = 5) -> List[WikiPage]:
        """Simple keyword search over the wiki index."""
        if not self._pages or not self._index:
            return []

        query_words = re.findall(r'\w+', query.lower())
        scores: Dict[int, int] = {}

        for word in query_words:
            if len(word) < 2:
                continue
            # Exact match
            if word in self._index:
                for idx in self._index[word]:
                    scores[idx] = scores.get(idx, 0) + 2
            # Prefix match
            for indexed_word, page_indices in self._index.items():
                if indexed_word.startswith(word) and indexed_word != word:
                    for idx in page_indices:
                        scores[idx] = scores.get(idx, 0) + 1

        ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_k]
        return [self._pages[idx] for idx, _ in ranked]

    def _find_page(self, title_or_path: str) -> Optional[WikiPage]:
        """Find a page by title (fuzzy) or path (partial)."""
        query_lower = title_or_path.lower()
        # Exact title match
        for page in self._pages:
            if page.title.lower() == query_lower:
                return page
        # Partial title match
        for page in self._pages:
            if query_lower in page.title.lower():
                return page
        # Path match
        for page in self._pages:
            if query_lower in page.path.lower():
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

    # -- Shutdown ------------------------------------------------------------

    def shutdown(self) -> None:
        pass


# -- Plugin registration ----------------------------------------------------

def register(ctx):
    """Plugin registration entry point."""
    ctx.register_memory_provider(QMDWikiMemoryProvider())
