"""
Notification management system for the Tamarin wrapper.

This module provides a centralized way to send notifications via Rich formatting.
"""

from rich.console import Console
from rich.prompt import Prompt
from rich.theme import Theme


class NotificationManager:
    """
    Manages notifications for the Tamarin wrapper.
    This class handles sending notifications via Rich formatting
    """

    def __init__(self, debug_enabled: bool = False):
        self._debug_enabled = debug_enabled

        # Create a Rich console with custom theme for notifications using truecolor
        self._theme = Theme(
            {
                "info": "bold blue",
                "success": "bold #00aa00",  # Bright green
                "warning": "bold #ff8c00",  # Dark orange
                "error": "bold #ff0000",  # Bright red
                "critical": "bold #ffffff on #8b0000",  # White on dark red
                "debug": "bold #888888",  # Dim gray (reduced opacity)
                "phase_separator": "bold #00aaaa",  # Cyan
            }
        )

        self._console = Console(theme=self._theme)

    def notify(self, message: str, severity: str = "information"):
        """
        Send a notification that will be displayed in the TUI or console.

        Args:
            message: The notification message to display
            severity: The severity level ("information", "warning", "error", "debug", "success", "critical")
        """
        # Map severity to Rich styled output with symbols and enhanced colors
        if severity == "error":
            self._console.print(f"[error][ERROR][/error] {message}")
        elif severity == "critical":
            self._console.print(f"[critical][CRITICAL][/critical] {message}")
        elif severity == "warning":
            self._console.print(f"[warning][WARN][/warning] {message}")
        elif severity == "success":
            self._console.print(f"[success][SUCCESS][/success] {message}")
        elif severity == "information":
            self._console.print(f"[info][INFO][/info] {message}")
        elif severity == "debug":
            if self._debug_enabled:
                self._console.print(f"[debug][DEBUG][/debug] {message}")
        else:
            # Default to information
            self._console.print(f"[info][INFO][/info] {message}")

    def error(self, message: str):
        """
        Send an error notification.

        Args:
            message: The error message to display
        """
        self.notify(message, "error")

    def critical(self, message: str):
        """
        Send a critical error notification that indicates a failure that stops execution.
        This will automatically exit the application with code 1.

        Args:
            message: The critical error message to display
        """
        self.notify(message, "critical")
        # Critical errors should stop execution immediately
        # Use sys.exit for more reliable termination in async contexts
        import sys

        sys.exit(1)

    def success(self, message: str):
        """
        Send a success notification for positive outcomes.

        Args:
            message: The success message to display
        """
        self.notify(message, "success")

    def info(self, message: str):
        """
        Send an information notification.

        Args:
            message: The information message to display
        """
        self.notify(message, "information")

    def warning(self, message: str):
        """
        Send a warning notification.

        Args:
            message: The warning message to display
        """
        self.notify(message, "warning")

    def debug(self, message: str):
        """
        Send a debug notification.

        Args:
            message: The debug message to display
        """
        self.notify(message, "debug")

    def phase_separator(self, phase_name: str):
        """
        Display a visual phase separator with the given phase name.

        Args:
            phase_name: The name of the phase to display
        """
        separator_line = "═" * 63
        phase_emoji = self._get_phase_emoji(phase_name)

        self._console.print()  # Empty line before
        self._console.print(f"[phase_separator]{separator_line}[/phase_separator]")
        self._console.print(
            f"[phase_separator]{phase_emoji} {phase_name.upper()}[/phase_separator]"
        )
        self._console.print(f"[phase_separator]{separator_line}[/phase_separator]")
        self._console.print()  # Empty line after

    def _get_phase_emoji(self, phase_name: str) -> str:
        """
        Get the appropriate emoji for a phase name.

        Args:
            phase_name: The name of the phase

        Returns:
            Emoji string for the phase
        """
        phase_emojis = {
            "configuration": "🔧",
            "tamarin integrity testing": "🧪",
            "task execution": "⚡",
            "summary": "📊",
        }
        return phase_emojis.get(phase_name.lower(), "🔄")

    def set_debug(self, enabled: bool):
        """
        Enable or disable debug output.

        Args:
            enabled: True to enable debug output, False to disable
        """
        self._debug_enabled = enabled

    def is_debug_enabled(self) -> bool:
        """
        Check if debug output is currently enabled.

        Returns:
            True if debug output is enabled, False otherwise
        """
        return self._debug_enabled

    def prompt_user(self, message: str, default: bool = True) -> bool:
        """
        Prompt the user with a yes/no question using Rich.

        Args:
            message: The message to display to the user
            default: Default answer if user just presses Enter (True for Yes, False for No)

        Returns:
            True if user wants to continue, False otherwise
        """
        try:
            return (
                Prompt.ask(
                    f"[bold #ffffff on #000000][?][/bold #ffffff on #000000] {message} {"\[Y/n]" if default else "\[y/N]"}",  # type: ignore
                    choices=["y", "n"],
                    default="y" if default else "n",
                    show_choices=False,
                )
                == "y"
            )
        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            self.warning("Operation cancelled by user")
            return default


# Create a singleton instance that can be imported and used throughout the app
notification_manager = NotificationManager()
