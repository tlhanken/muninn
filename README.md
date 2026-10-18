# Muninn

An AI agent long-term memory framework.

The raven of memory. A Hermes memory provider backed by `.qmd`/`.md` wiki files
indexed with QMD: OKF-aware search, wikilink extraction, write and append tools,
session logging on turn boundaries, and executable code cells for verifying that
documented knowledge still runs.

Sibling of Huginn, who thinks and fetches. Muninn remembers.

## Install (NixOS, through nixos-config)

Muninn is a Python package that Hermes discovers through an entry point
(`hermes_agent.memory_providers`), so it needs no symlink and no per-profile plugins
directory — it is visible to **every** profile, including ones with no `plugins/`
directory of their own.

Declare it as a flake input:

```nix
muninn = {
  url = "github:tlhanken/muninn";
  inputs.nixpkgs.follows = "nixpkgs-unstable";
  # Share nixos-config's hermes-agent, so there is exactly one Hermes revision in
  # the graph. Without this, this repo's own pin could name a different revision
  # than the one actually running, and the build interpreter would stop matching
  # the venv the package is loaded into.
  inputs.hermes-agent.follows = "hermes-agent";
};
```

Then give it to Hermes — as a NixOS service option, or as a Home Manager override:

```nix
services.hermes-agent.extraPythonPackages = [ inputs.muninn.packages.${system}.default ];
# or
hermesAgent = inputs.hermes-agent.packages.${system}.default.override {
  extraPythonPackages = [ inputs.muninn.packages.${system}.default ];
};
```

…and select it declaratively:

```nix
settings.memory.provider = "muninn";
```

Two details of that wiring are load-bearing:

- **The interpreter comes from Hermes.** The package is loaded into Hermes' own
  environment, so the flake builds it with `hermes.passthru.python` — the interpreter
  hermes-agent selects from `pm/lock.json`, which has already moved once (3.12 to
  3.14). Nothing here hardcodes a version.
- **`pyyaml` is not a runtime dependency of the derivation.** Hermes fails the build
  when an `extraPythonPackages` entry or its propagated deps is already in the sealed
  venv, and pyyaml is in that venv. The provider takes yaml from the venv at runtime;
  the wheel metadata still declares it, which is right for a standalone install.

## Layout

```
src/muninn/__init__.py   the provider: tools, config, indexing, session logging
src/muninn/parser.py     frontmatter, wikilinks, slugs, code cells
tests/                   parser contract (Tier 1) and Hermes-coupled tests (Tier 2)
openspec/                living specs and change proposals
flake.nix                the package nixos-config consumes, plus the dev shell
plugin.yaml              plugin metadata
```

`parser.py` is loaded by path from `__init__.py`, which is why the two files must stay
siblings.

## Tests

Tier 1 — the parser contract. Pure plugin code, no Hermes required:

```
just test
```

Tier 2 — discovery and the Hermes memory-provider contract. It must run under the
interpreter Hermes actually uses, never uv's, so it needs the dev shell, which borrows
that interpreter from hermes-agent and exports `HERMES_PYTHON`:

```
nix develop
just test-hermes
```

## Specs

OpenSpec is the specification and change-management standard here: living specs in
`openspec/specs/`, proposals in `openspec/changes/`. Validate with `just validate-specs`.

## A note on names

The provider was renamed from `qmd-wiki` to `muninn`. Three things deliberately did
**not** move, because they are data contracts that already hold state:

- `~/.hermes/qmd-wiki.json` — the config file.
- `QMD_WIKI_DIR` — the wiki-directory environment variable.
- `"qmd_wiki_parser"` — the synthetic `sys.modules` key used when loading `parser.py`
  by path. Internal, and the loading mechanism around it is delicate.

So the identity you type (`memory.provider`) is `muninn`, while the storage paths keep
their original names. The specs still describe the capability under its old name
(`qmd-wiki-memory-provider`); renaming them is cosmetic and not done here.

## License

MIT © 2026 Trevor Hanken. See [LICENSE](LICENSE).
