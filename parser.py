"""QMD Wiki parser — extract frontmatter, content, code cells, and wikilinks from .qmd/.md files.

Pure stdlib, no external dependencies. Works on NixOS.
"""

from __future__ import annotations

import re
import os
import subprocess
import tempfile
import textwrap
from datetime import datetime, timezone
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

    # OKF metadata (from frontmatter)
    page_type: Optional[str] = None  # frontmatter "type" field
    confidence: str = "medium"  # "high", "medium", "low" (default medium)
    status: str = "active"  # "active", "superseded", "rejected" (default active)

    # Wikilinks extracted from markdown body
    wikilinks: List[str] = field(default_factory=list)

    # Summary: from frontmatter or auto-extracted from first paragraph
    summary: str = ""

    # Which wiki_dir this page was indexed from (set by _rebuild_index)
    source_dir: str = ""

    @property
    def has_executable_code(self) -> bool:
        return any(c.language in ("python", "r", "bash", "sh") for c in self.code_cells)

    @property
    def search_text(self) -> str:
        """Flat text for search indexing — title, tags, summary, markdown, code outputs, wikilinks."""
        parts = [self.title] + self.tags + [self.summary, self.markdown]
        for cell in self.code_cells:
            if cell.output:
                parts.append(cell.output)
        # Include wikilink targets in search text so [[link]] targets are searchable
        parts.extend(self.wikilinks)
        return " ".join(parts)


def parse_frontmatter(content: str) -> Tuple[dict, str]:
    """Extract YAML frontmatter and return (metadata, body).

    Uses simple line-based parsing — no yaml dependency needed for basic
    title/tags/last_verified/type/confidence/status fields.
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


def extract_wikilinks(text: str) -> List[str]:
    """Extract [[wikilink]] targets from markdown text.

    Supports:
      [[Page Name]]           → "Page Name"
      [[page-name]]           → "page-name"
      [[alias|display text]]  → "page-name" (alias is the target)
    Returns de-duplicated list preserving order.
    """
    links = re.findall(r'\[\[([^\]]+)\]\]', text)
    seen = set()
    result = []
    for link in links:
        # Handle alias syntax: [[target|display text]]
        target = link.split("|")[0].strip() if "|" in link else link.strip()
        if target and target not in seen:
            seen.add(target)
            result.append(target)
    return result


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

    temp_path = None
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
        if temp_path:
            try:
                os.unlink(temp_path)
            except Exception:
                pass


def _strip_markdown_noise(text: str) -> str:
    """Strip common markdown formatting, preserving inner text.

    Removes fenced code blocks, inline code (keeping inner text), and
    bold/italic markers. Used by summary extraction.
    """
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return text


def extract_summary(
    text: str,
    max_chars: int = 200,
    mode: str = "paragraph",
) -> str:
    """Extract a summary from markdown text.

    Modes:
      "paragraph" — first meaningful paragraph (page catalog summaries).
      "sentence"  — first meaningful sentence of the first meaningful line
                    (session closeout summaries).

    Shared logic (both modes): strip markdown noise, skip headings, list
    items, separators, and empty lines; clean wikilink syntax.
    """
    cleaned = _strip_markdown_noise(text)

    def _cleaned_line(line: str) -> Optional[str]:
        line = line.strip()
        if not line:
            return None
        if line.startswith("#"):
            return None
        if line.startswith("[code cell:"):
            return None
        if line == "---" or line == "***":
            return None
        if mode == "sentence" and (line.startswith("- ") or line.startswith("* ")):
            return None
        # Clean wikilink syntax for readability
        return re.sub(r"\[\[([^\]|]+)(\|[^\]]+)?\]\]", r"\1", line)

    for line in cleaned.split("\n"):
        line = _cleaned_line(line)
        if not line:
            continue
        if mode == "sentence":
            sentence = re.split(r"(?<=[.!?])\s+", line)[0].strip().strip("`\"'")
            if not sentence:
                continue
            return textwrap.shorten(
                sentence, width=max_chars, placeholder="..."
            ) if len(sentence) > max_chars else sentence
        # paragraph mode
        return textwrap.shorten(
            line, width=max_chars, placeholder="..."
        ) if len(line) > max_chars else line
    return ""


def _auto_summary(markdown: str, max_chars: int = 200) -> str:
    """Auto-generate a summary from the first meaningful paragraph of markdown.

    Thin wrapper over the shared ``extract_summary`` (paragraph mode).
    """
    return extract_summary(markdown, max_chars=max_chars, mode="paragraph")


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

    # Extract OKF metadata from frontmatter
    page_type = metadata.get("type")
    confidence = metadata.get("confidence", "medium")
    if confidence not in ("high", "medium", "low"):
        confidence = "medium"

    status = metadata.get("status", "active")
    if status not in ("active", "superseded", "rejected", "candidate"):
        status = "active"

    # Extract wikilinks from the markdown body
    wikilinks = extract_wikilinks(markdown)

    # Extract summary: from frontmatter or auto-generate from first paragraph
    summary = metadata.get("summary", "")
    if not summary:
        summary = _auto_summary(markdown)

    page = WikiPage(
        path=path,
        title=metadata.get("title", path.split("/")[-1].replace(".qmd", "").replace(".md", "")),
        tags=metadata.get("tags", []),
        last_verified=metadata.get("last_verified"),
        markdown=markdown.strip(),
        code_cells=code_cells,
        raw=content,
        page_type=page_type,
        confidence=confidence,
        status=status,
        wikilinks=wikilinks,
        summary=summary,
    )

    if execute_cells:
        for cell in page.code_cells:
            if cell.language in ("python", "py"):
                execute_code_cell(cell)

    return page


def slugify(title: str) -> str:
    """Convert a title to a SCHEMA-compliant filename (without extension).

    Rules: lowercase, spaces → hyphens, strip non-alphanumeric except hyphens,
    collapse consecutive hyphens, max 80 chars, no leading/trailing hyphens.
    """
    s = title.lower().strip()
    s = re.sub(r'[/\\._]', ' ', s)      # separators → spaces (before strip)
    s = re.sub(r'[^a-z0-9\s-]', '', s)  # strip non-alphanumeric (keep spaces, hyphens)
    s = re.sub(r'[\s]+', '-', s)         # spaces → hyphens
    s = re.sub(r'-+', '-', s)            # collapse consecutive hyphens
    s = s.strip('-')                      # no leading/trailing hyphens
    if len(s) > 80:
        s = s[:80].rsplit('-', 1)[0]     # cut at word boundary near 80 chars
    return s or 'untitled'


def generate_frontmatter(
    title: str,
    tags: Optional[List[str]] = None,
    page_type: Optional[str] = None,
    confidence: str = "medium",
    status: str = "active",
    created: Optional[str] = None,
    updated: Optional[str] = None,
    extra_fields: Optional[dict] = None,
) -> str:
    """Generate YAML frontmatter string for a wiki page.

    Returns the frontmatter block including opening/closing --- delimiters.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if created is None:
        created = now
    if updated is None:
        updated = now

    lines = ["---"]
    lines.append(f'title: "{title}"')
    if tags:
        lines.append(f'tags: [{", ".join(tags)}]')
    if page_type:
        lines.append(f'type: {page_type}')
    lines.append(f'confidence: {confidence}')
    lines.append(f'status: {status}')
    lines.append(f'created: {created}')
    lines.append(f'updated: {updated}')
    if extra_fields:
        for k, v in extra_fields.items():
            lines.append(f'{k}: {v}')
    lines.append("---")
    return "\n".join(lines)


def write_wiki_file(
    path: str,
    title: str,
    content: str,
    tags: Optional[List[str]] = None,
    page_type: Optional[str] = None,
    confidence: str = "medium",
    status: str = "active",
) -> dict:
    """Write a wiki page to disk with auto-generated frontmatter.

    If the file already exists, preserve the created date and merge tags.
    Returns a dict with metadata about the write operation.
    """
    tags = tags or []
    created = None
    action = "created"

    if os.path.exists(path):
        # Read existing file to preserve created date and merge tags
        with open(path, "r", encoding="utf-8") as f:
            existing = f.read()
        existing_meta, _ = parse_frontmatter(existing)
        created = existing_meta.get("created")
        # Merge tags: existing tags first, then new tags (deduped, order-preserved)
        existing_tags = existing_meta.get("tags", [])
        if isinstance(existing_tags, list):
            merged = list(existing_tags)
            for t in tags:
                if t not in merged:
                    merged.append(t)
            tags = merged
        action = "updated"

    fm = generate_frontmatter(
        title=title,
        tags=tags,
        page_type=page_type,
        confidence=confidence,
        status=status,
        created=created,
    )

    # Ensure parent directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)

    file_content = f"{fm}\n\n{content}\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(file_content)

    # Extract wikilinks from the content for reporting
    wikilinks = extract_wikilinks(content)

    return {
        "action": action,
        "path": path,
        "title": title,
        "tags": tags,
        "wikilinks": wikilinks,
    }


def append_to_wiki_file(path: str, content: str, section: Optional[str] = None) -> str:
    """Append content to an existing wiki page.

    If section is provided, inserts content under a new ## section header.
    Updates the 'updated' field in frontmatter.
    Returns the new full file content.
    """
    with open(path, "r", encoding="utf-8") as f:
        file_content = f.read()

    meta, body = parse_frontmatter(file_content)

    # Build the append block
    if section:
        append_block = f"\n\n## {section}\n\n{content}\n"
    else:
        append_block = f"\n\n{content}\n"

    new_body = body.rstrip() + append_block

    # Regenerate frontmatter with bumped updated date
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    fm = generate_frontmatter(
        title=meta.get("title", os.path.basename(path).replace(".md", "")),
        tags=tags,
        page_type=meta.get("type"),
        confidence=meta.get("confidence", "medium"),
        status=meta.get("status", "active"),
        created=meta.get("created"),
        updated=now,
        extra_fields={
            k: v for k, v in meta.items()
            if k not in ("title", "tags", "type", "confidence", "status", "created", "updated")
            and v
        },
    )

    new_content = f"{fm}\n\n{new_body}\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return new_content


def format_page_for_context(page: WikiPage, max_chars: int = 3000) -> str:
    """Format a wiki page for injection into session context."""
    lines = []
    lines.append(f"### {page.title}")
    if page.tags:
        lines.append(f"Tags: {', '.join(page.tags)}")
    if page.page_type:
        lines.append(f"Type: {page.page_type}")
    if page.confidence != "medium":
        lines.append(f"Confidence: {page.confidence}")
    if page.last_verified:
        lines.append(f"Last verified: {page.last_verified}")
    lines.append("")

    # Show summary if present (before markdown body)
    if page.summary:
        lines.append(f"> {page.summary}")
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

    # Include wikilinks if present
    if page.wikilinks:
        lines.append(f"\nLinks: {', '.join(f'[[{w}]]' for w in page.wikilinks)}")

    return "\n".join(lines)
