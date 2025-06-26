# Packaging Guide for batch-tamarin

This document explains how to package and publish batch-tamarin to PyPI.

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
   - `dist/batch_tamarin-0.1.0.tar.gz` (source distribution)
   - `dist/batch_tamarin-0.1.0-py3-none-any.whl` (wheel distribution)

## Uploading the Package

### Test on TestPyPI

1. **Upload to TestPyPI:**
   ```bash
   python -m twine upload --repository testpypi dist/*
   ```

2. **Install from TestPyPI:**
   ```bash
   pip install --index-url https://test.pypi.org/simple/ batch-tamarin
   ```

3. **Test the installation:**
   ```bash
   batch-tamarin --version
   ```

## Publishing to PyPI

1. **Upload to PyPI:**
   ```bash
   python -m twine upload dist/*
   ```

2. **Verify installation:**
   ```bash
   pip install batch-tamarin
   batch-tamarin --version
   ```

## Version Management

Update the version in these files before building:
- `src/batch_tamarin/__init__.py` (`__version__`)
- `pyproject.toml` (`version`)

## Package Structure

```
batch-tamarin/
├── pyproject.toml          # Main configuration
├── README.md              # Package description
├── LICENSE                # GPL-3.0 license
├── MANIFEST.in            # Additional files to include
├── requirements.txt       # Production dependencies (keep for dev)
├── requirements-dev.txt   # Development dependencies
└── src/
    └── batch_tamarin/   # Main package
        ├── __init__.py    # Package initialization
        ├── main.py        # Entry point
        └── ...
```

## Key Features

- ✅ Modern `pyproject.toml` configuration
- ✅ Proper package structure with relative imports
- ✅ CLI entry point: `batch-tamarin`
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
