{
  description = "Tamarin Prover 1.4.0 and batch-tamarin 1.1.0";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    nixpkgs-old.url = "github:NixOS/nixpkgs/04002e2b7186c166af87c20da7a7ceb8c0edb021";
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
            hash = "sha256-E3vbeDEiXcGyDVFq28aW7MuaTCLanhaGfnD7nqf9zcA=";
          };

          nativeBuildInputs = with python.pkgs; [ setuptools wheel ];
          propagatedBuildInputs = with python.pkgs; [ tree-sitter ];
        };

        batch-tamarin = python.pkgs.buildPythonPackage rec {
          pname = "batch-tamarin";
          version = "1.1.0";
          format = "pyproject";

          src = pkgs.fetchFromGitHub {
            owner = "tamarin-prover";
            repo = "batch-tamarin";
            rev = "v${version}";
            hash = "sha256-wmfCoY2z7b/wnlqeb1Vc9eHzeWYS+v+n9mWxXzrkJzM=";
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
