import asyncio
from pathlib import Path
from typing import Optional

import typer

from model.wrapper import Wrapper
from modules.config_manager import ConfigError, ConfigManager
from runner import TaskRunner
from ui.panels.tamarin_path_manager import TamarinPathManager
from utils.notifications import notification_manager

app = typer.Typer(help="Tamarin-wrapper")


async def load_wrapper_from_config(
    config_path: Path, revalidate: bool = False
) -> Wrapper:
    """Load wrapper from configuration file."""
    try:
        wrapper = await ConfigManager.load_wrapper_config(config_path, revalidate)
        return wrapper
    except ConfigError as e:
        notification_manager.error(f"Failed to load configuration: {e}")
        # Fall back to empty wrapper
        return Wrapper()


async def process_config_file(config_path: Path, revalidate: bool = False) -> None:
    """Process configuration file and execute tasks."""
    try:
        # Load recipe and convert to executable tasks
        config_manager = ConfigManager()
        recipe = await config_manager.load_recipe(config_path, revalidate)
        executable_tasks = config_manager.recipe_to_executable_tasks(recipe)

        # Execute all tasks using runner
        runner = TaskRunner(recipe.config)
        summary = await runner.execute_all_tasks(executable_tasks)

        # Print execution summary
        notification_manager.info(
            f"Execution completed: {summary.successful_tasks}/{summary.total_tasks} tasks successful"
        )

    except Exception as e:
        notification_manager.error(f"Execution failed: {e}")
        raise typer.Exit(1)


def main(
    config_file: Optional[str] = typer.Argument(
        None, help="Configuration file to process and execute tasks"
    ),
    modify: Optional[str] = typer.Option(
        None,
        "--modify",
        "-m",
        help="Load configuration file and open UI for modification",
    ),
    version: bool = typer.Option(
        False, "--version", "-v", help="Show Tamarin-wrapper version."
    ),
    revalidate: bool = typer.Option(
        False,
        "--revalidate",
        "-r",
        help="Re-validate tamarin binaries paths when loading from config, useful for modifying existing configurations",
    ),
) -> None:
    """
    Entry point for the Tamarin-wrapper application.
    """
    if version:
        print("Tamarin-wrapper v0.1")
        return

    if modify:
        # Load configuration and open UI
        config_path = Path(modify)
        wrapper = asyncio.run(load_wrapper_from_config(config_path, revalidate))
    elif config_file:
        # Execute config file tasks
        config_path = Path(config_file)
        try:
            asyncio.run(process_config_file(config_path, revalidate))
            return
        except typer.Exit:
            # Re-raise typer.Exit to maintain proper exit codes
            raise
        except Exception as e:
            notification_manager.error(f"Failed to process config file: {e}")
            raise typer.Exit(1)
    else:
        # Normal startup (auto-detection will run in UI if needed)
        wrapper = Wrapper()

    # Start the UI
    app = TamarinPathManager(wrapper)
    app.run()


if __name__ == "__main__":
    typer.run(main)
