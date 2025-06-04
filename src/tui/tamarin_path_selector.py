"""Tamarin Path Selector - Terminal UI for selecting and managing Tamarin paths."""

from pathlib import Path
from typing import List, Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

from .config import ConfigManager


class TamarinPathSelector(App):
    """A terminal UI for selecting and managing Tamarin paths."""

    CSS_PATH = str(Path(__file__).parent / "styles.css")

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("a", "add_path", "Add Path"),
        ("d", "delete_path", "Delete Path"),
        ("enter", "select_path", "Select Path"),
    ]

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.selected_path: Optional[str] = None
        self.paths: List[str] = []

    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Header()
        yield Static("Tamarin Path Selector", classes="title")

        with Container(classes="main-container"):
            with Vertical(classes="left-panel"):
                yield Label("Current Tamarin Paths:", classes="section-title")
                yield ListView(id="path_list")
                yield Label("Use ↑↓ to navigate, Enter to select", classes="help-text")

            with Vertical(classes="right-panel"):
                yield Label("Manage Paths:", classes="section-title")

                with Container(classes="input-section"):
                    yield Label("Add New Path:")
                    yield Input(
                        placeholder="Enter path to Tamarin executable...",
                        id="path_input",
                    )

                with Horizontal(classes="button-row"):
                    yield Button("Add Path", id="add_btn", variant="primary")
                    yield Button("Delete Selected", id="delete_btn", variant="error")
                    yield Button("Select & Exit", id="select_btn", variant="success")

                with Container(classes="input-section"):
                    yield Button(
                        "Auto-Detect Paths", id="detect_btn", variant="default"
                    )

        yield Footer()

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        self.load_config()
        self.update_path_list()

    def load_config(self) -> None:
        """Load configuration from file."""
        self.config_manager.load_config()
        self.paths = self.config_manager.get_tamarin_paths()
        self.selected_path = self.config_manager.get_selected_path()

    def save_config(self) -> None:
        """Save configuration to file."""
        if self.selected_path:
            self.config_manager.set_selected_path(self.selected_path)

    def update_path_list(self) -> None:
        """Update the path list widget."""
        path_list = self.query_one("#path_list", ListView)
        path_list.clear()

        current_selected = self.config_manager.get_selected_path()

        for path in self.paths:
            # Check if path exists and mark it
            is_valid = self.config_manager.validate_path(path)
            status = "✓" if is_valid else "✗"

            # Mark currently selected path
            prefix = "→ " if path == current_selected else "  "

            item_text = f"{prefix}{status} {path}"

            # Create label with appropriate styling
            label = Label(item_text)
            if is_valid:
                label.add_class("valid-path")
            else:
                label.add_class("invalid-path")

            if path == current_selected:
                label.add_class("selected-indicator")

            path_list.append(ListItem(label))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "add_btn":
            self.action_add_path()
        elif event.button.id == "delete_btn":
            self.action_delete_path()
        elif event.button.id == "select_btn":
            self.action_select_path()
        elif event.button.id == "detect_btn":
            self.action_detect_paths()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.input.id == "path_input":
            self.action_add_path()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle list selection."""
        if event.list_view.id == "path_list" and event.item:
            # Extract the path from the label (remove prefix and status indicator)
            label_text = event.item.children[0].renderable
            if isinstance(label_text, str):
                # Remove the prefix (→ or spaces), status indicator (✓ or ✗) and spaces
                path = label_text[4:] if len(label_text) > 4 else label_text
                self.selected_path = path

    def action_add_path(self) -> None:
        """Add a new path."""
        path_input = self.query_one("#path_input", Input)
        new_path = path_input.value.strip()

        if new_path:
            if self.config_manager.add_tamarin_path(new_path):
                self.paths = self.config_manager.get_tamarin_paths()
                self.update_path_list()
                path_input.value = ""

                # Check if path is valid
                if self.config_manager.validate_path(new_path):
                    self.notify(f"Added valid path: {new_path}")
                else:
                    self.notify(
                        f"Added path (not found): {new_path}", severity="warning"
                    )
            else:
                self.notify("Path already exists!", severity="warning")
        else:
            self.notify("Please enter a path!", severity="error")

    def action_delete_path(self) -> None:
        """Delete the selected path."""
        if self.selected_path:
            if self.config_manager.remove_tamarin_path(self.selected_path):
                self.paths = self.config_manager.get_tamarin_paths()
                self.update_path_list()
                self.notify(f"Deleted path: {self.selected_path}")
                self.selected_path = None
            else:
                self.notify("Failed to delete path!", severity="error")
        else:
            self.notify("No path selected for deletion!", severity="warning")

    def action_select_path(self) -> None:
        """Select the current path and exit."""
        if self.selected_path:
            self.config_manager.set_selected_path(self.selected_path)
            self.notify(f"Selected path: {self.selected_path}")
            self.exit(self.selected_path)
        else:
            self.notify("No path selected!", severity="warning")

    def action_detect_paths(self) -> None:
        """Auto-detect Tamarin paths."""
        detected_paths = self.config_manager.auto_detect_tamarin_paths()

        if not detected_paths:
            self.notify("No Tamarin installations detected.", severity="warning")
            return

        added_count = 0
        for path in detected_paths:
            if self.config_manager.add_tamarin_path(path):
                added_count += 1

        if added_count > 0:
            self.paths = self.config_manager.get_tamarin_paths()
            self.update_path_list()
            self.notify(f"Auto-detected and added {added_count} new path(s)!")
        else:
            self.notify(
                "All detected paths were already configured.", severity="information"
            )


def run_tamarin_path_selector() -> Optional[str]:
    """Run the Tamarin path selector and return the selected path."""
    app = TamarinPathSelector()
    return app.run()


if __name__ == "__main__":
    selected = run_tamarin_path_selector()
    if selected:
        print(f"Selected Tamarin path: {selected}")
    else:
        print("No path selected.")
