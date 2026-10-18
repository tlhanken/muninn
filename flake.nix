{
  description = "Muninn — Hermes memory provider backed by .qmd/.md wiki files";

  inputs = {
    # Pinned to the exact revision nixos-config locks, so Muninn's Python closure
    # substitutes from cache instead of rebuilding. Bump this together with
    # nixos-config's nixpkgs, never independently.
    nixpkgs.url = "github:NixOS/nixpkgs/fe13242281a67641c0102cdb1087f0ebe586c7df";

    flake-utils.url = "github:numtide/flake-utils";

    # The Hermes revision nixos-config deploys. The dev shell needs it because the
    # provider is imported into Hermes' environment: Tier 2 must run under the 3.12
    # interpreter Hermes actually uses, never uv's. `passthru.devDeps` brings that
    # interpreter plus the dev dependency group (pytest), and `passthru.devShellHook`
    # exports HERMES_PYTHON pointing at it.
    hermes-agent.url = "github:NousResearch/hermes-agent/548091836760a67e331b8f5643be8e5c08fae1e6";
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
        python = pkgs.python312;
        hermes = hermes-agent.packages.${system}.default;

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
            python
            pkgs.uv
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
