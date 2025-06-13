"""
Notification management system for the Tamarin wrapper.

This module provides a centralized way to send notifications via Rich formatting.
"""

import typer


class NotificationManager:
    """
    Manages notifications for the Tamarin wrapper.
    This class handles sending notifications via Rich formatting
    """

    def __init__(self, debug_enabled: bool = False):
        self._debug_enabled = debug_enabled

    def notify(self, message: str, severity: str = "information"):
        """
        Send a notification that will be displayed in the TUI or console.

        Args:
            message: The notification message to display
            severity: The severity level ("information", "warning", "error", "debug")
        """
        # Define styling for different severity levels using Typer's style system
        if severity == "error":
            # Red styling for errors
            prefix = typer.style("[ERROR]", fg=typer.colors.RED, bold=True)
            message = typer.style(f"{message}", fg=typer.colors.BRIGHT_RED)
            styled_message = f"{prefix} {message}"
        elif severity == "warning":
            # Yellow/orange styling for warnings
            prefix = typer.style("[WARN]", fg=typer.colors.YELLOW, bold=True)
            message = typer.style(message, fg=typer.colors.BRIGHT_YELLOW)
            styled_message = f"{prefix} {message}"
        elif severity == "information":
            # Black styling for information
            prefix = typer.style("[INFO]", fg=typer.colors.RESET, bold=True)
            message = typer.style(message, fg=typer.colors.RESET)
            styled_message = f"{prefix} {message}"
        elif severity == "debug":
            if self._debug_enabled:
                # Gray/dim styling for debug
                prefix = typer.style("[DEBUG]", fg=typer.colors.BRIGHT_BLACK, bold=True)
                message = typer.style(message, fg=typer.colors.BRIGHT_BLACK)
                styled_message = f"{prefix} {message}"
            else:
                styled_message = None
        else:
            # Default styling
            prefix = typer.style("[INFO]", fg=typer.colors.RESET, bold=True)
            message = typer.style(message, fg=typer.colors.RESET)
            styled_message = f"{prefix} {message}"

        if styled_message:
            typer.echo(styled_message)

    def error(self, message: str):
        """
        Send an error notification.

        Args:
            message: The error message to display
        """
        self.notify(message, "error")

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


# Create a singleton instance that can be imported and used throughout the app
notification_manager = NotificationManager()
