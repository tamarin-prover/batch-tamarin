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
          typer
          pip
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            pythonEnv
            python3Packages.pip
            python3Packages.setuptools
            python3Packages.wheel
          ];

          shellHook = ''
            echo "Python ${python.version} development environment"
            echo "Available packages: typer"
            echo "Run 'python --version' to check Python version"
          '';
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