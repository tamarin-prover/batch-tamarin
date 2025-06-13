import asyncio
from pathlib import Path

import typer

from modules.config_manager import ConfigManager
from runner import TaskRunner
from utils.notifications import notification_manager

app = typer.Typer(help="Tamarin-wrapper")


async def process_config_file(config_path: Path, revalidate: bool = False) -> None:
    """Process configuration file and execute tasks."""
    try:
        # Load recipe and convert to executable tasks
        config_manager = ConfigManager()
        recipe = await config_manager.load_json_recipe(config_path, revalidate)
        executable_tasks = config_manager.recipe_to_executable_tasks(recipe)

        # Execute all tasks using runner
        runner = TaskRunner(recipe.config)
        await runner.execute_all_tasks(executable_tasks)

    except Exception as e:
        notification_manager.error(f"Execution failed: {e}")
        raise typer.Exit(1)


def main(
    config_file: str = typer.Argument(..., help="JSON recipe file to execute"),
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
        print("Tamarin-wrapper v0.1")
        return

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


if __name__ == "__main__":
    typer.run(main)
