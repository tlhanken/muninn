"""QMD Wiki parser — extract frontmatter, content, and code cells from .qmd/.md files.

Pure stdlib, no external dependencies. Works on NixOS.
"""

from __future__ import annotations

import re
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class CodeCell:
    """A fenced code cell from a .qmd file."""
    language: str
    source: str
    output: Optional[str] = None  # populated after execution
    error: Optional[str] = None
    line_start: int = 0


@dataclass
class WikiPage:
    """A parsed wiki page from a .qmd or .md file."""
    path: str
    title: str
    tags: List[str] = field(default_factory=list)
    last_verified: Optional[str] = None
    markdown: str = ""  # body without frontmatter, without code cell sources
    code_cells: List[CodeCell] = field(default_factory=list)
    raw: str = ""  # full file content

    @property
    def has_executable_code(self) -> bool:
        return any(c.language in ("python", "r", "bash", "sh") for c in self.code_cells)

    @property
    def search_text(self) -> str:
        """Flat text for search indexing — title, tags, markdown, code outputs."""
        parts = [self.title] + self.tags + [self.markdown]
        for cell in self.code_cells:
            if cell.output:
                parts.append(cell.output)
        return " ".join(parts)


def parse_frontmatter(content: str) -> Tuple[dict, str]:
    """Extract YAML frontmatter and return (metadata, body).

    Uses simple line-based parsing — no yaml dependency needed for basic
    title/tags/last_verified fields.
    """
    if not content.startswith("---"):
        return {}, content

    lines = content.split("\n")
    # Find closing ---
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}, content

    fm_text = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:])

    # Simple YAML parsing for common fields
    metadata = {}
    for line in fm_text.split("\n"):
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        # Handle quoted strings
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]

        # Handle list values [a, b, c]
        if value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip('"\'') for v in value[1:-1].split(",") if v.strip()]
            metadata[key] = items
        else:
            metadata[key] = value

    return metadata, body


def extract_code_cells(body: str) -> Tuple[str, List[CodeCell]]:
    """Extract fenced code cells from markdown body.

    Returns (markdown_without_code_sources, code_cells).
    Code cells are fenced blocks with language annotations like ```{python}
    or ```{r}. Regular code blocks (```) are kept in the markdown.
    """
    cells = []
    lines = body.split("\n")
    result_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for Quarto-style code cell: ```{python}
        match = re.match(r'^```(\{)?(\w+)(\})?', line.strip())
        if match and match.group(2):
            lang = match.group(2)
            # Only treat as code cell if it has the { } Quarto syntax
            # or if it's a python/r/bash block we want to track
            is_quarto_cell = bool(match.group(1) and match.group(3))

            if is_quarto_cell or lang in ("python", "r", "bash", "sh"):
                # Collect code until closing ```
                code_lines = []
                line_start = i + 1
                i += 1
                while i < len(lines) and lines[i].strip() != "```":
                    code_lines.append(lines[i])
                    i += 1
                # Skip closing ```
                i += 1

                cell = CodeCell(
                    language=lang,
                    source="\n".join(code_lines),
                    line_start=line_start,
                )
                cells.append(cell)

                # Replace with a placeholder in markdown
                result_lines.append(f"[code cell: {lang}]")
                continue

        result_lines.append(line)
        i += 1

    return "\n".join(result_lines), cells


def execute_code_cell(cell: CodeCell, timeout: int = 10) -> None:
    """Execute a code cell and populate cell.output or cell.error.

    Only supports Python cells. Uses subprocess for isolation.
    """
    if cell.language not in ("python", "py"):
        cell.output = f"[execution not supported for {cell.language}]"
        return

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(cell.source)
            f.flush()
            temp_path = f.name

        result = subprocess.run(
            ["python3", temp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        os.unlink(temp_path)

        if result.returncode == 0:
            cell.output = result.stdout.strip() if result.stdout.strip() else "[no output]"
            cell.error = None
        else:
            cell.output = None
            cell.error = result.stderr.strip()[-500:] if result.stderr else "unknown error"
    except subprocess.TimeoutExpired:
        cell.output = None
        cell.error = f"[timeout after {timeout}s]"
    except Exception as e:
        cell.output = None
        cell.error = f"[execution error: {e}]"
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


def parse_wiki_file(path: str, execute_cells: bool = False) -> WikiPage:
    """Parse a .qmd or .md file into a WikiPage.

    Args:
        path: Path to the file
        execute_cells: If True, execute Python code cells and capture output
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    metadata, body = parse_frontmatter(content)
    markdown, code_cells = extract_code_cells(body)

    page = WikiPage(
        path=path,
        title=metadata.get("title", path.split("/")[-1].replace(".qmd", "").replace(".md", "")),
        tags=metadata.get("tags", []),
        last_verified=metadata.get("last_verified"),
        markdown=markdown.strip(),
        code_cells=code_cells,
        raw=content,
    )

    if execute_cells:
        for cell in page.code_cells:
            if cell.language in ("python", "py"):
                execute_code_cell(cell)

    return page


def format_page_for_context(page: WikiPage, max_chars: int = 3000) -> str:
    """Format a wiki page for injection into session context."""
    lines = []
    lines.append(f"### {page.title}")
    if page.tags:
        lines.append(f"Tags: {', '.join(page.tags)}")
    if page.last_verified:
        lines.append(f"Last verified: {page.last_verified}")
    lines.append("")

    # Truncate markdown if too long
    md = page.markdown
    if len(md) > max_chars:
        md = md[:max_chars] + "\n...[truncated]"
    lines.append(md)

    # Include code cell outputs (not sources)
    for cell in page.code_cells:
        if cell.output:
            lines.append(f"\n```\n{cell.output}\n```")
        elif cell.error:
            lines.append(f"\n[execution error: {cell.error}]")

    return "\n".join(lines)
