#!/usr/bin/env python3
"""
Tamarin-wrapper main application using typer for CLI functionality.
"""

import typer

app = typer.Typer(help="Tamarin-wrapper")

def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show Tamarin-wrapper version.")
) -> None:
    """
    Entry point for the Tamarin-wrapper application.
    """
    if version: 
        print("Tamarin-wrapper v0.1")


if __name__ == "__main__":
    typer.run(main)