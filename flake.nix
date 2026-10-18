{
  description = "Muninn — Hermes memory provider backed by .qmd/.md wiki files";

  inputs = {
    # The Hermes revision nixos-config locks. This is the one version-sensitive pin
    # in this flake: everything Python-shaped is derived from it below, and it must
    # move together with nixos-config's hermes-agent input.
    hermes-agent.url = "github:NousResearch/hermes-agent/548091836760a67e331b8f5643be8e5c08fae1e6";

    # Follow Hermes' own nixpkgs rather than pinning a second one, so the package
    # set here is the same one Hermes is built from.
    nixpkgs.follows = "hermes-agent/nixpkgs";

    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      hermes-agent,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        hermes = hermes-agent.packages.${system}.default;

        # The exact interpreter Hermes runs. hermes-agent derives it from
        # pm/lock.json (nix/pythonLock.nix) and exposes it as passthru.python, so it
        # is never hardcoded here and never has to be kept in step by hand: when the
        # pin moves Hermes from 3.12 to 3.14, this package follows automatically.
        # That matters because the package is loaded INTO Hermes' environment.
        python = hermes.passthru.python;

        muninn = python.pkgs.buildPythonPackage {
          pname = "muninn";
          version = "0.1.0"; # keep in step with pyproject.toml
          pyproject = true;
          src = ./.;
          build-system = [ python.pkgs.hatchling ];

          # pyyaml is deliberately NOT a runtime dependency of this derivation.
          # Hermes' extraPythonPackages machinery expands every entry to itself plus
          # its propagated deps, then FAILS the build if any resulting package name
          # is already in the sealed venv ("collides with a package in hermes sealed
          # venv"). pyyaml is in that venv, so declaring it here would break the
          # Hermes build. The provider gets yaml from the venv at runtime; the wheel
          # metadata still declares it (honest for a standalone install), and the
          # parser contract tests need it at check time.
          nativeCheckInputs = [
            python.pkgs.pytestCheckHook
            python.pkgs.pyyaml
          ];
          pythonImportsCheck = [ "muninn" ];
        };
      in
      {
        packages.default = muninn;
        packages.muninn = muninn;
        checks.default = muninn;

        # nixos-config consumes this for entry-point discovery:
        #   hermesAgent = inputs.hermes-agent.packages.${system}.default.override {
        #     extraPythonPackages = [ inputs.muninn.packages.${system}.default ];
        #   };
        # extraPythonPackages appends the package's site-packages to Hermes'
        # PYTHONPATH, which is what puts muninn's dist-info where
        # importlib.metadata can find the hermes_agent.memory_providers entry point.
        devShells.default = pkgs.mkShell {
          packages = [
            pkgs.just
            pkgs.uv
            python
          ]
          ++ hermes.passthru.devDeps;

          shellHook = ''
            ${hermes.passthru.devShellHook}
            echo "Muninn dev shell"
            echo "  Tier 1: uv run --no-project --python-preference only-system --with pytest --with pyyaml python -m pytest tests/test_parser_contract.py -q"
            echo "  Tier 2: \$HERMES_PYTHON -m pytest tests/ -q   (HERMES_PYTHON=$HERMES_PYTHON)"
          '';
        };
      }
    );
}
