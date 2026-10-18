# Muninn — recipes. `just` to list.

# Tier 1: the parser contract. Pure plugin code, no Hermes required, run by a
# uv-managed interpreter. --python-preference only-system is required on NixOS:
# uv's downloaded interpreters are glibc-linked and the kernel refuses to exec them.
test-parser:
    uv run --no-project --python-preference only-system --with pytest --with pyyaml python -m pytest tests/test_parser_contract.py -q

# Tier 2: Hermes-coupled tests (discovery, lifecycle, turn path). Needs the dev
# shell, because it must run under the interpreter Hermes itself uses — a bare
# `python -m pytest` silently tests a different interpreter.
test-hermes:
    "$HERMES_PYTHON" -m pytest tests/ -q

# Everything that runs without Hermes present.
test: test-parser

# The exact package nixos-config consumes.
build:
    nix build .#default

# The OpenSpec corpus: living specs and open changes.
validate-specs:
    openspec validate --all --no-interactive

# What CI runs.
check:
    nix flake check
