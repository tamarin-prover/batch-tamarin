#!/bin/bash

# Setup script for pre-commit hooks in tamarin-wrapper project

set -e

echo "Setting up pre-commit hooks for tamarin-wrapper..."

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "Error: Not in a git repository. Please run 'git init' first."
    exit 1
fi

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo "Error: pre-commit is not installed."
    exit 1
fi

# Install pre-commit hooks
echo "Installing pre-commit hooks..."
pre-commit install

# Run pre-commit on all files to ensure everything is working
echo "Running pre-commit on all files to verify setup..."
pre-commit run --all-files

echo "✅ Pre-commit hooks have been successfully installed!"
echo ""
echo "From now on, your code will be automatically formatted before each commit."
echo "You can also run 'pre-commit run --all-files' manually to format all files."
echo ""
echo "Available formatting tools:"
echo "  - black: Python code formatter"
echo "  - isort: Import sorter"
echo "  - autoflake: Removes unused imports and variables"
echo "  - Various pre-commit hooks for general file cleanup"
