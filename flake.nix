{
  description = "Tamarin-wrapper Python project";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        python = pkgs.python3;

        pythonEnv = python.withPackages (ps: with ps; [
          pip
          typer
          textual
          black
          isort
          autoflake
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            pythonEnv
            python3Packages.pip
            python3Packages.setuptools
            python3Packages.wheel
            pre-commit
          ];
        };

        packages.default = pkgs.stdenv.mkDerivation {
          pname = "tamarin-wrapper";
          version = "0.1.0";

          src = ./.;

          buildInputs = [ pythonEnv ];

          installPhase = ''
            mkdir -p $out/bin
            cp -r . $out/
          '';
        };
      });
}
