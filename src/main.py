#!/usr/bin/env python3
"""
Tamarin-wrapper
"""

import typer

from tui.config import ConfigManager
from tui.tamarin_path_selector import run_tamarin_path_selector

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
        selected_path = run_tamarin_path_selector()
        if selected_path:
            print(f"Selected Tamarin path: {selected_path}")
            ConfigManager().set_selected_path(selected_path)
        else:
            print("No path selected.")


if __name__ == "__main__":
    typer.run(main)
