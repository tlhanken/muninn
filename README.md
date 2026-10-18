# Muninn

An AI agent long-term memory framework.

A memory provider for Hermes Agent, backed by `.qmd`/`.md` wiki files and indexed with
[QMD](https://github.com/tobi/qmd). QMD does the searching — BM25 full text, vector
similarity, LLM reranking — and Muninn bridges Hermes to it:

- Per-agent directory isolation, so each agent indexes only its own wiki
- `wiki_write` and `wiki_append`, with frontmatter managed for you
- Session logging, written on turn boundaries
- Filtering by page type, confidence, and status
- A lightweight page catalog in the system prompt, plus result shaping for context injection
- Optional execution of documented code cells, to check that the knowledge still runs

## Requirements

- Hermes Agent
- the `qmd` CLI on `PATH`

## Install

Hermes discovers memory providers through the `hermes_agent.memory_providers`
entry-point group, so installing the package is all it takes. Every profile sees it —
there is no per-profile plugin directory to populate.

### NixOS / Home Manager

Add the flake input:

```nix
muninn = {
  url = "github:tlhanken/muninn";
  inputs.nixpkgs.follows = "nixpkgs-unstable";
  inputs.hermes-agent.follows = "hermes-agent";
};
```

The `follows` edges keep a single Hermes revision in the graph, so the interpreter Muninn
is built against is the one Hermes runs. Then import the module:

```nix
imports = [ inputs.muninn.nixosModules.default ];   # or homeManagerModules.default
```

It adds the package to `services.hermes-agent.extraPythonPackages` and defaults
`settings.memory.provider` to `"muninn"`, which you can override. Importing it where the
Hermes modules are absent does nothing rather than failing.

### Consuming the package directly

If Hermes comes in as a package rather than through `services.hermes-agent`:

```nix
hermesAgent = hermes-agent.packages.${system}.default.override {
  extraPythonPackages = [ inputs.muninn.packages.${system}.default ];
};
```

and select the provider:

```yaml
memory:
  provider: muninn
```

`overlays.default` is available too, for `pkgs.muninn`.

### Packaging notes

- **The interpreter is Hermes'.** The provider is loaded into Hermes' own environment, so
  the flake builds it with `hermes.passthru.python` — the interpreter hermes-agent selects
  from `pm/lock.json`. No version is hardcoded.
- **`pyyaml` is a check-time input, not a runtime dependency** of the derivation. Hermes
  fails the build when an `extraPythonPackages` entry, or a dependency it propagates, is
  already present in its sealed venv, and pyyaml is in that venv; the provider uses the
  venv's copy at runtime. The wheel metadata still declares it, which is what a standalone
  install needs.

## Configuration

`~/.hermes/qmd-wiki.json`:

| Key | Default | Meaning |
| --- | --- | --- |
| `wiki_dirs` | auto-detected | directories to index — this is what isolates one agent's memory from another's |
| `wiki_dir` | — | single directory, wrapped into `wiki_dirs` |
| `max_context_chars` | `2000` | most wiki content injected into a turn |
| `max_pages` | `3` | pages returned by prefetch |
| `execute_cells` | `false` | run documented code cells during a refresh |

Environment variables: `QMD_WIKI_DIR` for a single directory, and `QMD_EXECUTE_CELLS=true`
to turn on code-cell execution.

## Tools

| Tool | Purpose |
| --- | --- |
| `wiki_search` | search the wiki |
| `wiki_read` | read a page |
| `wiki_refresh` | rebuild the index |
| `wiki_write` | write a page, managing its frontmatter |
| `wiki_append` | append to a page |

## Layout

```
src/muninn/__init__.py   the provider: tools, config, indexing, session logging
src/muninn/parser.py     frontmatter, wikilinks, slugs, code cells
tests/                   parser contract (Tier 1) and Hermes-coupled tests (Tier 2)
openspec/                living specs and change proposals
flake.nix                the package and the development shell
plugin.yaml              plugin metadata
```

`parser.py` is loaded by path from `__init__.py`, which is why the two files must stay
siblings.

## Tests

Tier 1 — the parser contract. Pure plugin code, no Hermes required:

```
just test
```

Tier 2 — discovery and the Hermes memory-provider contract. It has to run under the
interpreter Hermes actually uses, never uv's, so it needs the development shell, which
borrows that interpreter from hermes-agent and exports `HERMES_PYTHON`:

```
nix develop
just test-hermes
```

## Specs

OpenSpec is the specification and change-management standard here: living specs in
`openspec/specs/`, proposals in `openspec/changes/`. Validate with `just validate-specs`.

## License

MIT © 2026 Trevor Hanken. See [LICENSE](LICENSE).
