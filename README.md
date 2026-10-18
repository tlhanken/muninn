# Muninn

The raven of memory. A Hermes memory provider backed by `.qmd`/`.md` wiki files
indexed with QMD: OKF-aware search, wikilink extraction, write and append tools,
session logging on turn boundaries, and executable code cells for verifying that
documented knowledge still runs.

Named as the sibling of Huginn, who thinks and fetches. Muninn remembers.

## Layout

    src/muninn/__init__.py   the provider: tools, config, indexing, session logging
    src/muninn/parser.py     frontmatter, wikilinks, slugs, code cells
    tests/                   parser contract (pure) and Hermes-coupled tests

`parser.py` is loaded by path from `__init__.py`, which is why the two must stay
siblings.

## Tests

Tier 1 — parser contract, no Hermes required:

    uv run --no-project --python-preference only-system \
        --with pytest --with pyyaml python -m pytest tests/test_parser_contract.py -q

Tier 2 — discovery and the Hermes memory-provider contract: see `tests/README.md`
once the flake lands. Tier 2 needs Hermes' own interpreter (3.11–3.13), not the
`uv`-managed one, and on NixOS needs `--python-preference only-system`.

## Status

Extracted from `~/workspace/tools` with history intact. The provider identifier is
still `qmd-wiki` on the running system; the rename to `muninn` lands together with
the `memory.provider` config change, and the old `~/.hermes/plugins/qmd-wiki`
symlink is retired only after Muninn is discovered from the environment.
