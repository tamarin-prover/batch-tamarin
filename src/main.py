#!/usr/bin/env python3
"""
Tamarin-wrapper
"""

import typer

app = typer.Typer(help="Tamarin-wrapper")


def main(
    version: bool = typer.Option(
        False, "--version", "-v", help="Show Tamarin-wrapper version."
    )
) -> None:
    """
    Entry point for the Tamarin-wrapper application.
    """
    if version:
        print("Tamarin-wrapper v0.1")
        return
    else:
        print("Welcome to Tamarin-wrapper!")
        print("Use --version or -v to see the version.")


if __name__ == "__main__":
    typer.run(main)
