{
  description = "Tamarin Prover 1.4.1 and batch-tamarin 1.2.0";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    nixpkgs-old.url = "github:NixOS/nixpkgs/fc159594a768143812be50e73a95a610cdb97a47";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, nixpkgs-old, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        pkgs-old = nixpkgs-old.legacyPackages.${system};
        python = pkgs.python313;

        py-tree-sitter-spthy = python.pkgs.buildPythonPackage rec {
          pname = "py-tree-sitter-spthy";
          version = "1.2.2";
          format = "pyproject";

          src = pkgs.fetchFromGitHub {
            owner = "lmandrelli";
            repo = "py-tree-sitter-spthy";
            rev = "v${version}";
            hash = "sha256-0000000000000000000000000000000000000000000=";
          };

          nativeBuildInputs = with python.pkgs; [ setuptools wheel ];
          propagatedBuildInputs = with python.pkgs; [ tree-sitter ];
        };

        batch-tamarin = python.pkgs.buildPythonPackage rec {
          pname = "batch-tamarin";
          version = "1.2.0";
          format = "pyproject";

          src = pkgs.fetchFromGitHub {
            owner = "tamarin-prover";
            repo = "batch-tamarin";
            rev = "v${version}";
            hash = "sha256-0000000000000000000000000000000000000000000=";
          };

          nativeBuildInputs = with python.pkgs; [ setuptools wheel build ];

          propagatedBuildInputs = with python.pkgs; [
            typer
            pydantic
            psutil
            tree-sitter
            diskcache
            jinja2
            py-tree-sitter-spthy
            graphviz
            docker
          ];

          pythonRuntimeDepsCheck = false;
          doCheck = false;
        };
      in
      {
        packages = {
          default = pkgs.buildEnv {
            name = "tamarin-prover-env";
            paths = with pkgs; [
              zsh
              graphviz
              coreutils
              bash
              batch-tamarin
            ] ++ (with pkgs-old; [
              tamarin-prover
            ]);
          };

          batch-tamarin = batch-tamarin;
        };

        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            zsh
            graphviz
            coreutils
            bash
            batch-tamarin
          ] ++ (with pkgs-old; [
            tamarin-prover
          ]);
        };
      });
}
