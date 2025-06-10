# Tamarin Python Wrapper

## Description

The Tamarin Python Wrapper provides scripts to run one or multiple models using one or multiple Tamarin binaries. Configure your "recipe" in a JSON file, and get a detailed execution report with parsed output.

## Features

- Run single or multiple models across one or more Tamarin binaries.
- Define execution recipes via a JSON configuration file.
- Parse and summarize execution outputs into comprehensive reports.
- Interactive UI for managing Tamarin paths and configurations.
- Notification system for execution status and results.

## Installation

### Using Nix Flakes

Enter the development environment with :

```sh
nix develop
```

### Using Python Virtual Environment

Prerequisites:

- Python 3.9+
- venv
- Tamarin Prover binaries
- pre-commit

```sh
cd src
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```sh
python main.py                   # launch UI (auto-detect)
python main.py -v                # show version
python main.py config.json -m    # modify existing config
python main.py config.json -m -r # modify with re-validation
```

## Configuration Example

Preview of `example_config.json`:

```json
{
  "tamarin_path": [
    {
      "path": "tamarin-binaries/tamarin-prover-1.8/1.8.0/bin/tamarin-prover",
      "version": "1.8.0",
      "test_success": true
    },
    {
      "path": "tamarin-binaries/tamarin-prover-1.6.1/1.6.1/bin/tamarin-prover",
      "version": "1.6.1",
      "test_success": false
    },
    {
      "path": "tamarin-binaries/tamarin-prover-dev/.stack-work/dist/aarch64-osx/ghc-9.6.6/build/tamarin-prover/tamarin-prover",
      "version": "1.11.0",
      "test_success": false
    }
  ]
}
```

## Implementation Guide

For detailed architecture, module overview, and workflow, see [`IMPLEMENTATION_GUIDE.md`](IMPLEMENTATION_GUIDE.md).

## Contributing

1. Fork the repository and create a feature branch:
   ```sh
   git checkout -b feature/my-awesome-feature
   ```
2. Install pre-commit hooks (that will format your code automatically):
   ```sh
   ./setup-hooks.sh
   ```
3. Commit your changes and push to your branch.
4. Open a pull request.
