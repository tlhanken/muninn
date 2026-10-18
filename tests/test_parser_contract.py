"""Tier 1 — parser contract. Pure plugin code; no Hermes required.

Each test states a property a caller depends on, not a snapshot of current output:
the emitted frontmatter must be valid YAML and must survive a round-trip, tags
containing commas must stay single tags, and a non-ASCII title must produce a
stable, distinct filename. PyYAML is the independent oracle for "valid YAML" —
the plugin hand-rolls the emitter, so only a real YAML parser can prove it correct.

The parser is loaded by path rather than imported as ``muninn.parser``: the package
``__init__`` loads it that way too, and importing the package would pull in the
``agent.memory_provider`` probe. Keeping this tier free of that is what lets it run
under a bare interpreter with nothing installed.

Run from the repo root:

    uv run --no-project --python-preference only-system \
        --with pytest --with pyyaml python -m pytest tests/test_parser_contract.py -q

(``--python-preference only-system`` is required on NixOS: uv's own downloaded
interpreters are glibc-linked and the kernel refuses to exec them.)
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import unicodedata
from pathlib import Path

import yaml

PARSER_PATH = Path(__file__).resolve().parents[1] / "src" / "muninn" / "parser.py"


def _load_parser():
    spec = importlib.util.spec_from_file_location(
        "muninn_parser_under_test", PARSER_PATH
    )
    assert spec is not None and spec.loader is not None, f"cannot load {PARSER_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


p = _load_parser()


def _frontmatter_body(fm: str) -> str:
    """Strip the --- delimiters so PyYAML sees one document, not two."""
    lines = fm.split("\n")
    assert lines[0] == "---" and lines[-1] == "---", "frontmatter must be delimited"
    return "\n".join(lines[1:-1])


# --- the bug: unescaped quotes produced invalid YAML -------------------------

def test_frontmatter_round_trips_quotes_and_backslashes():
    title = 'He said "hi" \\ and left'
    fm = p.generate_frontmatter(title=title)
    meta, _body = p.parse_frontmatter(f"{fm}\n\nbody\n")
    assert meta["title"] == title


def test_emitted_frontmatter_is_valid_yaml():
    """An independent parser must accept it — this is what a YAML reader sees."""
    title = 'He said "hi" \\ and left'
    tags = ["a,b", "plain", 'quote"d']
    fm = p.generate_frontmatter(title=title, tags=tags)

    doc = yaml.safe_load(_frontmatter_body(fm))

    assert doc["title"] == title
    assert doc["tags"] == tags


# --- the bug: a comma inside a quoted tag split one tag into two -------------

def test_tag_containing_a_comma_stays_one_tag():
    tags = ["a,b", "c"]
    fm = p.generate_frontmatter(title="T", tags=tags)
    meta, _body = p.parse_frontmatter(f"{fm}\n\nbody\n")
    assert meta["tags"] == tags


# --- the bug: non-ASCII titles collapsed to a shared placeholder -------------

def test_slugify_preserves_unicode_letters():
    assert p.slugify("Café résumé") == "café-résumé"


def test_distinct_cjk_titles_do_not_collide():
    first = p.slugify("日本語のタイトル")
    second = p.slugify("日本語の別のタイトル")
    assert first != second
    assert not first.startswith("untitled")


def test_slugify_is_unicode_normalisation_insensitive():
    assert p.slugify(unicodedata.normalize("NFD", "Café")) == p.slugify("Café")


def test_unsluggable_title_falls_back_deterministically():
    slug = p.slugify("🎉🎉")
    assert slug.startswith("untitled-")
    assert len(slug) == len("untitled-") + 8
    assert slug == p.slugify("🎉🎉")
    assert slug != p.slugify("🎊🎊")


# --- stable contracts the round-trip depends on -----------------------------

def test_wikilink_alias_resolves_to_target():
    assert p.extract_wikilinks("see [[target|display text]]") == ["target"]


def test_content_without_frontmatter_is_returned_unchanged():
    meta, body = p.parse_frontmatter("just a body\n")
    assert meta == {}
    assert body == "just a body\n"


def test_quarto_code_cell_extracted_and_plain_fence_kept():
    markdown, cells = p.extract_code_cells("```{python}\nx = 1\n```\n\nplain:\n\n```\nraw\n```\n")
    assert [c.language for c in cells] == ["python"]
    assert "[code cell: python]" in markdown
    assert "raw" in markdown


def test_hashlib_fallback_is_stable_for_the_same_title():
    """Guards the fallback's determinism independently of slugify's internals."""
    title = "🎉🎉"
    expected = "untitled-" + hashlib.sha1(title.encode("utf-8")).hexdigest()[:8]
    assert p.slugify(title) == expected
