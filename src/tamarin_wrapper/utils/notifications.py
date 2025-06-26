"""
Notification management system for the Tamarin wrapper.

This module provides a centralized way to send notifications via Rich formatting.
"""

from rich.console import Console
from rich.highlighter import RegexHighlighter
from rich.prompt import Prompt
from rich.theme import Theme

from ..model.executable_task import ExecutionSummary


class TamarinHighlighter(RegexHighlighter):
    """Custom highlighter for Tamarin wrapper output with rich formatting"""

    base_style = "tamarin."
    highlights = [
        # Section borders (═══════════...)
        r"(?P<border>═+)",
        # Component tags
        r"(?P<component>\[(?:TamarinTest|ConfigManager|TaskRunner|ProcessManager|ResourceManager|TaskManager|OutputManager)\])",
        # File paths
        r"(?P<filepath>[a-zA-Z0-9_\-./]+\.(?:json|txt|spthy))\b",
        # Resource allocation info
        r"(?P<allocated>Allocated:|Available resources:)",
        # Task completion messages
        r"(?P<task_success>Task completed successfully:)",
        r"(?P<task_failed>Task failed:)",
        r"(?P<task_timeout>Task timed out:)",
        r"(?P<task_memory_limit>Task exceeded memory limit:)",
    ]


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
                # Tamarin highlighter styles
                "tamarin.border": "dim #00aaaa",
                "tamarin.component": "bold magenta",
                "tamarin.filepath": "#005f7c",
                "tamarin.allocated": "bold blue",
                "tamarin.task_success": "#00aa00",
                "tamarin.task_failed": "#ff0000",
                "tamarin.task_timeout": "#ff8c00",
                "tamarin.task_memory_limit": "#8b008b",
            }
        )

        self._console = Console(theme=self._theme, highlighter=TamarinHighlighter())

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
                    f"[bold #ffffff on #000000][?][/bold #ffffff on #000000] {message} \\[y/n]",
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

    def task_execution_summary(self, summary: ExecutionSummary) -> None:
        """
        Display a comprehensive task execution summary using Rich formatting.

        Args:
            summary: ExecutionSummary with complete execution statistics
        """
        from rich.console import Group
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.table import Table

        # Import TaskStatus from the model - use relative import
        from ..model.executable_task import TaskStatus

        # Overview metrics table
        overview_table = Table(show_header=True, header_style="bold magenta")
        overview_table.add_column("Metric", style="cyan")
        overview_table.add_column("Value", justify="right")

        # Calculate additional metrics
        timeout_tasks = sum(
            1 for r in summary.task_results if r.status == TaskStatus.TIMEOUT
        )
        memory_limit_exceeded_tasks = sum(
            1
            for r in summary.task_results
            if r.status == TaskStatus.MEMORY_LIMIT_EXCEEDED
        )
        failed_tasks_other = (
            summary.failed_tasks - timeout_tasks - memory_limit_exceeded_tasks
        )
        avg_duration = (
            summary.total_duration / summary.total_tasks
            if summary.total_tasks > 0
            else 0
        )

        overview_table.add_row("Total Tasks", f"[bold]{summary.total_tasks}[/bold]")
        overview_table.add_row(
            "✅ Successful", f"[bold green]{summary.successful_tasks}[/bold green]"
        )
        overview_table.add_row(
            "❌ Failed", f"[bold red]{failed_tasks_other}[/bold red]"
        )
        overview_table.add_row(
            "⏱️ Timed Out", f"[bold #ff8c00]{timeout_tasks}[/bold #ff8c00]"
        )
        overview_table.add_row(
            "🧠 Memory Limit",
            f"[bold purple]{memory_limit_exceeded_tasks}[/bold purple]",
        )
        overview_table.add_row(
            "🕒 Total Duration", f"{self._format_duration(summary.total_duration)}"
        )
        overview_table.add_row("⚡ Avg Task Duration", f"{avg_duration:.1f}s")

        # Calculate memory statistics
        tasks_with_memory = [
            r for r in summary.task_results if r.memory_stats is not None
        ]
        if tasks_with_memory:
            # Extract peak memory values safely
            peak_memory_values = [
                r.memory_stats.peak_memory_mb
                for r in tasks_with_memory
                if r.memory_stats
            ]
            if peak_memory_values:
                total_peak_memory = sum(peak_memory_values)
                max_peak_memory = max(peak_memory_values)
                avg_peak_memory = sum(peak_memory_values) / len(peak_memory_values)

                overview_table.add_row(
                    "🧠 Total Peak Memory", f"{self._format_memory(total_peak_memory)}"
                )
                overview_table.add_row(
                    "🔥 Max Peak Memory", f"{self._format_memory(max_peak_memory)}"
                )
                overview_table.add_row(
                    "📊 Avg Peak Memory", f"{self._format_memory(avg_peak_memory)}"
                )

        # Task details table
        details_table = Table(
            title="Task Details", show_header=True, header_style="bold blue"
        )
        details_table.add_column("Task", style="cyan", no_wrap=True)
        details_table.add_column("Status", justify="center")
        details_table.add_column("Duration", justify="right")
        details_table.add_column("Peak Memory", justify="right")
        details_table.add_column("Avg Memory", justify="right")

        for result in summary.task_results:
            # Format status with color and icon
            if result.status == TaskStatus.COMPLETED:
                status_display = "[green]✅ PASS[/green]"
            elif result.status == TaskStatus.TIMEOUT:
                status_display = "[yellow]⏱️ TIMEOUT[/yellow]"
            elif result.status == TaskStatus.MEMORY_LIMIT_EXCEEDED:
                status_display = "[purple]🧠 MEMORY LIMIT[/purple]"
            else:
                status_display = "[red]❌ FAIL[/red]"

            # Format memory display
            peak_memory_display = (
                self._format_memory(result.memory_stats.peak_memory_mb)
                if result.memory_stats
                else "N/A"
            )

            avg_memory_display = (
                self._format_memory(result.memory_stats.avg_memory_mb)
                if result.memory_stats
                else "N/A"
            )

            details_table.add_row(
                result.task_id,
                status_display,
                f"{result.duration:.1f}s",
                peak_memory_display,
                avg_memory_display,
            )

        # Create components list
        from typing import Any, List

        components: List[Any] = [
            Panel(overview_table, title="Overview", border_style="blue"),
            details_table,
        ]

        # Add failed task details if any
        failed_results = [
            r
            for r in summary.task_results
            if r.status
            in [TaskStatus.FAILED, TaskStatus.TIMEOUT, TaskStatus.MEMORY_LIMIT_EXCEEDED]
        ]

        if failed_results:
            error_details = Markdown("**❌ Failed Tasks Details:**")
            components.append(error_details)

            for result in failed_results:
                if result.status == TaskStatus.TIMEOUT:
                    error_type = "Timeout"
                elif result.status == TaskStatus.MEMORY_LIMIT_EXCEEDED:
                    error_type = "Memory Limit Exceeded"
                else:
                    error_type = "Error"
                # Get the last line of stderr, prefix with ... if there are multiple lines
                if result.stderr:
                    stderr_lines = result.stderr.strip().splitlines()
                    if len(stderr_lines) > 1:
                        last_stderr = f"**sterr** : (...) {stderr_lines[-1]}"
                    else:
                        last_stderr = f"**stderr** : {stderr_lines[-1]}"
                else:
                    last_stderr = ""
                components.append(
                    Markdown(
                        f"  • **{result.task_id}** -- {error_type} (code:{result.return_code}) :"
                    )
                )
                components.append(Markdown(f"{last_stderr}"))

        # Single comprehensive output
        final_panel = Panel(
            Group(*components),
            title="📊 Task Execution Summary",
            border_style="blue",
            padding=(1, 2),
        )

        # Use single console print call as requested
        self._console.print("")  # spacing
        self._console.print(final_panel)

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f"{minutes}m {secs:.1f}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    def _format_memory(self, memory_mb: float) -> str:
        """
        Format memory usage in human-readable format.
        Automatically switches between MB and GB based on size.

        Args:
            memory_mb: Memory usage in megabytes

        Returns:
            Formatted memory string (e.g., "256 MB" or "1.5 GB")
        """
        if memory_mb < 1024:
            return f"{memory_mb:.1f} MB"
        else:
            memory_gb = memory_mb / 1024
            return f"{memory_gb:.1f} GB"


# Create a singleton instance that can be imported and used throughout the app
notification_manager = NotificationManager()
