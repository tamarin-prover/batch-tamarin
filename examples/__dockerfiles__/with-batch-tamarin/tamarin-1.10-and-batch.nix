{
  description = "Tamarin Prover 1.10.0 and batch-tamarin 1.0.0";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/a421ac6595024edcfbb1ef950a3712b89161c359";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python3;

        py-tree-sitter-spthy = python.pkgs.buildPythonPackage rec {
          pname = "py-tree-sitter-spthy";
          version = "1.2.1";
          format = "pyproject";

          src = pkgs.fetchFromGitHub {
            owner = "lmandrelli";
            repo = "py-tree-sitter-spthy";
            rev = "v${version}";
            hash = "sha256-CYDn36QUqDvuSLFSIHdKCtmkcmXJefiy35npNNnKzw4=";
          };

          nativeBuildInputs = with python.pkgs; [ setuptools wheel ];
          propagatedBuildInputs = with python.pkgs; [ tree-sitter ];
        };

        batch-tamarin = python.pkgs.buildPythonPackage rec {
          pname = "batch-tamarin";
          version = "1.0.0";
          format = "pyproject";

          src = pkgs.fetchFromGitHub {
            owner = "tamarin-prover";
            repo = "batch-tamarin";
            rev = "v${version}";
            hash = "sha256-z4QTPzfVooTM+C/oZaWYu/QgTcVXeIwU82ZWUZTFzlU=";
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
              tamarin-prover
              graphviz
              coreutils
              bash
              batch-tamarin
            ];
          };

          batch-tamarin = batch-tamarin;
        };

        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            zsh
            tamarin-prover
            graphviz
            coreutils
            bash
            batch-tamarin
          ];
        };
      });
}
