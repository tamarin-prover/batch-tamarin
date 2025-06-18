#!/usr/bin/env python3
"""Build script for Tamarin tree-sitter grammar."""

import sys
from pathlib import Path

try:
    from tree_sitter import Language
except ImportError:
    print("Error: tree-sitter not installed. Run: pip install tree-sitter")
    sys.exit(1)


def build_tamarin_grammar():
    """Build the Tamarin spthy tree-sitter grammar from subtree."""

    grammar_dir = Path("vendor/tree-sitter-spthy")
    if not grammar_dir.exists():
        print(
            "Error: Tamarin tree-sitter grammar not found in vendor/tree-sitter-spthy"
        )
        sys.exit(1)

    build_dir = Path("src/tamarin_wrapper/modules/parsers/build")
    build_dir.mkdir(parents=True, exist_ok=True)

    print("Building Tamarin spthy tree-sitter grammar...")
    try:
        Language.build_library(str(build_dir / "tamarin-spthy.so"), [str(grammar_dir)])
        print("✓ Grammar built successfully")

    except Exception as e:
        print(f"Error building grammar: {e}")
        print("Ensure you have: C compiler, Node.js, and tree-sitter installed")
        sys.exit(1)


def verify_setup():
    """Verify that the tree-sitter setup works."""
    grammar_path = Path("src/tamarin_wrapper/modules/parsers/build/tamarin-spthy.so")

    if not grammar_path.exists():
        return False

    try:
        Language(str(grammar_path), "spthy")
        return True
    except:
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.verify:
        if verify_setup():
            print("✓ Tree-sitter setup working")
        else:
            print("✗ Setup verification failed")
            sys.exit(1)
    else:
        build_tamarin_grammar()
