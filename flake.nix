{
  description = "Muninn — Hermes memory provider backed by .qmd/.md wiki files";

  inputs = {
    # The Hermes revision this repo is developed and tested against. The consumer's
    # follows edge decides what it is actually built with.
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
    let
      # Integration surfaces, defined once and system-independent. They point at this
      # flake's own package, so a consumer gets the interpreter-correct build instead
      # of one rebuilt against their own pkgs.
      module = import ./nix/module.nix { inherit self; };
    in
    {
      # Consumption is one import line:
      #   imports = [ inputs.muninn.nixosModules.default ];        # or
      #   imports = [ inputs.muninn.homeManagerModules.default ];
      # The module adds the package to services.hermes-agent.extraPythonPackages and
      # selects memory.provider = "muninn".
      nixosModules.default = module;
      homeManagerModules.default = module;

      # For consumption that wants the package directly: pkgs.muninn.
      overlays.default = final: prev: {
        muninn = self.packages.${final.stdenv.hostPlatform.system}.default;
      };
    }
    // flake-utils.lib.eachDefaultSystem (
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
          src = ./.; # git-tracked files only; a new file is invisible until staged
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

        # Consumers: either the module (input + one import line) or the package
        # directly. extraPythonPackages appends the package's site-packages to
        # Hermes' PYTHONPATH, which is what puts muninn's dist-info where
        # importlib.metadata can find the hermes_agent.memory_providers entry point.
        # The package path remains necessary for setups that consume the Hermes
        # package directly rather than through services.hermes-agent.
        devShells.default = pkgs.mkShell {
          packages = [
            pkgs.just
            pkgs.uv
            python
            # The package itself, not just its source: this derivation carries
            # muninn-0.1.0.dist-info, and the dist-info is what makes the
            # hermes_agent.memory_providers entry point discoverable. Tier 2 tests
            # discovery, so it needs the entry point.
            muninn
          ]
          ++ hermes.passthru.devDeps;

          shellHook = ''
            ${hermes.passthru.devShellHook}
            # Derive the version directory. A hardcoded lib/python3.12/site-packages
            # points at nothing, and entry-point discovery then silently returns empty.
            export PYTHONPATH="${muninn}/${python.sitePackages}''${PYTHONPATH:+:$PYTHONPATH}"
            echo "Muninn dev shell"
            echo "  Tier 1: just test"
            echo "  Tier 2: just test-hermes   (HERMES_PYTHON=$HERMES_PYTHON)"
          '';
        };
      }
      // nixpkgs.lib.optionalAttrs (nixpkgs.lib.hasSuffix "linux" system) {
        # A check that would have caught a real bug. Assigning the provider inside
        # `settings` with lib.mkDefault leaves Nix's override marker unresolved —
        # `settings` is a loose deepConfigType rendered with a bare builtins.toJSON — so
        # config.yaml would carry {"_type":"override",...} where Hermes expects the
        # string, and the provider would be silently wrong. Assert the value *and its
        # type* here, where the module is evaluated for real. Linux only: the Hermes
        # module is a NixOS module, so a darwin system cannot host it. The guard tests
        # the `system` string rather than pkgs.stdenv.hostPlatform.isLinux, because
        # forcing `pkgs` on a system nixpkgs has dropped (x86_64-darwin in 26.11) is
        # itself a hard error.
        checks.moduleWiring =
          let
            wired =
              (nixpkgs.lib.nixosSystem {
                inherit system;
                modules = [
                  hermes-agent.nixosModules.default
                  module
                  {
                    services.hermes-agent.enable = true;
                    services.hermes-agent.stateDir = "/tmp/muninn-wiring-check";
                  }
                ];
              }).config.services.hermes-agent;
            provider = wired.settings.memory.provider;
            count = builtins.length wired.extraPythonPackages;
          in
          if !(builtins.isString provider) then
            throw ''
              muninn: settings.memory.provider is a ${builtins.typeOf provider}, not a
              string. Do not use lib.mkDefault (or mkForce) inside services.hermes-agent
              .settings — the override marker is never resolved and lands in the
              generated config.yaml verbatim.
            ''
          else if provider != "muninn" then
            throw ''muninn: settings.memory.provider is "${toString provider}", expected "muninn"''
          else if count != 1 then
            throw ''muninn: expected exactly 1 extraPythonPackages entry, got ${toString count}''
          else
            pkgs.runCommand "muninn-module-wiring-ok" { } ''
              echo "settings.memory.provider is the string \"muninn\"; extraPythonPackages has 1 entry" > $out
            '';
      }
    );
}
