"""
Notification management system for the Tamarin wrapper application.

This module provides a centralized way to send notifications throughout the application
without creating tight coupling between business logic and UI components.
"""

import re

from textual.app import App


def _sanitize_message(message: str) -> str:
    """
    Sanitize a message to prevent control characters from crashing the UI.

    This function removes or replaces potentially problematic characters
    that could be interpreted as control sequences by the terminal/UI.

    Args:
        message: The raw message string

    Returns:
        A sanitized version of the message safe for display
    """
    # Remove ANSI escape sequences
    message = re.sub(r"\x1b\[[0-9;]*m", "", message)

    # Replace other problematic control characters
    message = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", message)

    # Replace shell variable references that look like control sequences
    message = re.sub(r"@@[A-Z_]+@", "[VARIABLE]", message)

    # Replace any remaining @ sequences that might be interpreted as markup
    message = message.replace("@@", "@")

    # Escape square brackets that can be interpreted as markup
    message = message.replace("[", "(").replace("]", ")")

    # Remove any other characters that could cause markup parsing issues
    message = re.sub(r"[<>{}]", "", message)

    # Replace multiple spaces/tabs with single space for cleaner display
    message = re.sub(r"\s+", " ", message)

    # Limit message length to prevent overwhelming the UI
    if len(message) > 1000:
        message = message[:997] + "..."

    return message.strip()


class NotificationManager:
    """
    Manages notifications for the application.

    This class acts as a bridge between business logic and the UI,
    allowing any part of the application to send notifications
    without directly depending on the Textual app instance.
    """

    def __init__(self, debug_enabled: bool = False):
        self._app_instance = None
        self._debug_enabled = debug_enabled

    def set_app(self, app: App) -> None:  # type: ignore
        """
        Set the Textual app instance that will handle notifications.

        Args:
            app: The Textual app instance
        """
        self._app_instance = app  # type: ignore

    def notify(self, message: str, severity: str = "information"):
        """
        Send a notification that will be displayed in the TUI or console.

        Args:
            message: The notification message to display
            severity: The severity level ("information", "warning", "error")
        """
        # Sanitize the message to prevent UI crashes from control characters
        sanitized_message = _sanitize_message(message)

        if self._app_instance:  # type: ignore
            if severity == "debug":
                # Debug messages are not sent to the TUI, but can be logged if debug is enabled
                if self._debug_enabled:
                    print(f"[DEBUG] {sanitized_message}")
                return
            self._app_instance.action_notify(sanitized_message, severity=severity)  # type: ignore
        else:
            # Fallback when no TUI is available (for testing/CLI usage)
            severity_prefix = {
                "information": "INFO",
                "warning": "WARN",
                "error": "ERROR",
                "debug": "DEBUG",
            }.get(severity, "INFO")

            # Only print debug messages if debug is enabled
            if severity == "debug" and not self._debug_enabled:
                return

            print(f"[{severity_prefix}] {sanitized_message}")

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

    def clear_app(self):
        """
        Clear the app instance reference (useful for cleanup).
        """
        self._app_instance = None


# Create a singleton instance that can be imported and used throughout the app
notification_manager = NotificationManager()
