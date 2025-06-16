# Packaging Guide for tamarin-wrapper

This document explains how to package and publish tamarin-wrapper to PyPI.

## Building the Package

1. **Clean previous builds:**
   ```bash
   rm -rf dist/ build/ **/*.egg-info/
   ```

2. **Build the package:**
   ```bash
   python -m build
   ```

   This creates:
   - `dist/tamarin_wrapper-0.1.0.tar.gz` (source distribution)
   - `dist/tamarin_wrapper-0.1.0-py3-none-any.whl` (wheel distribution)

## Uploading the Package

### Test on TestPyPI

1. **Upload to TestPyPI:**
   ```bash
   python -m twine upload --repository testpypi dist/*
   ```

2. **Install from TestPyPI:**
   ```bash
   pip install --index-url https://test.pypi.org/simple/ tamarin-wrapper
   ```

3. **Test the installation:**
   ```bash
   tamarin-wrapper --version
   ```

## Publishing to PyPI

1. **Upload to PyPI:**
   ```bash
   python -m twine upload dist/*
   ```

2. **Verify installation:**
   ```bash
   pip install tamarin-wrapper
   tamarin-wrapper --version
   ```

## Version Management

Update the version in these files before building:
- `src/tamarin_wrapper/__init__.py` (`__version__`)
- `pyproject.toml` (`version`)

## Package Structure

```
tamarin-wrapper/
├── pyproject.toml          # Main configuration
├── README.md              # Package description
├── LICENSE                # GPL-3.0 license
├── MANIFEST.in            # Additional files to include
├── requirements.txt       # Production dependencies (keep for dev)
├── requirements-dev.txt   # Development dependencies
└── src/
    └── tamarin_wrapper/   # Main package
        ├── __init__.py    # Package initialization
        ├── main.py        # Entry point
        └── ...
```

## Key Features

- ✅ Modern `pyproject.toml` configuration
- ✅ Proper package structure with relative imports
- ✅ CLI entry point: `tamarin-wrapper`
- ✅ Separation of production and development dependencies
- ✅ GPL-3.0 license
- ✅ Compatible with Nix development environment

## Dependencies

### Production (included in package):
- `typer>=0.15.0`
- `pydantic>=2.11.0`
- `psutil>=7.0.0`

### Development (excluded from package):
- `black>=25.1.0`
- `isort>=6.0.1`
- `autoflake>=2.3.1`
- `pre-commit>=4.2.0`
- `pytest>=8.3.5`

## Notes

- The package excludes system dependencies (Tamarin Prover, etc.)
- Users need to install Tamarin Prover separately
- The original `requirements.txt` is kept for development convenience
- Nix users can continue using `nix develop`
