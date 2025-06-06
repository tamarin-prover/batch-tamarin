from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static

from model.tamarin_path import TamarinPath
from model.wrapper import Wrapper
from ui.widgets.tamarin_path_card import TamarinPathCard


class CurrentTamarinPath(Widget):
    CSS_PATH = str(Path(__file__).parent / "style/current_tamarin_path.css")

    class PathDeleteRequested(Message):
        """Message sent when a path deletion is requested."""

        def __init__(self, tamarin_path: TamarinPath) -> None:
            self.tamarin_path = tamarin_path
            super().__init__()

    def __init__(self, wrapper: Wrapper, **kwargs) -> None:  # type: ignore
        super().__init__(**kwargs)  # type: ignore
        self.wrapper = wrapper

    def compose(self) -> ComposeResult:
        """Compose the current Tamarin path viewer widget."""
        yield Static("Current Tamarin Paths", classes="path-viewer-title")

        with Vertical(classes="path-container", id="paths_container"):
            tamarin_paths = self.wrapper.get_tamarin_paths()

            if not tamarin_paths:
                yield Static("No Tamarin paths found", classes="no-paths")
            else:
                for tamarin_path in tamarin_paths:
                    yield TamarinPathCard(tamarin_path, id=f"card_{id(tamarin_path)}")

    async def refresh_paths(self):
        """Refresh the display when paths are updated."""
        await self.recompose()

    def on_tamarin_path_card_delete_requested(
        self, event: TamarinPathCard.DeleteRequested
    ) -> None:
        """Handle delete requests from cards."""
        # Forward the message to parent
        self.post_message(self.PathDeleteRequested(event.tamarin_path))
