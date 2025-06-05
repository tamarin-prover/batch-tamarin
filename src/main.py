import typer

from model.wrapper import Wrapper
from ui.panels.tamarin_path_manager import TamarinPathManager

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
        wrapper = Wrapper()
        app = TamarinPathManager(wrapper)
        app.run()


if __name__ == "__main__":
    typer.run(main)
