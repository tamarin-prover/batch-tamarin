"""
Notification management system for the Tamarin wrapper application.

This module provides a centralized way to send notifications throughout the application
without creating tight coupling between business logic and UI components.
"""


class NotificationManager:
    """
    Manages notifications for the application.

    This class acts as a bridge between business logic and the UI,
    allowing any part of the application to send notifications
    without directly depending on the Textual app instance.
    """

    def __init__(self):
        self._app_instance = None

    def set_app(self, app):
        """
        Set the Textual app instance that will handle notifications.

        Args:
            app: The Textual app instance
        """
        self._app_instance = app

    def notify(self, message: str, severity: str = "information"):
        """
        Send a notification that will be displayed in the TUI or console.

        Args:
            message: The notification message to display
            severity: The severity level ("information", "warning", "error")
        """
        if self._app_instance:
            self._app_instance.action_notify(message, severity=severity)
        else:
            # Fallback when no TUI is available (for testing/CLI usage)
            severity_prefix = {
                "information": "INFO",
                "warning": "WARN",
                "error": "ERROR",
            }.get(severity, "INFO")
            print(f"[{severity_prefix}] {message}")

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

    def clear_app(self):
        """
        Clear the app instance reference (useful for cleanup).
        """
        self._app_instance = None


# Create a singleton instance that can be imported and used throughout the app
notification_manager = NotificationManager()
