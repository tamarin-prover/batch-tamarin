from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from model.wrapper import Wrapper


class CurrentTamarinPath(Widget):
    CSS_PATH = str(Path(__file__).parent / "style/current_tamarin_path.css")

    def __init__(self, wrapper: Wrapper, **kwargs) -> None:  # type: ignore
        super().__init__(**kwargs)  # type: ignore
        self.wrapper = wrapper

    def compose(self) -> ComposeResult:
        """Compose the current Tamarin path viewer widget."""
        yield Static("Current Tamarin Paths", classes="path-viewer-title")

        with Vertical(classes="path-container"):
            tamarin_paths = self.wrapper.get_tamarin_paths()

            if not tamarin_paths:
                yield Static("No Tamarin paths found", classes="no-paths")
            else:
                for _, tamarin_path in enumerate(tamarin_paths):
                    # Determine status icon
                    if not tamarin_path.version:
                        status_icon = "❓"
                        status_text = "Unknown"
                    elif tamarin_path.test_success:
                        status_icon = "✅"
                        status_text = "Valid"
                    else:
                        status_icon = "❌"
                        status_text = "Failed"

                    # Format version info
                    version_info = (
                        f"v{tamarin_path.version}"
                        if tamarin_path.version
                        else "No version"
                    )

                    # Create a single line with all information
                    path_info = f"{status_icon} {tamarin_path.path} ({version_info}) - {status_text}"
                    yield Static(path_info, classes="path-entry")

    async def refresh_paths(self):
        """Refresh the display when paths are updated."""
        await self.recompose()
