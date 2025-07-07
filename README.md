# Batch Tamarin (`batch-tamarin`) : Tamarin Python Wrapper

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-gold.svg)](https://github.com/tamarin-prover/batch-tamarin/blob/main/LICENSE) [![Release](https://img.shields.io/badge/release-0.2.2-forestgreen)](https://github.com/tamarin-prover/batch-tamarin/releases) [![PyPI version](https://img.shields.io/pypi/v/batch-tamarin.svg?color=blue)](https://pypi.org/project/batch-tamarin/)

A Python wrapper for Tamarin Prover that enables batch execution of protocol verification tasks with JSON configuration files, comprehensive reporting, and validation tools.

![WrapperLogo](https://raw.githubusercontent.com/tamarin-prover/batch-tamarin/main/assets/logo.png)

## Features

-   **Batch Execution**: Run multiple Tamarin models across different Tamarin binary versions
-   **JSON Configuration**: Define execution recipes using simple JSON configuration files
-   **Interactive Configuration**: Generate JSON configurations from spthy files with guided prompts
-   **Resource Management**: Intelligent CPU and memory allocation for parallel task execution
-   **Progress Tracking**: Real-time progress updates with Rich-formatted output
-   **Output Processing**: Reformat the different Tamarin output to give a detailed summary of execution
-   **CLI Interface**: Easy-to-use command-line interface with `run`, `check`, and `init` commands
-   **Configuration Validation**: Validate JSON recipes and preview tasks before execution
-   **Wellformedness Checking**: Check theory files for syntax errors and warnings

## Table of Contents

-   [Features](#features)
-   [Installation](#installation)
    -   [Prerequisites](#prerequisites)
    -   [From PyPI](#from-pypi)
    -   [From local package](#from-local-package)
-   [Usage](#usage)
    -   [Basic Commands](#basic-commands)
    -   [Configuration Example](#configuration-example)
    -   [Output](#output)
-   [Development](#development)
    -   [Contributing](#contributing)
    -   [Dependencies, Configuration](#dependencies-configuration)
        -   [Using Nix (the easy way)](#using-nix-the-easy-way)
        -   [Using Python Virtual Environment (still pretty easy)](#using-python-virtual-environment-still-pretty-easy)
    -   [Testing During Development](#testing-during-development)
-   [Packaging/Publishing](#packagingpublishing)
    -   [Building the Package](#building-the-package)
    -   [Publishing](#publishing)
-   [License](#license)
    -   [License Summary](#license-summary)
-   [Implementation Details](#implementation-details)
-   [Acknowledgments](#acknowledgments)
-   [Final Note](#final-note)

## Installation

### Prerequisites

-   **Python 3.9+**
-   **Tamarin Prover binaries** (installed separately)

### From PyPI

```bash
pip install batch-tamarin
```

### From local package

Get the latest release from this github repo.

```bash
pip install pip install ./batch_tamarin-0.1.1-py3-none-any.whl
```

## Usage

### Basic Commands

```bash
# Show version
batch-tamarin --version

# Show help
batch-tamarin --help

# Run tasks with configuration file
batch-tamarin run recipe.json

# Run with debug output
batch-tamarin run recipe.json --debug

# Check configuration and preview tasks
batch-tamarin check recipe.json

# Check with detailed wellformedness report
batch-tamarin check recipe.json --report

# Check with debug output
batch-tamarin check recipe.json --debug

# Generate configuration interactively from spthy files
batch-tamarin init protocol.spthy

# Generate configuration with multiple files and custom output
batch-tamarin init protocol1.spthy protocol2.spthy --output my_recipe.json
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
			"resources": {
				"max_cores": 2,
				"max_memory": 8,
				"timeout": 3600
			},
			"lemmas": [
				{
					"name": "nonce_reuse_key_type",
					"resources": {
						"max_cores": 1
					}
				},
				{
					"name": "authenticator_rcv_m2_must_be_preceded_by_snd_m1",
					"tamarin_versions": ["stable"],
					"resources": {
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

Read the configuration guide to understand how to write a JSON recipe : [`JSON Guide`](https://github.com/tamarin-prover/batch-tamarin/blob/main/RECIPE_GUIDE.md)

### Output

The wrapper will output the results of all analysis in the `output_file` specified in the recipe.
It will follow this pattern :

```
output_directory/
├── failed/
│   ├── output_prefix[\_lemma]\_tamarin_alias.json
│   └── ...
├── proofs/
│   ├── output_prefix[\_lemma]\_tamarin_alias.spthy
│   └── ...
└── success/
    ├── output_prefix[\_lemma]\_tamarin_alias.json
    └── ...
```

As the name of each directory and file describe, you will find successful task in `success` and their linked models proofs in `proofs`
Failed tasks don't output proofs (that's a tamarin behavior), you will only find a json in `failed`

Here is an example for each result json :
`success/`

```json
{
	"task_id": "wpa2_authenticator_installed_is_unique_for_anonce_dev",
	"warnings": ["1 wellformedness check failed!"],
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
	"unterminated_lemma": ["nonce_reuse_key_type", "...", "krack_attack_ptk"]
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
	"last_stderr_lines": ["Process exceeded memory limit"]
}
```

## Development

A macOS or Linux environment is highly recommended, as tamarin-prover is only running on these OS. You can use WSL2 on Windows hosts.

### Contributing

1. **Fork the repository** and create a feature branch:

    ```bash
    git checkout -b feature/my-awesome-feature
    ```

2. **Set up development environment** (see options below)

3. **Install pre-commit hooks**:

    ```bash
    ./setup-hooks.sh
    ```

4. **Make your changes** and commit them

5. **Push to your branch** and open a pull request

### Dependencies, Configuration

#### Using Nix (the easy way)

```bash
# Enter development environment with all dependencies
nix develop

# Install the package in editable mode (required once per environment)
pip install -e .

# The batch-tamarin command is now available
batch-tamarin --version
```

#### Using Python Virtual Environment (still pretty easy)

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install development dependencies
pip install -r requirements.txt

# The package is installed in editable mode automatically
batch-tamarin --version
```

### Testing During Development

#### Running Tests

The project uses pytest for testing. To run the test suite:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_config_manager.py

# Run with coverage report
pytest --cov=src/batch_tamarin
```

#### Testing the Package Installation

Since the package uses proper Python packaging structure, you cannot run `python src/batch_tamarin/main.py` directly. Use one of these methods:

```bash
# Method 1 (Recommended): Use the CLI command (after pip install -e .)
batch-tamarin --help

# Method 2: Test built package (Useful before publishing)
python -m build
pip install dist/batch_tamarin-*.whl
```

## Packaging/Publishing

### Building the Package

```bash
# Clean previous builds
rm -rf dist/ build/ **/*.egg-info/ # Be careful, it's still a rm -rf command
# Might fail because of *.egg-info pattern, you might want to remove it

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

For detailed packaging instructions, see [`PACKAGING.md`](https://github.com/tamarin-prover/batch-tamarin/blob/main/PACKAGING.md).

## License

This project is licensed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**.

See the [LICENSE](https://github.com/tamarin-prover/batch-tamarin/blob/main/LICENSE) file for the full license text.

### License Summary

-   ✅ **Use**: Commercial and private use allowed
-   ✅ **Modify**: Modifications and derivatives allowed
-   ✅ **Distribute**: Distribution allowed
-   ❗ **Share Alike**: Derivatives must be licensed under GPL-3.0+
-   ❗ **Disclose Source**: Source code must be made available
-   ❗ **Include License**: License and copyright notice must be included

## Implementation Details

For detailed architecture, module overview, and workflow documentation, see [`ARCHITECTURE.md`](https://github.com/tamarin-prover/batch-tamarin/blob/main/ARCHITECTURE.md).

---

## Acknowledgments

This project has been done during an internship at CISPA.
It was made with the help of the Cas Cremers research group, a particular thanks should go to :

-   Cas Cremers, as the supervisor of this internship but also for all his support and guidance.
-   Maïwenn Racouchot and Aleksi Peltonen for their close collaboration, feedback, and, most importantly, the logo.
-   Esra Günsay, Erik Pallas, Niklas Medinger, Aurora Naska and Alexander Dax for their valuable support and development ideas.

## Final Note

As this package need to directly use `tamarin-prover` commands, you can visit the [Tamarin Prover website](https://tamarin-prover.com) for installation instructions.
