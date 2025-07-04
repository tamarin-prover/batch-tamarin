import asyncio
from pathlib import Path

import typer

from . import __author__, __version__
from .modules.config_manager import ConfigManager
from .modules.output_manager import output_manager
from .modules.tamarin_test_cmd import check_tamarin_integrity
from .runner import TaskRunner
from .utils.model_checking import validate_with_tamarin
from .utils.notifications import notification_manager

app = typer.Typer(help="batch-tamarin")


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version information"
    ),
):
    """
    Batch Tamarin - Protocol verification automation tool.
    """
    if version:
        print(
            r"""
██████╗  █████╗ ████████╗ ██████╗██╗  ██╗    ████████╗ █████╗ ███╗   ███╗ █████╗ ██████╗ ██╗███╗   ██╗
██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██║  ██║    ╚══██╔══╝██╔══██╗████╗ ████║██╔══██╗██╔══██╗██║████╗  ██║
██████╔╝███████║   ██║   ██║     ███████║       ██║   ███████║██╔████╔██║███████║██████╔╝██║██╔██╗ ██║
██╔══██╗██╔══██║   ██║   ██║     ██╔══██║       ██║   ██╔══██║██║╚██╔╝██║██╔══██║██╔══██╗██║██║╚██╗██║
██████╔╝██║  ██║   ██║   ╚██████╗██║  ██║       ██║   ██║  ██║██║ ╚═╝ ██║██║  ██║██║  ██║██║██║ ╚████║
╚═════╝ ╚═╝  ╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝       ╚═╝   ╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝
            """
        )
        print(f"Running v{__version__}")
        print(f"Authored by: {__author__}")
        print(
            "Project initiated for an internship at CISPA, under the supervision of Pr.Dr. Cas Cremers."
        )
        return

    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        raise typer.Exit()


async def process_config_file(config_path: Path) -> None:
    """Process configuration file and execute tasks."""
    try:
        # Load recipe from configuration file
        config_manager = ConfigManager()
        recipe = await config_manager.load_json_recipe(config_path)

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


@app.command()
def run(
    config_file: str = typer.Argument(..., help="JSON recipe file to execute"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output"),
) -> None:
    """
    Execute tasks from the specified configuration file.
    """
    # Set debug mode if enabled
    if debug:
        notification_manager.set_debug(True)
        notification_manager.debug("[NotificationUtil] DEBUG Enabled")

    # Execute config file tasks
    config_path = Path(config_file)
    try:
        asyncio.run(process_config_file(config_path))
    except typer.Exit:
        # Re-raise typer.Exit to maintain proper exit codes
        raise
    except Exception as e:
        notification_manager.error(f"Failed to process JSON recipe : {e}")
        raise typer.Exit(1)


async def check_command(config_path: Path, report: bool) -> None:
    """Check configuration and show executable tasks that would be run."""
    try:
        # Load recipe from configuration file
        config_manager = ConfigManager()
        recipe = await config_manager.load_json_recipe(config_path)

        # Check tamarin integrity
        await check_tamarin_integrity(recipe.tamarin_versions)

        # Initialize output manager (bypass directory creation)
        output_manager.initialize(Path(recipe.config.output_directory), bypass=True)

        # Convert recipe to executable tasks
        executable_tasks = config_manager.recipe_to_executable_tasks(recipe)

        # Collect tamarin validation errors
        tamarin_errors = await validate_with_tamarin(executable_tasks, report)

        # Display the check report
        notification_manager.check_report(recipe, executable_tasks, tamarin_errors)

    except Exception as e:
        notification_manager.error(f"Check failed: {e}")
        raise typer.Exit(1)


@app.command()
def check(
    config_file: str = typer.Argument(..., help="JSON recipe file to check"),
    report: bool = typer.Option(
        False,
        "--report",
        "-r",
        help="Give Tamarin output report",
    ),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output"),
) -> None:
    """
    Check configuration and show executable tasks that would be run.
    """
    # Set debug mode if enabled
    if debug:
        notification_manager.set_debug(True)
        notification_manager.debug("[NotificationUtil] DEBUG Enabled")

    config_path = Path(config_file)
    try:
        asyncio.run(check_command(config_path, report))
    except typer.Exit:
        raise
    except Exception as e:
        notification_manager.error(f"Failed to check configuration: {e}")
        raise typer.Exit(1)


def cli():
    """Entry point for the CLI when installed via pip."""
    app()


if __name__ == "__main__":
    app()
