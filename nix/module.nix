# The module this flake exports as both nixosModules.default and
# homeManagerModules.default. Importing it wires Muninn into Hermes as the memory
# provider, so the consumer does not need to know about extraPythonPackages or the
# entry-point group:
#
#   imports = [ inputs.muninn.nixosModules.default ];
#
# Both exports are deliberately the same module: the option paths under
# services.hermes-agent are identical in the NixOS and Home Manager modules.
{ self }:
{
  config,
  lib,
  pkgs,
  ...
}:
let
  # The package comes from this flake's own outputs, selected for the consumer's
  # system, so it is built by `hermes.passthru.python` — the interpreter Hermes
  # actually runs — rather than rebuilt against the consumer's `pkgs`, whose default
  # python could be a different minor version.
  muninn = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
in
{
  config = lib.mkIf (config.services ? hermes-agent) {
    # extraPythonPackages appends the package's site-packages to Hermes' PYTHONPATH,
    # which is what puts muninn's dist-info where importlib.metadata finds the
    # hermes_agent.memory_providers entry point. An environment-level install is what
    # makes the provider visible to every profile, including ones with no plugins/
    # directory of their own — a symlink cannot do that.
    services.hermes-agent.extraPythonPackages = [ muninn ];

    # mkDefault, so a host can still select a different provider.
    services.hermes-agent.settings.memory.provider = lib.mkDefault "muninn";
  };
}
