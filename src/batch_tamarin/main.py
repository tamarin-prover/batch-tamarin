from typing import List, Optional

import typer

from . import __author__, __version__
from .commands.check import CheckCommand
from .commands.init import InitCommand
from .commands.run import RunCommand
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


@app.command()
def run(
    config_file: str = typer.Argument(..., help="JSON recipe file to execute"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output"),
) -> None:
    """
    Execute tasks from the specified configuration file.
    """
    try:
        RunCommand.run(config_file, debug)
    except typer.Exit:
        # Re-raise typer.Exit to maintain proper exit codes
        raise
    except Exception as e:
        notification_manager.error(f"Failed to process JSON recipe : {e}")
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
    try:
        CheckCommand.run(config_file, report, debug)
    except typer.Exit:
        raise
    except Exception as e:
        notification_manager.error(f"Failed to check configuration: {e}")
        raise typer.Exit(1)


@app.command()
def init(
    spthy_files: List[str] = typer.Argument(
        ..., help="One or more .spthy files to configure"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file for generated configuration"
    ),
) -> None:
    """
    Interactive configuration generator for batch-tamarin.

    Creates a JSON configuration file from spthy files with interactive prompts.
    """
    try:
        init_command = InitCommand()
        init_command.run(spthy_files, output)
    except KeyboardInterrupt:
        notification_manager.info("Configuration generation cancelled by user")
        raise typer.Exit(1)
    except Exception as e:
        notification_manager.error(f"Configuration generation failed: {e}")
        raise typer.Exit(1)


def cli():
    """Entry point for the CLI"""
    app()


if __name__ == "__main__":
    app()
