"""
Tamarin Path Card Widget

This widget displays individual Tamarin path information in a card format
with sections for Path, Test status, and Version, along with a delete button.
"""

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Static

from model.tamarin_path import TamarinPath


class TamarinPathCard(Widget):
    """
    A card widget that displays information about a single Tamarin path.

    Shows the path, test status, version, and provides a delete button.
    """

    CSS_PATH = str(Path(__file__).parent / "style/tamarin_path_card.css")

    class DeleteRequested(Message):
        """Message sent when the delete button is pressed."""

        def __init__(self, tamarin_path: TamarinPath) -> None:
            self.tamarin_path = tamarin_path
            super().__init__()

    def __init__(self, tamarin_path: TamarinPath, **kwargs) -> None:  # type: ignore
        super().__init__(**kwargs)  # type: ignore
        self.tamarin_path = tamarin_path

    def compose(self) -> ComposeResult:
        """Compose the Tamarin path card."""
        with Vertical(classes="tamarin-card"):
            # Header with path and delete button
            with Horizontal(classes="card-header"):
                yield Static("Path:", classes="label")
                yield Static(str(self.tamarin_path.path), classes="path-value")
                yield Button(
                    "🗑",
                    variant="error",
                    classes="delete-btn",
                    id=f"delete_{id(self.tamarin_path)}",
                )

            # Test status section
            with Horizontal(classes="card-row"):
                yield Static("Test:", classes="label")
                test_status = (
                    "✅ Success" if self.tamarin_path.test_success else "❌ Failed"
                )
                test_class = (
                    "test-success" if self.tamarin_path.test_success else "test-failed"
                )
                yield Static(test_status, classes=f"test-value {test_class}")

            # Version section
            with Horizontal(classes="card-row"):
                yield Static("Version:", classes="label")
                version_display = (
                    self.tamarin_path.version
                    if self.tamarin_path.version
                    else "No version"
                )
                version_class = (
                    "version-valid" if self.tamarin_path.version else "version-invalid"
                )
                yield Static(version_display, classes=f"version-value {version_class}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id and event.button.id.startswith("delete_"):
            self.post_message(self.DeleteRequested(self.tamarin_path))

    async def update_tamarin_path(self, tamarin_path: TamarinPath) -> None:
        """Update the card with new Tamarin path information."""
        self.tamarin_path = tamarin_path
        # Trigger a recompose to update the display
        await self.recompose()
