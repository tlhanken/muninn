"""Tier 2 — the Hermes-facing contract: discovery, identity, and the tool surface.

Tier 1 (test_parser_contract.py) covers pure plugin code and needs no Hermes. This file
is the opposite: it only means anything inside Hermes' own interpreter, so run it from
the development shell, which sets HERMES_PYTHON and puts this package — with its entry
point — on PYTHONPATH:

    nix develop
    just test-hermes

Two ways this file could lie, both guarded here:

* Hermes not importable. A bare skip would report success while testing nothing, so when
  HERMES_PYTHON is set the import failure is raised as an error instead of skipped. This
  is the check that was missing the first time the plugin's tests "passed".
* The provider falling back to its stub ``MemoryProvider`` class. That fallback exists so
  the module imports anywhere, and it makes a broken import path look healthy. Asserting
  identity against the real ABC is the only thing that catches it.
"""

from __future__ import annotations

import importlib.metadata
import os
from pathlib import Path

import pytest

PROVIDER = "muninn"
ENTRY_POINT_GROUP = "hermes_agent.memory_providers"

_IMPORT_ERROR: Exception | None = None
try:
    from agent.memory_provider import MemoryProvider as RealMemoryProvider
    from plugins import memory as hermes_memory
except Exception as exc:  # pragma: no cover - exercised only outside the dev shell
    _IMPORT_ERROR = exc
    RealMemoryProvider = None  # type: ignore[assignment]

if _IMPORT_ERROR is not None:
    if os.environ.get("HERMES_PYTHON"):
        raise RuntimeError(
            "HERMES_PYTHON is set, so this is the development shell, but Hermes is not "
            f"importable ({_IMPORT_ERROR!r}). Tier 2 would test nothing, so this is an "
            "error rather than a skip. Run it as: nix develop && just test-hermes"
        )
    pytest.skip(
        f"Hermes is not importable ({_IMPORT_ERROR!r}); Tier 2 needs the development shell",
        allow_module_level=True,
    )

import muninn as muninn_module


def _entry_point():
    eps = importlib.metadata.entry_points()
    found = [
        ep
        for ep in (eps.select(group=ENTRY_POINT_GROUP) if hasattr(eps, "select") else eps.get(ENTRY_POINT_GROUP, []))
        if ep.name == PROVIDER
    ]
    assert found, (
        f"{PROVIDER} is not installed as a {ENTRY_POINT_GROUP} entry point. The package "
        "must be installed (the flake's dev shell puts it on PYTHONPATH) — an entry point "
        "does not exist for a source tree alone."
    )
    return found[0]


def _loaded_provider():
    """Load the provider the way Hermes does, from its installed entry point."""
    from plugins.memory import _load_provider_from_entry_point, load_memory_provider

    provider = load_memory_provider(PROVIDER, register_skills=False)
    if provider is None:
        # Hermes refuses in-process imports of pip-installed providers in some contexts
        # (hermes_cli.plugin_isolation). That is a policy about how Hermes runs, not a
        # defect in the provider, so fall back to the function the loader itself uses
        # once it is permitted to import.
        provider = _load_provider_from_entry_point(_entry_point(), register_skills=False)
    assert provider is not None, "the provider failed to load from its entry point"
    return provider


def test_entry_point_yields_a_package_directory():
    """A package entry point, not a module: config_schema and the CLI are read from disk."""
    directory = hermes_memory._entry_point_package_dir(_entry_point())
    assert directory is not None, (
        "the entry point does not resolve to a package directory. Point it at a package "
        "(__init__.py), never a bare module or a callable, or the provider silently loses "
        "its dashboard panel and its `hermes <provider>` commands."
    )
    assert (directory / "plugin.yaml").is_file(), f"{directory} has no plugin.yaml"


def test_hermes_discovery_lists_the_provider():
    assert PROVIDER in hermes_memory.list_memory_provider_names()


def test_provider_class_is_the_real_abc():
    """Catches the stub fallback: the module loads either way, and only identity differs."""
    assert muninn_module.MemoryProvider is RealMemoryProvider, (
        "muninn fell back to its stub MemoryProvider. The real ABC import is failing, so "
        "the provider would load, do nothing, and raise nothing."
    )


def test_loaded_provider_identity_and_tools():
    provider = _loaded_provider()
    assert isinstance(provider, RealMemoryProvider)
    assert provider.name == PROVIDER, "name must equal the entry-point name and memory.provider"

    schemas = provider.get_tool_schemas()
    names = {s["name"] for s in schemas}
    assert names == {"wiki_search", "wiki_read", "wiki_refresh", "wiki_write", "wiki_append"}
    for schema in schemas:
        assert schema.get("description"), f"{schema['name']} has no description"
        assert isinstance(schema.get("parameters"), dict), f"{schema['name']} has no parameter schema"


def test_register_hands_the_provider_to_the_context():
    class StubContext:
        def __init__(self):
            self.registered = []

        def register_memory_provider(self, provider):
            self.registered.append(provider)

    ctx = StubContext()
    muninn_module.register(ctx)
    assert len(ctx.registered) == 1, "register() must call ctx.register_memory_provider exactly once"
    assert ctx.registered[0].name == PROVIDER


def test_config_schema_covers_the_documented_keys():
    keys = {entry["key"] for entry in _loaded_provider().get_config_schema()}
    documented = {"wiki_dirs", "wiki_dir", "max_context_chars", "max_pages", "execute_cells"}
    assert documented == keys, f"README documents {sorted(documented)}, provider exposes {sorted(keys)}"


def test_wiki_env_var_makes_the_provider_available(tmp_path, monkeypatch):
    """The documented QMD_WIKI_DIR path, exercised rather than assumed.

    The provider resolves its wiki directories when it is constructed, so the environment
    has to be in place *before* loading. Setting it afterwards leaves the provider reading
    whatever it found first — on a development machine, the real vault — which makes an
    empty directory look available. HERMES_HOME is redirected too, so a configured
    ~/.hermes/qmd-wiki.json (which takes precedence over the env var) cannot leak in, and
    the real vault is never indexed by a test.
    """
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setenv("QMD_WIKI_DIR", str(tmp_path / "wiki"))
    (tmp_path / "wiki").mkdir()

    provider = _loaded_provider()
    # __init__ leaves the directories empty and initialize() is what loads them — but
    # initialize() also scans the directories and builds search collections, side effects a
    # config test has no business triggering. Call the loader's own config step instead.
    provider._load_config()
    assert provider.is_available() is False, "an empty directory is not an available wiki"

    (tmp_path / "wiki" / "note.md").write_text("# Note\n")
    assert provider.is_available() is True, "a directory holding a .md page is an available wiki"
