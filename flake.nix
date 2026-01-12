{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-25.05";
    nixpkgs-unstable.url = "github:nixos/nixpkgs/nixos-unstable";
    systems.url = "github:nix-systems/default";
    jail-nix.url = "sourcehut:~alexdavid/jail.nix";
    jailed-agents.url = "github:btmxh/jailed-agents";
    git-hooks.url = "github:cachix/git-hooks.nix";
  };

  outputs =
    {
      self,
      nixpkgs,
      nixpkgs-unstable,
      systems,
      jail-nix,
      jailed-agents,
      git-hooks,
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
          pkgs-unstable = nixpkgs-unstable.legacyPackages.${system};
          inherit (self.checks.${system}.pre-commit-check) shellHook enabledPackages config;
          inherit (config) package configFile;
          jail = jail-nix.lib.init pkgs;
        in
        {
          default = pkgs.mkShell {
            inherit shellHook;
            buildInputs = enabledPackages;
            packages =
              with pkgs;
              [
                python3
                uv
                ruff
                pkgs-unstable.ty
                nixd
                nixfmt-rfc-style
              ]
              ++ (builtins.attrValues (
                jailed-agents.lib.${system}.makeJailedAgents {
                  extraPkgs = [
                    python3
                    uv
                    ruff
                    ty
                    nixfmt-rfc-style
                    ruff
                    ty
                    package
                  ]
                  ++ enabledPackages;

                  extraJailOptions = with jail.combinators; [
                    (readonly configFile)
                    (readonly (lib.getExe package))
                    (readonly ".venv")
                  ];
                }
              ));
          };
        }
      );

      # Run the hooks with `nix fmt`.
      formatter = forEachSystem (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          inherit (self.checks.${system}.pre-commit-check) config;
          inherit (config) package configFile;
          script = ''
            "${pkgs.lib.getExe package}" run --all-files --config ${configFile}
          '';
        in
        pkgs.writeShellScriptBin "pre-commit-run" script
      );

      # Run the hooks in a sandbox with `nix flake check`.
      # Read-only filesystem and no internet access.
      checks = forEachSystem (system: {
        pre-commit-check = git-hooks.lib.${system}.run {
          src = ./.;
          hooks = {
            nixfmt.enable = true;
            statix.enable = true;
            check-yaml.enable = true;
            end-of-file-fixer.enable = true;
            trim-trailing-whitespace.enable = true;
            ruff.enable = true;
            ruff-format.enable = true;
            uv-export.enable = true;
          };
        };
      });
    };
}
