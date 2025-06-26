import asyncio
from pathlib import Path
from typing import Optional

import typer

from . import __author__, __version__
from .modules.config_manager import ConfigManager
from .runner import TaskRunner
from .utils.notifications import notification_manager

app = typer.Typer(help="Tamarin-wrapper")


async def process_config_file(config_path: Path, revalidate: bool = False) -> None:
    """Process configuration file and execute tasks."""
    try:
        # Load recipe from configuration file
        config_manager = ConfigManager()
        recipe = await config_manager.load_json_recipe(config_path, revalidate)

        # Initialize TaskRunner - this validates and potentially corrects resource limits
        # The ResourceManager within TaskRunner may update recipe.config with corrected values
        runner = TaskRunner(recipe)

        # Convert recipe to executable tasks using the recipe
        executable_tasks = config_manager.recipe_to_executable_tasks(recipe)

        # Execute all tasks using runner
        await runner.execute_all_tasks(executable_tasks)

    except Exception as e:
        notification_manager.error(f"Execution failed: {e}")
        raise typer.Exit(1)


def main(
    config_file: Optional[str] = typer.Argument(
        None, help="JSON recipe file to execute"
    ),
    version: bool = typer.Option(
        False, "--version", "-v", help="Show Tamarin-wrapper version."
    ),
    revalidate: bool = typer.Option(
        False,
        "--revalidate",
        "-r",
        help="Check tamarin binaries integrity at startup.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Enable debug output.",
    ),
) -> None:
    """
    Entry point for the Tamarin-wrapper application.
    """
    # Set debug mode if enabled
    if debug:
        notification_manager.set_debug(True)
        notification_manager.debug("[NotificationUtil] DEBUG Enabled")

    if version:
        print(
            r"""
▗▄▄▄▖▗▄▖ ▗▖  ▗▖ ▗▄▖ ▗▄▄▖ ▗▄▄▄▖▗▖  ▗▖    ▗▖ ▗▖▗▄▄▖  ▗▄▖ ▗▄▄▖ ▗▄▄▖ ▗▄▄▄▖▗▄▄▖
  █ ▐▌ ▐▌▐▛▚▞▜▌▐▌ ▐▌▐▌ ▐▌  █  ▐▛▚▖▐▌    ▐▌ ▐▌▐▌ ▐▌▐▌ ▐▌▐▌ ▐▌▐▌ ▐▌▐▌   ▐▌ ▐▌
  █ ▐▛▀▜▌▐▌  ▐▌▐▛▀▜▌▐▛▀▚▖  █  ▐▌ ▝▜▌    ▐▌█▐▌▐▛▀▚▖▐▛▀▜▌▐▛▀▘ ▐▛▀▘ ▐▛▀▀▘▐▛▀▚▖
  █ ▐▌ ▐▌▐▌  ▐▌▐▌ ▐▌▐▌ ▐▌▗▄█▄▖▐▌  ▐▌    ▐▙█▟▌▐▌ ▐▌▐▌ ▐▌▐▌   ▐▌   ▐▙▄▄▖▐▌ ▐▌
            """
        )
        print(f"Running v{__version__}")
        print(f"Authored by: {__author__}")
        print(
            "Project initiated for an internship at CISPA, under the supervision of Pr.Dr. Cas Cremers."
        )
        return

    # Check if config file is provided when not showing version
    if not config_file:
        print("Error: Missing argument 'CONFIG_FILE'.")
        print("Usage: tamarin-wrapper [OPTIONS] CONFIG_FILE")
        print("Try 'tamarin-wrapper --help' for help.")
        raise typer.Exit(1)

    # Execute config file tasks
    config_path = Path(config_file)
    try:
        asyncio.run(process_config_file(config_path, revalidate))
    except typer.Exit:
        # Re-raise typer.Exit to maintain proper exit codes
        raise
    except Exception as e:
        notification_manager.error(f"Failed to process JSON recipe : {e}")
        raise typer.Exit(1)


def cli():
    """Entry point for the CLI when installed via pip."""
    typer.run(main)


if __name__ == "__main__":
    typer.run(main)
