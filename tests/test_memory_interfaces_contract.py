"""Tier 1 — the memory-interfaces contract. Pure plugin code; no Hermes required.

Muninn's formats used to be defined in several places that drifted apart. They are now
defined once, as constants in parser.py, and documented in the living spec
openspec/specs/memory-interfaces/spec.md. This file is what keeps those two from
drifting again: every value list in the spec is compared with its constant, so changing
either side alone fails the build.

It also checks the session-log format by writing real files with the same helpers the
provider uses, and parses their frontmatter with PyYAML as an independent oracle.

The parser is loaded by path, exactly as tests/test_parser_contract.py explains.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PARSER_PATH = ROOT / "src" / "muninn" / "parser.py"
PROVIDER_PATH = ROOT / "src" / "muninn" / "__init__.py"
SPEC_PATH = ROOT / "openspec" / "specs" / "memory-interfaces" / "spec.md"


def _load_parser():
    spec = importlib.util.spec_from_file_location(
        "muninn_parser_interfaces_under_test", PARSER_PATH
    )
    assert spec is not None and spec.loader is not None, f"cannot load {PARSER_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


p = _load_parser()

NOW = datetime(2026, 10, 18, 21, 10, tzinfo=timezone.utc)


# --- spec <-> code parity ------------------------------------------------------

def _spec_values(label: str) -> list[str]:
    """Values on the spec line ``<label>: `a`, `b`, ...`` — exactly one such line."""
    text = SPEC_PATH.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.startswith(f"{label}: ")]
    assert len(lines) == 1, (
        f"expected exactly one '{label}:' line in {SPEC_PATH.relative_to(ROOT)}, "
        f"found {len(lines)} — the parity check would otherwise test nothing"
    )
    return re.findall(r"`([^`]+)`", lines[0])


@pytest.mark.parametrize(
    "label, constant",
    [
        ("Page types", "PAGE_TYPES"),
        ("Confidence levels", "CONFIDENCE_LEVELS"),
        ("Statuses", "STATUSES"),
        ("Search-excluded statuses", "SEARCH_EXCLUDED_STATUSES"),
        ("Session log fields", "SESSION_LOG_FIELDS"),
    ],
)
def test_spec_lists_match_the_code(label, constant):
    assert _spec_values(label) == list(getattr(p, constant)), (
        f"spec '{label}' and parser.{constant} disagree; change both in the same commit"
    )


def test_defaults_are_members_of_their_sets():
    assert p.DEFAULT_CONFIDENCE in p.CONFIDENCE_LEVELS
    assert p.DEFAULT_STATUS in p.STATUSES
    assert set(p.SEARCH_EXCLUDED_STATUSES) <= set(p.STATUSES)
    assert p.DEFAULT_STATUS not in p.SEARCH_EXCLUDED_STATUSES


def test_provider_does_not_redefine_the_sets():
    """__init__.py must import the sets, never restate them."""
    source = PROVIDER_PATH.read_text(encoding="utf-8")
    for literal in ('"dream-candidate"', '"self-model"', '"superseded", "rejected"',
                    '"high", "medium", "low"'):
        assert literal not in source, f"__init__.py restates a contract value: {literal}"


# --- page types, confidence, status --------------------------------------------

def test_retired_type_is_not_writable():
    assert "dream-candidate" not in p.PAGE_TYPES


def test_vault_types_are_writable():
    assert {"self-model", "strategy"} <= set(p.PAGE_TYPES)


def _write_page(tmp_path, frontmatter: str) -> Path:
    path = tmp_path / "page.md"
    path.write_text(f"---\n{frontmatter}\n---\n\nBody text.\n", encoding="utf-8")
    return path


def test_retired_type_still_parses(tmp_path):
    page = p.parse_wiki_file(str(_write_page(tmp_path, "title: Old\ntype: dream-candidate")))
    assert page.page_type == "dream-candidate"


def test_unknown_confidence_and_status_are_coerced(tmp_path):
    page = p.parse_wiki_file(
        str(_write_page(tmp_path, "title: X\nconfidence: certain\nstatus: draft"))
    )
    assert page.confidence == p.DEFAULT_CONFIDENCE
    assert page.status == p.DEFAULT_STATUS


# --- session-log format ---------------------------------------------------------

def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    return yaml.safe_load(text.split("---", 2)[1])


def test_session_slug_with_and_without_session_id():
    assert re.fullmatch(r"session-2026-10-18-[0-9a-f]{8}", p.session_slug(NOW, "abc"))
    assert p.session_slug(NOW, "abc") == p.session_slug(NOW, "abc")
    assert p.session_slug(NOW) == "session-2026-10-18-2110"


def test_session_crossing_utc_midnight_moves_to_a_new_file():
    later_same_day = NOW.replace(hour=23, minute=59)
    next_day = datetime(2026, 10, 19, 0, 1, tzinfo=timezone.utc)
    assert p.session_slug(later_same_day, "abc") == p.session_slug(NOW, "abc")
    assert p.session_slug(next_day, "abc") != p.session_slug(NOW, "abc")


def test_new_session_log_has_the_contract_fields(tmp_path):
    path = tmp_path / "sessions" / f"{p.session_slug(NOW, 'abc')}.md"
    p.create_session_log(str(path), NOW, "sera", p.format_session_turn(NOW, "hi", "hello"))

    meta = _frontmatter(path)
    # `summary` is only added when the session ends.
    assert set(meta) == set(p.SESSION_LOG_FIELDS) - {"summary"}
    assert meta["type"] == p.SESSION_LOG_TYPE
    assert meta["agent"] == "sera"
    assert meta["tags"] == [*p.SESSION_LOG_TAGS, "agent:sera"]
    assert p.count_session_entries(path.read_text(encoding="utf-8")) == 2


def test_session_entries_are_one_per_speaker_with_full_content():
    long_message = "x" * 5000
    entries = p.format_session_turn(NOW, long_message, "reply")
    headers = p.SESSION_ENTRY_RE.findall(entries)
    assert len(headers) == 2
    assert "### 2026-10-18 21:10 UTC | User" in entries
    assert "### 2026-10-18 21:10 UTC | Assistant" in entries
    assert long_message in entries


def test_heading_inside_a_message_is_not_an_entry():
    entries = p.format_session_turn(NOW, "### 2026 plans\n### Notes", "ok")
    assert p.count_session_entries(entries) == 2


# --- session logs are append-only and uncapped -------------------------------------

def _new_log(tmp_path) -> Path:
    path = tmp_path / "sessions" / f"{p.session_slug(NOW, 'long')}.md"
    p.create_session_log(str(path), NOW, "sera", p.format_session_turn(NOW, "turn 0", "reply 0"))
    return path


def test_long_session_keeps_every_entry(tmp_path):
    path = _new_log(tmp_path)
    for i in range(1, 250):
        p.append_session_turn(str(path), p.format_session_turn(NOW, f"turn {i}", f"reply {i}"))

    text = path.read_text(encoding="utf-8")
    assert p.count_session_entries(text) == 500
    assert "turn 0\n" in text and "turn 249\n" in text
    assert set(_frontmatter(path)) == set(p.SESSION_LOG_FIELDS) - {"summary"}


def test_append_leaves_logged_bytes_unchanged(tmp_path):
    path = _new_log(tmp_path)
    before = path.read_bytes()
    p.append_session_turn(str(path), p.format_session_turn(NOW, "next", "reply"))
    after = path.read_bytes()
    assert after.startswith(before)
    assert p.count_session_entries(after.decode("utf-8")) == 4


def test_append_separates_entries_whatever_the_file_ends_with(tmp_path):
    path = _new_log(tmp_path)
    path.write_text(path.read_text(encoding="utf-8").rstrip("\n"), encoding="utf-8")
    p.append_session_turn(str(path), p.format_session_turn(NOW, "next", "reply"))
    text = path.read_text(encoding="utf-8")
    assert "reply 0\n\n### " in text
    assert p.count_session_entries(text) == 4
