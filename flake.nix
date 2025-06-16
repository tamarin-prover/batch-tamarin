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

        # Build the tamarin-wrapper package properly
        tamarin-wrapper = python.pkgs.buildPythonPackage rec {
          pname = "tamarin-wrapper";
          version = "0.1.2";
          format = "pyproject";

          src = ./.;

          nativeBuildInputs = with python.pkgs; [
            setuptools
            wheel
            build
          ];

          propagatedBuildInputs = with python.pkgs; [
            typer
            pydantic
            psutil
          ];

          # Don't run tests during build (they require Tamarin binaries)
          doCheck = false;

          meta = with pkgs.lib; {
            description = "Python wrapper for Tamarin Prover with JSON recipe execution";
            license = licenses.gpl3Plus;
            maintainers = [ ];
          };
        };

        # Development environment with the package and tools
        devPythonEnv = python.withPackages (ps: with ps; [
          # Include our package in development mode
          tamarin-wrapper

          # Development tools
          black
          isort
          autoflake
          build
          twine
          pip
        ]);

      in
      {
        # Main package output
        packages.default = tamarin-wrapper;
        packages.tamarin-wrapper = tamarin-wrapper;

        # Development shell
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            devPythonEnv
            pre-commit

            # Tamarin dependencies
            maude
            graphviz
            stack
            ghc
            zlib
            libffi
          ];

          shellHook = ''
            echo "🚀 Tamarin-wrapper development environment"
            echo "📦 Package: tamarin-wrapper v0.1.2"
            echo "🔧 Available commands:"
            echo "  tamarin-wrapper --version    # Test CLI"
            echo "  tamarin-wrapper --help       # Show help"
            echo "  python -m build              # Build package"
            echo "  python -m twine upload dist/* # Upload to PyPI"
          '';
        };

        # Development environment for building packages
        devShells.packaging = pkgs.mkShell {
          buildInputs = with pkgs; [
            (python.withPackages (ps: with ps; [
              build
              twine
              setuptools
              wheel
            ]))
          ];
        };
      });
}
