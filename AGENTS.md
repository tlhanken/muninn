# AGENTS.md — notes for AI agents working in this repo

## What this is

Muninn, a Hermes memory provider: the raven of memory, sibling of Huginn who thinks
and fetches. Backed by `.qmd`/`.md` wiki files indexed with QMD. Distributed as a
Python package that Hermes discovers through an entry point, and built by the flake at
the repo root.

## Commands

    just test              # Tier 1, the parser contract (no Hermes needed)
    just test-hermes       # Tier 2, needs `nix develop` for $HERMES_PYTHON
    just build             # nix build .#default
    just validate-specs    # openspec validate --all --no-interactive
    just check             # nix flake check

## Rules that are easy to get wrong here

- **Never hardcode the interpreter.** The package is loaded into Hermes' own
  environment, so it must be built by the same interpreter Hermes runs. Take it from
  `hermes.passthru.python`; hermes-agent derives it from `pm/lock.json`, and it has
  already moved once (3.12 to 3.14). A hardcoded `python312` breaks silently.
- **Never hardcode `lib/python3.12/site-packages`** in test or probe scripts. Glob the
  version directory instead. A stale minor version points `PYTHONPATH` at a path that
  does not exist, discovery then returns nothing, and that false negative looks like a
  broken provider.
- **Do not declare `pyyaml` as a runtime dependency of the derivation.** Hermes fails
  the build when an `extraPythonPackages` entry or its propagated deps is already in
  the sealed venv, and pyyaml is in that venv. It stays a check-only input; the wheel
  metadata may still declare it, which is right for a standalone install.
- **The entry-point name is the provider identity.** It must match the provider's
  `name` property, `plugin.yaml`, and `memory.provider` in config. Changing it is a
  breaking config change and belongs in its own commit.
- **Data contracts keep their old names.** `~/.hermes/qmd-wiki.json`, `QMD_WIKI_DIR`,
  and the `"qmd_wiki_parser"` `sys.modules` key are deliberately unchanged through the
  qmd-wiki -> muninn rename. They hold state; do not "tidy" them.
- **Specs come first.** OpenSpec is the specification and change-management standard
  for this repo: living specs in `openspec/specs/`, proposals in `openspec/changes/`.
  Post a short plan and wait for an explicit go before creating proposal files, and
  validate with `openspec validate` before calling a change done.
- **`parser.py` is loaded by path** from `__init__.py` (as `qmd_wiki_parser`), which is
  why the two files must stay siblings. The load order around `sys.modules` is
  deliberate: it is what makes dataclass annotations resolve on 3.13+.
