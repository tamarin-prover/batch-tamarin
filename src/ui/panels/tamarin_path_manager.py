import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Static

from model.wrapper import Wrapper
from modules.process_manager import process_manager
from utils.notifications import notification_manager


class TamarinPathManager(App):  # type: ignore
    """Simple Terminal UI for managing Tamarin installation paths."""

    CSS_PATH = str(Path(__file__).parent / "style/tamarin_path_manager.css")

    BINDINGS = [
        ("q,escape", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("a", "add_path", "Add Path"),
        ("r", "refresh", "Refresh"),
    ]

    def __init__(self, wrapper: Wrapper) -> None:
        super().__init__()
        self.wrapper = wrapper
        notification_manager.set_app(self)  # type: ignore

    def compose(self) -> ComposeResult:
        """Compose the simple UI."""
        yield Header()
        yield Static("🔧 Tamarin Path Manager", id="title")

        yield Static("📁 Current Tamarin Paths:", id="paths-header")

        with VerticalScroll(id="paths-list"):
            yield Static("Loading paths...", id="loading")

        yield Static("➕ Add New Path:", id="add-header")
        yield Input(placeholder="Enter path to tamarin-prover...", id="path-input")
        yield Button("Add Path", variant="primary", id="add-btn")

        yield Static("", id="status")

        with Container(id="buttons"):
            yield Button("Refresh", variant="default", id="refresh-btn")
            yield Button("Save & Exit", variant="success", id="save-btn")
            yield Button("Cancel", variant="error", id="cancel-btn")

        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the app."""
        await self.refresh_paths()

    async def refresh_paths(self) -> None:
        """Refresh the paths display."""
        notification_manager.info("🔄 Loading paths...")

        # Auto-detect paths
        await self.wrapper.auto_detect_tamarin_paths()

        # Get paths
        paths = self.wrapper.get_tamarin_paths()

        # Clear current list
        paths_list = self.query_one("#paths-list", VerticalScroll)
        await paths_list.remove_children()

        if not paths:
            await paths_list.mount(
                Static("❌ No Tamarin paths found", classes="no-paths")
            )
        else:
            for i, path in enumerate(paths, 1):
                # Create a simple text display for each path
                test_status = "✅ OK" if path.test_success else "❌ FAIL"
                version = path.version if path.version else "No version"

                path_info = f"{i}. {path.path}"
                await paths_list.mount(Static(path_info, classes="path-item"))

                test_info = f"   Test: {test_status} | Version: {version}"
                await paths_list.mount(Static(test_info, classes="path-details"))

                delete_btn = Button(
                    f"🗑 Delete Path {i}",
                    variant="error",
                    id=f"delete-{i}",
                    classes="delete-btn",
                )
                await paths_list.mount(delete_btn)

                # Add separator
                await paths_list.mount(Static("─" * 50, classes="separator"))

        notification_manager.info(f"📊 Loaded {len(paths)} path(s)")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "add-btn":
            self.add_path()
        elif event.button.id == "refresh-btn":
            asyncio.create_task(self.refresh_paths())
        elif event.button.id == "save-btn":
            self.save_and_exit()
        elif event.button.id == "cancel-btn":
            asyncio.create_task(self._cleanup_and_exit())
        elif event.button.id and event.button.id.startswith("delete-"):
            self.delete_path(event.button.id)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.input.id == "path-input":
            self.add_path()

    def add_path(self) -> None:
        """Add a new path."""
        path_input = self.query_one("#path-input", Input)
        path_str = path_input.value.strip()

        if not path_str:
            notification_manager.error("❌ Please enter a path")
            return

        asyncio.create_task(self.validate_and_add_path(path_str))

    async def validate_and_add_path(self, path_str: str) -> None:
        """Validate and add path."""
        notification_manager.info("⏳ Validating path...")

        try:
            path = Path(path_str)
            if not path.exists():
                notification_manager.error("❌ Path does not exist")
                return

            tamarin_path = await self.wrapper.add_tamarin_path(str(path))

            if not tamarin_path.version:
                notification_manager.error("❌ Not a valid tamarin-prover")
                return

            if tamarin_path.test_success:
                notification_manager.info(f"✅ Added: {tamarin_path.version}")
            else:
                notification_manager.warning(
                    f"⚠️ Added: {tamarin_path.version} (test failed)"
                )

            # Clear input and refresh
            path_input = self.query_one("#path-input", Input)
            path_input.value = ""
            await self.refresh_paths()

        except Exception as e:
            notification_manager.error(f"❌ Error: {str(e)}")

    def delete_path(self, button_id: str) -> None:
        """Delete a path."""
        try:
            index = int(button_id.split("-")[1]) - 1
            paths = self.wrapper.get_tamarin_paths()

            if 0 <= index < len(paths):
                path_to_remove = paths[index]
                if self.wrapper.remove_tamarin_path(str(path_to_remove.path)):
                    notification_manager.info(f"🗑 Removed: {path_to_remove.path}")
                    asyncio.create_task(self.refresh_paths())
                else:
                    notification_manager.error("❌ Failed to remove path")

        except (ValueError, IndexError):
            notification_manager.error("❌ Invalid path selection")

    def action_add_path(self) -> None:
        """Focus on add path input."""
        path_input = self.query_one("#path-input", Input)
        path_input.focus()

    def action_refresh(self) -> None:
        """Refresh paths."""
        asyncio.create_task(self.refresh_paths())

    async def action_quit(self) -> None:
        """Quit the application."""
        await self._cleanup_and_exit()

    def save_and_exit(self) -> None:
        """Save and exit."""
        notification_manager.info("💾 Saving configuration...")
        asyncio.create_task(self._cleanup_and_exit())

    async def _cleanup_and_exit(self) -> None:
        """Clean up and exit."""
        active_count = process_manager.get_active_processes_count()
        if active_count > 0:
            notification_manager.info(f"🛑 Stopping {active_count} process(es)...")
            await process_manager.kill_all_processes()

        self.exit()  # type: ignore
