{
  description = "batch-tamarin Python project";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python3;

        # Extract metadata directly from pyproject.toml
        pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);
        packageVersion = pyproject.project.version;

        # Extract runtime dependencies
        runtimeDeps = with python.pkgs; [
          typer
          pydantic
          psutil
          tree-sitter
          diskcache
          jinja2
          graphviz
          # py-tree-sitter-spthy will be installed with a shell hook since it's not in nixpkgs
        ];

        # Extract development dependencies
        devDeps = with python.pkgs; [
          black
          isort
          autoflake
          pytest
          pytest-asyncio
          build
          twine
          setuptools
          wheel
          pip
          pre-commit-hooks
        ];

        # Build the batch-tamarin package properly
        batch-tamarin = python.pkgs.buildPythonPackage {
          pname = "batch-tamarin";
          version = packageVersion;
          format = "pyproject";

          src = ./.;

          nativeBuildInputs = with python.pkgs; [
            setuptools
            wheel
            build
          ];

          propagatedBuildInputs = runtimeDeps;

          # Don't run tests during build (they require Tamarin binaries)
          doCheck = false;

          meta = with pkgs.lib; {
            description = pyproject.project.description;
            license = licenses.gpl3Plus;
            maintainers = [ ];
          };
        };

        # Development Python environment with dependencies but without the package itself
        # This allows for editable installs during development
        devPythonEnv = python.withPackages (ps: runtimeDeps ++ devDeps);

      in
      {
        # Main package output
        packages.default = batch-tamarin;
        packages.batch-tamarin = batch-tamarin;

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
            # Create a local development directory
            export DEV_ROOT="$PWD/.dev"
            mkdir -p "$DEV_ROOT"

            # Set up Python environment for editable installs
            export PYTHONPATH="$PWD/src:$DEV_ROOT/lib/python${python.pythonVersion}/site-packages:$PYTHONPATH"
            export PIP_PREFIX="$DEV_ROOT"
            export PIP_USER=false
            export PIP_NO_BUILD_ISOLATION=false

            # Add local bin to PATH
            export PATH="$DEV_ROOT/bin:$PATH"

            # Install py-tree-sitter-spthy via pip if not already installed
            echo "📦 Installing py-tree-sitter-spthy via pip..."
            pip install "py-tree-sitter-spthy>=1.2.0"

            echo "🚀 Batch Tamarin development environment"
            echo "📦 Python ${python.version} with dependencies available"
            echo "📋 Package version: ${packageVersion}"
            echo "📁 Development root: $DEV_ROOT"
            echo ""
            echo "🔧 Setup:"
            echo "  pip install -e .             # Install package in editable mode"
            echo ""
            echo "🔧 Development commands:"
            echo "  python -m build              # Build package"
            echo "  python -m twine upload dist/* # Upload to PyPI"
            echo "  black src/                   # Format code"
            echo "  isort src/                   # Sort imports"
            echo "  autoflake --recursive src/   # Remove unused imports"
            echo "  pytest                       # Run tests"
            echo "  batch-tamarin --help       # Test CLI (after editable install)"
            echo ""
            echo "🔧 Pre-commit setup:"
            echo "  pre-commit install          # Set up pre-commit hook (run once)"
            echo "  pre-commit run -a           # Run all hooks"
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
