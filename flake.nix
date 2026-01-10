{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-25.05";
    flake-utils.url = "github:numtide/flake-utils";
    jailed-agents.url = "github:btmxh/jailed-agents";
  };

  outputs = { self, nixpkgs, flake-utils, jailed-agents, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let pkgs = nixpkgs.legacyPackages.${system};
      in {
        formatter = pkgs.nixfmt-tree;
        devShells.default = pkgs.mkShell {
          packages = with pkgs;
            [ python3 uv nixd nixfmt ]
            ++ (builtins.attrValues (jailed-agents.lib.${system}.makeJailedAgents { }));
        };
      });
}
