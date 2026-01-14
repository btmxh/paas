{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    systems.url = "github:nix-systems/default";
    jailed-agents.url = "github:btmxh/jailed-agents";
  };

  outputs =
    {
      self,
      nixpkgs,
      systems,
      jailed-agents,
      ...
    }:
    let
      forEachSystem = nixpkgs.lib.genAttrs (import systems);
    in
    {
      devShells = forEachSystem (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.mkShell {
            buildInputs = enabledPackages;
            shellHook = shellHook + ''
              export PATH="$PWD/bin:$PATH"
            '';
            packages =
              with pkgs;
              [
                ruff
                nixd
                nixfmt-rfc-style
                pre-commit
              ]
              ++ (builtins.attrValues (
                jailed-agents.lib.${system}.makeJailedAgents {
                  extraPkgs = [
                    ruff
                    nixfmt-rfc-style
                    pre-commit
                  ];
                }
              ));
          };
        }
      );
    };
}
