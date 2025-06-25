# Tamarin Python Wrapper

A Python wrapper for Tamarin Prover that enables batch execution of protocol verification tasks with JSON configuration files and comprehensive reporting.

## Features

- **Batch Execution**: Run multiple Tamarin models across different Tamarin binary versions
- **JSON Configuration**: Define execution recipes using simple JSON configuration files
- **Resource Management**: Intelligent CPU and memory allocation for parallel task execution
- **Progress Tracking**: Real-time progress updates with Rich-formatted output
- **Output Processing**: Reformat the different Tamarin output to give a detailed summary of execution
- **CLI Interface**: Easy-to-use command-line interface with comprehensive options

## Installation

### From PyPI

```bash
pip install tamarin-wrapper
```

### From TestPyPI

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ tamarin-wrapper
```

### Prerequisites

- **Python 3.9+**
- **Tamarin Prover binaries** (install separately)

## Usage

### Basic Commands

```bash
# Show version
tamarin-wrapper --version

# Show help
tamarin-wrapper --help

# Run with configuration file
tamarin-wrapper recipe.json

# Run with debug output
tamarin-wrapper recipe.json --debug

# Run with Tamarin binary validation
tamarin-wrapper recipe.json --revalidate
```

### Configuration Example

Create a JSON configuration file based on the WPA2 example:

```json
{
  "config": {
    "global_max_cores": 10,
    "global_max_memory": "max",
    "default_timeout": 7200,
    "output_directory": "./results"
  },
  "tamarin_versions": {
    "stable": {
      "path": "tamarin-binaries/tamarin-prover-1.10/1.10.0/bin/tamarin-prover"
    },
    "legacy": {
      "path": "tamarin-binaries/tamarin-prover-1.8/1.8.0/bin/tamarin-prover"
    }
  },
  "tasks": {
    "wpa2": {
      "theory_file": "protocols/wpa2_four_way_handshake_unpatched.spthy",
      "tamarin_versions": ["stable", "legacy"],
      "output_file": "wpa2.txt",
      "preprocess_flags": ["yes"],
      "tamarin_options": ["-v"],
      "ressources": {
        "max_cores": 2,
        "max_memory": 8,
        "timeout": 3600
      },
      "lemmas": [
        {
          "name": "nonce_reuse_key_type",
          "ressources": {
            "max_cores": 1
          }
        },
        {
          "name": "authenticator_rcv_m2_must_be_preceded_by_snd_m1",
          "tamarin_versions": ["stable"],
          "ressources": {
            "max_cores": 4,
            "max_memory": 16,
            "timeout": 30
          }
        }
      ]
    }
  }
}
```

Read the configuration guide to understand how to write a JSON recipe : [`JSON Guide`](RECIPE_GUIDE.md)

## Output
The wrapper will output the results of all analysis in the `output_file` specified in the recipe.
It will follow this pattern :
```
output_directory/
├── failed/
│   ├── output_prefix[\_lemma]\_tamarin_alias.json
│   └── ...
├── models/
│   ├── output_prefix[\_lemma]\_tamarin_alias.spthy
│   └── ...
└── success/
    ├── output_prefix[\_lemma]\_tamarin_alias.json
    └── ...
```
As the name of each directory and file describe, you will find sucessful task in `sucess` and their linked models in `models`
Failed tasks don't output models (that's a tamarin behavior), you will only find a json in `failed`

Here is an example for each result json :
`success/`
```json
{
  "task_id": "wpa2_authenticator_installed_is_unique_for_anonce_dev",
  "warnings": [
    "1 wellformedness check failed!"
  ],
  "tamarin_timing": 12.27,
  "wrapper_measures": {
    "time": 12.385284208023222,
    "avg_memory": 200.17067307692307,
    "peak_memory": 358.34375
  },
  "output_spthy": "results/models/wpa2_authenticator_installed_is_unique_for_anonce_dev.spthy",
  "verified_lemma": {
    "authenticator_installed_is_unique_for_anonce": {
      "steps": 102,
      "analysis_type": "all-traces"
    }
  },
  "falsified_lemma": {},
  "unterminated_lemma": [
    "nonce_reuse_key_type",
    "...",
    "krack_attack_ptk"
  ]
}
```
`failed/`
```json
{
  "task_id": "wpa2_authenticator_rcv_m2_must_be_preceded_by_snd_m1_dev",
  "error_description": "The task exceeded its memory limit. Review the memory limit setting for this task.",
  "wrapper_measures": {
    "time": 30.274985666008433,
    "avg_memory": 566.9329637096774,
    "peak_memory": 1059.609375
  },
  "return_code": -2,
  "last_stderr_lines": [
    "Process exceeded memory limit"
  ]
}
```
## Development

### Contributing

1. **Fork the repository** and create a feature branch:
   ```bash
   git checkout -b feature/my-awesome-feature
   ```

2. **Set up development environment** (see options below)

3. **Install pre-commit hooks**:
   ```bash
   pre-commit install
   ```

4. **Make your changes** and commit them

5. **Push to your branch** and open a pull request

### Development Environment Options

#### Using Nix

```bash
# Enter development environment with all dependencies
nix develop

# Install the package in editable mode (required once per environment)
pip install -e .

# The tamarin-wrapper command is now available
tamarin-wrapper --version
```

#### Using Python Virtual Environment

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements.txt

# The package is installed in editable mode automatically
tamarin-wrapper --version
```

### Testing During Development

Since the package uses proper Python packaging structure, you cannot run `python src/tamarin_wrapper/main.py` directly. Use one of these methods:

```bash
# Method 1 (Recommended): Use the CLI command (after pip install -e .)
tamarin-wrapper

# Method 2: Run as Python module
python -m tamarin_wrapper.main

# Method 3: Test built package (Useful before publishing)
python -m build
pip install dist/tamarin_wrapper-*.whl
```

## Packaging/Publishing

### Building the Package

```bash
# Clean previous builds
rm -rf dist/ build/ **/*.egg-info/ # Be careful, it's still a rm -rf command, might fail because of *.egg-info pattern, you might want to remove it

# Build wheel and source distribution
python -m build
```

### Publishing

#### Test Upload (TestPyPI)
```bash
python -m twine upload --repository testpypi dist/*
```

#### Production Upload (PyPI)
```bash
python -m twine upload dist/*
```

For detailed packaging instructions, see [`PACKAGING.md`](PACKAGING.md).

## License

This project is licensed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**.

See the [LICENSE](LICENSE) file for the full license text.

### License Summary

- ✅ **Use**: Commercial and private use allowed
- ✅ **Modify**: Modifications and derivatives allowed
- ✅ **Distribute**: Distribution allowed
- ❗ **Share Alike**: Derivatives must be licensed under GPL-3.0+
- ❗ **Disclose Source**: Source code must be made available
- ❗ **Include License**: License and copyright notice must be included

## Implementation Details

For detailed architecture, module overview, and workflow documentation, see [`IMPLEMENTATION_GUIDE.md`](IMPLEMENTATION_GUIDE.md).

---

**Note**: This package requires Tamarin Prover to be installed separately. Visit the [Tamarin Prover website](https://tamarin-prover.com) for installation instructions.
