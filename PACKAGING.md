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

The project uses a **single source of truth** for versioning: `pyproject.toml`.

1. **Bump the version** in `pyproject.toml` (`project.version`).
2. **Run the update script** (or let the pre-commit hook do it automatically):
   ```bash
   python scripts/update_version.py
   ```
   This propagates the version to:
   - `src/batch_tamarin/__init__.py` (`__version__`)
   - `README.md` release badge
   - `examples/__dockerfiles__/with-batch-tamarin/*.nix`

3. **Update `uv.lock`** if you use `uv`:
   ```bash
   uv lock
   ```

### Notes

- `__author__` may contain [Rich](https://github.com/Textualize/rich) console markup
  (e.g. `[dim green]…[/dim green]`) for styled `--version` output. The update script
  preserves any existing markup, so manual styling edits are safe.
- When the version changes, the script invalidates SHA256 hashes in the Nix
  examples so that Nix will report the correct new hash on the next build.
- `__contributors__` in `__init__.py` is also preserved by the script.

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
