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

    # Plain value, NOT lib.mkDefault: `settings` is a loose deepConfigType, so an
    # override marker applied to a nested key is never resolved and toJSON serialises
    # it verbatim — the rendered config.yaml would carry
    # {"_type": "override", "content": "muninn", "priority": 1000} where Hermes expects
    # the string "muninn". The merge into config.yaml is a deep merge, so a host that
    # wants a different provider can still set settings.memory.provider itself.
    services.hermes-agent.settings.memory.provider = "muninn";
  };
}
