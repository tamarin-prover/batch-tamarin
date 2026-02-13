from pathlib import Path

import typer
from rich import print as rprint

from . import __author__, __contributors__, __version__
from .commands.cache import cache_command
from .commands.check import CheckCommand
from .commands.init import InitCommand
from .commands.report import ReportCommand
from .commands.run import RunCommand
from .model.tamarin_recipe import SchedulingStrategy
from .utils.notifications import notification_manager

app = typer.Typer(help="batch-tamarin")
app.add_typer(cache_command)


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
        rprint(
            r"""[gold3]
██████╗  █████╗ ████████╗ ██████╗██╗  ██╗       ████████╗ █████╗ ███╗   ███╗ █████╗ ██████╗ ██╗███╗   ██╗
██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██║  ██║       ╚══██╔══╝██╔══██╗████╗ ████║██╔══██╗██╔══██╗██║████╗  ██║
██████╔╝███████║   ██║   ██║     ███████║          ██║   ███████║██╔████╔██║███████║██████╔╝██║██╔██╗ ██║
██╔══██╗██╔══██║   ██║   ██║     ██╔══██║  ████╗   ██║   ██╔══██║██║╚██╔╝██║██╔══██║██╔══██╗██║██║╚██╗██║
██████╔╝██║  ██║   ██║   ╚██████╗██║  ██║  ╚═══╝   ██║   ██║  ██║██║ ╚═╝ ██║██║  ██║██║  ██║██║██║ ╚████║
╚═════╝ ╚═╝  ╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝          ╚═╝   ╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝[/gold3]
            """
        )
        rprint(f"Running [bold cyan]v{__version__}[/bold cyan]\n")
        rprint(f"Authored by: {__author__}")
        print(
            "Project initiated for an internship at CISPA, under the supervision of Pr.Dr. Cas Cremers."
        )
        print(
            "Special thanks to the contributors who support this project: "
            + ", ".join(__contributors__)
            + "."
        )
        return

    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        raise typer.Exit()


@app.command()
def run(
    config_file: str = typer.Argument(..., help="JSON recipe file to execute"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output"),
    scheduler: SchedulingStrategy = typer.Option(
        SchedulingStrategy.FIFO,
        "--scheduler",
        "-s",
        help="Task scheduling strategy: fifo (file sequential scheduling), sjf (shortest job first), ljf (longest job first)",
    ),
) -> None:
    """
    Execute tasks from the specified configuration file.
    """
    try:
        RunCommand.run(config_file, debug, scheduler)
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
    spthy_files: list[str] = typer.Argument(
        ..., help="One or more .spthy files to configure"
    ),
    output: str | None = typer.Option(
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


@app.command()
def report(
    results_directory: str = typer.Argument(
        ..., help="Directory containing execution results"
    ),
    output: str = typer.Option(
        "report",
        "--output",
        "-o",
        help="Output file path",
    ),
    format_type: str = typer.Option(
        "md", "--format", "-f", help="Output format (md/html/tex/typ)"
    ),
) -> None:
    """
    Generate a comprehensive report from execution results.

    Analyzes the results directory and generates a detailed report containing
    execution statistics, performance metrics, error analysis, and trace
    visualizations.
    """
    try:
        results_path = Path(results_directory)
        output_path = Path(output)

        ReportCommand.run(results_path, output_path, format_type)

    except typer.Exit:
        raise
    except Exception as e:
        notification_manager.error(f"Report generation failed: {e}")
        raise typer.Exit(1)


def cli():
    """Entry point for the CLI"""
    app()


if __name__ == "__main__":
    app()
