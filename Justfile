# Muninn — recipes. `just` to list.

# Tier 1: the parser contract. Pure plugin code, no Hermes required, run by a
# uv-managed interpreter. --python-preference only-system is required on NixOS:
# uv's downloaded interpreters are glibc-linked and the kernel refuses to exec them.
test-parser:
    uv run --no-project --python-preference only-system --with pytest --with pyyaml python -m pytest tests/test_parser_contract.py -q

# Tier 2: the Hermes-facing contract — discovery, provider identity, the tool surface.
# It has to run under the interpreter Hermes actually uses, never a bare `python`, or a
# different interpreter quietly tests nothing. The dev shell provides that as
# HERMES_PYTHON and puts the package (with its entry point) on PYTHONPATH.
test-hermes:
    @test -n "$HERMES_PYTHON" || { echo "HERMES_PYTHON is unset — run this inside 'nix develop'"; exit 1; }
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
