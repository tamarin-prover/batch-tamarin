import asyncio
from pathlib import Path
from typing import Optional

import typer

from model.wrapper import Wrapper
from modules.config_manager import ConfigError, ConfigManager
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


def main(
    config_file: Optional[str] = typer.Argument(
        None, help="Configuration file to process (future implementation)"
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
        help="Re-validate tamarin paths when loading from config",
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
        # Future: Direct processing mode
        notification_manager.info("Direct processing mode not yet implemented")
        return
    else:
        # Normal startup (auto-detection will run in UI if needed)
        wrapper = Wrapper()

    # Start the UI
    app = TamarinPathManager(wrapper)
    app.run()


if __name__ == "__main__":
    typer.run(main)
