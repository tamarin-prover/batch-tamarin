import asyncio
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Input, Static

from model.tamarin_path import TamarinPath
from model.wrapper import Wrapper


class AddTamarinPath(Widget):
    CSS_PATH = str(Path(__file__).parent / "style/add_tamarin_path.css")

    class PathAdded(Message):
        """Message sent when a path is successfully added."""

        def __init__(self, path: str) -> None:
            self.path = path
            super().__init__()

    def __init__(self, wrapper: Wrapper, **kwargs) -> None:
        super().__init__(**kwargs)
        self.wrapper = wrapper
        self.is_validating = False

    def compose(self) -> ComposeResult:
        """Compose the add path widget."""
        yield Static("Add New Tamarin Path", classes="add-path-title")

        with Vertical(classes="add-path-container"):
            with Horizontal(classes="input-row"):
                yield Input(
                    placeholder="Enter path to tamarin-prover...",
                    classes="path-input",
                    id="path_input",
                )
                yield Button("Browse", classes="browse-btn", id="browse_btn")

            with Horizontal(classes="button-row"):
                yield Button(
                    "Add Path", variant="primary", classes="add-btn", id="add_btn"
                )
                yield Button(
                    "Clear", variant="default", classes="clear-btn", id="clear_btn"
                )

            yield Static("", classes="validation-status", id="status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "add_btn":
            self.add_path()
        elif event.button.id == "clear_btn":
            self.clear_input()
        elif event.button.id == "browse_btn":
            self.browse_for_path()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key)."""
        if event.input.id == "path_input":
            self.add_path()

    def add_path(self) -> None:
        """Add the entered path."""
        if self.is_validating:
            return

        path_input = self.query_one("#path_input", Input)
        path_str = path_input.value.strip()

        if not path_str:
            self.update_status("Please enter a path", "error")
            return

        # Start async validation
        asyncio.create_task(self.validate_and_add_path(path_str))

    async def validate_and_add_path(self, path_str: str) -> None:
        """Validate and add path asynchronously."""
        self.is_validating = True
        self.update_status("⏳ Validating path...", "validating")

        try:
            # Convert to Path object
            path = Path(path_str)

            # Check if file exists
            if not path.exists():
                self.update_status("❌ Path does not exist", "error")
                return

            # Create TamarinPath object (this will validate)
            tamarin_path = TamarinPath(path)

            # Check validation results
            if tamarin_path.version is None:
                self.update_status("❌ Not a valid tamarin-prover", "error")
                return

            if not tamarin_path.test_success:
                self.update_status("❌ Tamarin test failed", "error")
                return

            # Add to wrapper
            self.wrapper.add_tamarin_path(str(path))
            self.update_status(f"✅ Added: {tamarin_path.version}", "success")

            # Clear input and notify
            path_input = self.query_one("#path_input", Input)
            path_input.value = ""

            # Send message to parent
            self.post_message(self.PathAdded(str(path)))

        except Exception as e:
            self.update_status(f"❌ Error: {str(e)}", "error")
        finally:
            self.is_validating = False

    def clear_input(self) -> None:
        """Clear the input field."""
        path_input = self.query_one("#path_input", Input)
        path_input.value = ""
        self.update_status("", "")

    def browse_for_path(self) -> None:
        """Open file browser (placeholder - implementation depends on platform)."""
        # This would need platform-specific implementation
        # For now, just show a message
        self.update_status("File browser not implemented yet", "info")

    def update_status(self, message: str, status_type: str) -> None:
        """Update the status message."""
        status_widget = self.query_one("#status", Static)
        status_widget.update(message)

        # Update CSS class based on status type
        status_widget.remove_class("error", "success", "validating", "info")
        if status_type:
            status_widget.add_class(status_type)
