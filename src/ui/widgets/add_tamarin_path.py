import asyncio
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Input, Static

from model.wrapper import Wrapper


class AddTamarinPath(Widget):
    CSS_PATH = str(Path(__file__).parent / "style/add_tamarin_path.css")

    class PathAdded(Message):
        """Message sent when a path is successfully added."""

        def __init__(self, path: str) -> None:
            self.path = path
            super().__init__()

    def __init__(self, wrapper: Wrapper, **kwargs) -> None:  # type: ignore
        super().__init__(**kwargs)  # type: ignore
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
                yield Button(
                    "Add Path", variant="primary", classes="add-btn", id="add_btn"
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "add_btn":
            self.add_path()

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
            from utils.notifications import notification_manager

            notification_manager.error("Please enter a path")
            return

        # Start async validation
        asyncio.create_task(self.validate_and_add_path(path_str))

    async def validate_and_add_path(self, path_str: str) -> None:
        """Validate and add path asynchronously."""
        from utils.notifications import notification_manager

        self.is_validating = True
        notification_manager.info("⏳ Validating path...")

        try:
            # Convert to Path object
            path = Path(path_str)

            # Check if file exists
            if not path.exists():
                notification_manager.error("❌ Path does not exist")
                return

            # Add to wrapper (this will validate asynchronously)
            tamarin_path = await self.wrapper.add_tamarin_path(str(path))

            # Check validation results and provide appropriate feedback
            if not tamarin_path.version:
                notification_manager.error(
                    "❌ Not a valid tamarin-prover - no version detected"
                )
                return

            if tamarin_path.test_success:
                notification_manager.info(
                    f"✅ Added: {tamarin_path.version} - fully functional"
                )
            else:
                notification_manager.warning(
                    f"⚠️ Added: {tamarin_path.version} - test failed, may work partially"
                )

            # Clear input and notify parent
            path_input = self.query_one("#path_input", Input)
            path_input.value = ""

            # Send message to parent
            self.post_message(self.PathAdded(str(path)))

        except Exception as e:
            notification_manager.error(f"❌ Error: {str(e)}")
        finally:
            self.is_validating = False
