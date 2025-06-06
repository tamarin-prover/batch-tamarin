from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Button, Footer, Header, Static

from model.wrapper import Wrapper
from ui.widgets.add_tamarin_path import AddTamarinPath
from ui.widgets.current_tamarin_path import CurrentTamarinPath
from utils.notifications import notification_manager


class TamarinPathManager(App):  # type: ignore
    """Terminal UI for managing Tamarin installation paths, used by the Tamarin-wrapper."""

    CSS_PATH = str(Path(__file__).parent / "style/tamarin_path_manager.css")

    BINDINGS = [("q, escape", "back", "Back"), ("space", "select", "Select")]

    def __init__(self, wrapper: Wrapper) -> None:
        super().__init__()
        self.wrapper = wrapper
        notification_manager.set_app(self)  # type: ignore

    def compose(self) -> ComposeResult:
        """Compose the selection path panel."""
        yield Header()
        yield Static("Tamarin Path Manager", classes="title")

        with Container(classes="main"):
            yield CurrentTamarinPath(self.wrapper, id="current_paths")
            yield AddTamarinPath(self.wrapper, id="add_path")
            with Container(classes="buttons"):
                yield Button("Cancel", variant="default", id="cancel_btn")
                yield Button("Save&Exit", variant="primary", id="save_btn")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel_btn":
            self.exit()  # type: ignore
        elif event.button.id == "save_btn":
            self.save_and_exit()

    async def on_add_tamarin_path_path_added(
        self, event: AddTamarinPath.PathAdded
    ) -> None:
        """Handle when a new path is added."""
        # Refresh the current paths display
        current_paths = self.query_one("#current_paths", CurrentTamarinPath)
        await current_paths.refresh_paths()

    def save_and_exit(self) -> None:
        """Save changes and exit."""
        # Here you would implement saving to config file if needed
        self.exit()  # type: ignore
