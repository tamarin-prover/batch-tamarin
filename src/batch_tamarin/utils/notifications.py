"""
Notification management system for the batch Tamarin.

This module provides a centralized way to send notifications via Rich formatting.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from rich.console import Console
from rich.highlighter import RegexHighlighter
from rich.prompt import Prompt
from rich.theme import Theme

from ..model.batch import Batch, LemmaResult
from ..model.tamarin_recipe import TamarinRecipe
from ..utils.system_resources import resolve_resource_value

if TYPE_CHECKING:
    from ..model.executable_task import ExecutableTask


class TamarinHighlighter(RegexHighlighter):
    """Custom highlighter for batch Tamarin output with rich formatting"""

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
    Manages notifications for the batch Tamarin.
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

    def task_execution_summary(self, batch: Batch) -> None:
        """
        Display a comprehensive batch execution summary using Rich formatting.

        Args:
            batch: Batch with complete execution results and metadata
        """
        if not batch.tasks:
            return

        from rich.columns import Columns
        from rich.console import Group
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.table import Table

        # Overview metrics table (matching HTML summary)
        overview_table = Table(show_header=True, header_style="bold magenta")
        overview_table.add_column("Metric", style="cyan")
        overview_table.add_column("Value", justify="right")

        # Calculate metrics from batch
        total_executions = batch.execution_metadata.total_tasks
        successful_executions = batch.execution_metadata.total_successes
        failed_executions = batch.execution_metadata.total_failures

        # Count timeout and memory limit tasks
        timeout_count = 0
        memory_limit_count = 0
        for task_name, rich_task in batch.tasks.items():
            for _subtask_name, rich_executable in rich_task.subtasks.items():
                if rich_executable.task_execution_metadata.status.value == "timeout":
                    timeout_count += 1
                elif (
                    rich_executable.task_execution_metadata.status.value
                    == "memory_limit_exceeded"
                ):
                    memory_limit_count += 1

        overview_table.add_row("Total Executions", f"[bold]{total_executions}[/bold]")
        overview_table.add_row(
            "Successful Executions",
            f"[bold #28a745]{successful_executions}[/bold #28a745]",
        )
        overview_table.add_row(
            "Failed Executions", f"[bold #ec1026]{failed_executions}[/bold #ec1026]"
        )
        overview_table.add_row(
            "Timed Out Executions", f"[bold #ea9400]{timeout_count}[/bold #ea9400]"
        )
        overview_table.add_row(
            "Task killed for memory limit",
            f"[bold #8b5cf6]{memory_limit_count}[/bold #8b5cf6]",
        )

        # Runtime table
        runtime_table = Table(show_header=True, header_style="bold cyan")
        runtime_table.add_column("Metric", style="cyan")
        runtime_table.add_column("Value", justify="right")

        runtime_table.add_row(
            "Total duration",
            f"{self._format_duration(batch.execution_metadata.total_runtime)}",
        )
        runtime_table.add_row(
            "Total peak memory used",
            f"{self._format_memory(batch.execution_metadata.total_memory)}",
        )
        runtime_table.add_row(
            "Max peak memory used",
            f"{self._format_memory(batch.execution_metadata.max_memory)}",
        )
        runtime_table.add_row(
            "Freshly executed tasks",
            f"{total_executions - batch.execution_metadata.total_cache_hit}",
        )
        runtime_table.add_row(
            "Cache hits",
            f"[bold #116dd7]{batch.execution_metadata.total_cache_hit}[/bold #116dd7]",
        )

        # Task details table (matching HTML structure)
        details_table = Table(show_header=True, header_style="bold blue")
        details_table.add_column("Task", style="cyan")
        details_table.add_column("Lemma", style="blue")
        details_table.add_column("Tamarin Version", style="white")
        details_table.add_column("Status", justify="center")
        details_table.add_column("Runtime", justify="right")
        details_table.add_column("Peak Memory", justify="right")
        details_table.add_column("Cache Hit", justify="center")

        # Track previous values for grouping (like HTML)
        prev_task_name = None
        prev_lemma_name = None

        # Convert tasks to list for easier iteration with lookahead
        tasks_list = list(batch.tasks.items())

        for task_idx, (task_name, rich_task) in enumerate(tasks_list):
            subtasks_list = list(rich_task.subtasks.items())

            for subtask_idx, (_subtask_name, rich_executable) in enumerate(
                subtasks_list
            ):
                # Format status based on lemma result for completed tasks
                if rich_executable.task_execution_metadata.status.value == "completed":
                    if rich_executable.task_result and hasattr(
                        rich_executable.task_result, "lemma_result"
                    ):
                        lemma_result = rich_executable.task_result.lemma_result  # type: ignore
                        if lemma_result == LemmaResult.VERIFIED:
                            status_display = "[#28a745]✅ Verified[/#28a745]"
                        elif lemma_result == LemmaResult.FALSIFIED:
                            status_display = "[#e600ff]❗ Falsified[/#e600ff]"
                        elif lemma_result == LemmaResult.UNTERMINATED:
                            status_display = "[#dbc100]🚧 Unterminated[/#dbc100]"
                        else:
                            status_display = "[#28a745]✅ Success[/#28a745]"
                    else:
                        status_display = "[#28a745]✅ Success[/#28a745]"
                elif rich_executable.task_execution_metadata.status.value == "timeout":
                    status_display = "[#ea9400]⏳ Timed Out[/#ea9400]"
                elif (
                    rich_executable.task_execution_metadata.status.value
                    == "memory_limit_exceeded"
                ):
                    status_display = "[#8b5cf6]🧠 Memory Limit[/#8b5cf6]"
                else:
                    status_display = "[#ec1026]❌ Failed[/#ec1026]"

                # Format other columns
                tamarin_alias = rich_executable.task_config.tamarin_alias
                tamarin_version_obj = batch.tamarin_versions.get(tamarin_alias)
                tamarin_version = (
                    tamarin_version_obj.version
                    if tamarin_version_obj and tamarin_version_obj.version
                    else "Unknown"
                )
                version_display = (
                    f"{tamarin_alias} ({tamarin_version})"
                    if tamarin_version != "Unknown"
                    else tamarin_alias
                )

                duration_display = self._format_duration(
                    rich_executable.task_execution_metadata.exec_duration_monotonic
                )
                memory_display = self._format_memory(
                    rich_executable.task_execution_metadata.peak_memory
                )

                cache_display = (
                    "[#116dd7]💾 Yes[/#116dd7]"
                    if rich_executable.task_execution_metadata.cache_hit
                    else "💻 No"
                )

                # Use -- for repeated task/lemma names (like HTML grouping)
                display_task_name = (
                    task_name + f"\n({rich_task.theory_file})"
                    if prev_task_name != task_name
                    else "--"
                )
                display_lemma_name = (
                    rich_executable.task_config.lemma
                    if prev_lemma_name != rich_executable.task_config.lemma
                    or subtask_idx == 0
                    else "--"
                )

                # Determine if we need separator after this row
                end_section = False

                # Check if this is the last subtask of the current task
                is_last_subtask_in_task = subtask_idx == len(subtasks_list) - 1
                # Check if this is the last task overall
                is_last_task = task_idx == len(tasks_list) - 1

                if is_last_subtask_in_task and not is_last_task:
                    # End of task - add double separator by adding section twice
                    end_section = True

                details_table.add_row(
                    display_task_name,
                    display_lemma_name,
                    version_display,
                    status_display,
                    duration_display,
                    memory_display,
                    cache_display,
                    end_section=end_section,
                )

                # Add double separator for task changes (after the end_section=True row)
                if is_last_subtask_in_task and not is_last_task:
                    details_table.add_section()  # This adds the second separator line

                # Update previous values
                prev_task_name = task_name
                prev_lemma_name = rich_executable.task_config.lemma

        # Settings section (matching HTML structure)
        config_table = Table(show_header=True, header_style="bold magenta")
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", justify="right")

        config_table.add_row("Max cores", str(batch.config.global_max_cores))
        config_table.add_row("Max memory", f"{batch.config.global_max_memory:.0f}GB")
        config_table.add_row("Default timeout", f"{batch.config.default_timeout}s")

        # Tamarin versions table
        versions_table = Table(show_header=True, header_style="bold cyan")
        versions_table.add_column("Alias", style="cyan")
        versions_table.add_column("Path", style="white")
        versions_table.add_column("Version", style="green")

        for alias, version_info in batch.tamarin_versions.items():
            versions_table.add_row(
                alias, version_info.path, version_info.version or "Unknown"
            )

        # Settings panel
        settings_panel = Panel(
            Columns([config_table, versions_table]),
            title="⚙️ Configuration",
            border_style="blue",
        )

        # Execution details panel
        execution_panel = Panel(
            Group(Columns([overview_table, runtime_table]), details_table),
            title="⚡ Execution",
            border_style="blue",
        )

        # Collect components

        components: list[Panel | str] = [settings_panel, execution_panel]

        # Error report section (matching HTML structure)
        from typing import Any

        failed_tasks: List[Dict[str, Any]] = []
        timeout_tasks: List[Dict[str, Any]] = []
        memory_limit_tasks: List[Dict[str, Any]] = []

        for task_name, rich_task in batch.tasks.items():
            for _subtask_name, rich_executable in rich_task.subtasks.items():
                task_info: Dict[str, Any] = {
                    "task_name": task_name,
                    "rich_executable": rich_executable,
                }

                if rich_executable.task_execution_metadata.status.value == "failed":
                    failed_tasks.append(task_info)
                elif rich_executable.task_execution_metadata.status.value == "timeout":
                    timeout_tasks.append(task_info)
                elif (
                    rich_executable.task_execution_metadata.status.value
                    == "memory_limit_exceeded"
                ):
                    memory_limit_tasks.append(task_info)

        if failed_tasks or timeout_tasks or memory_limit_tasks:

            error_components: list[Markdown] = []

            # Process all error tasks together with separators
            all_errors: list[str] = []

            # Failed tasks
            for task in failed_tasks:
                exec: Any = task["rich_executable"]
                tamarin_version_obj = batch.tamarin_versions.get(
                    exec.task_config.tamarin_alias
                )
                version = (
                    tamarin_version_obj.version
                    if tamarin_version_obj and tamarin_version_obj.version
                    else "Unknown"
                )

                error_text = f"**❌ FAILED:** Task: {task['task_name']}, "
                error_text += f"on lemma: {exec.task_config.lemma}, with tamarin-prover: {exec.task_config.tamarin_alias} ({version})\n\n"

                if (
                    exec.task_result
                    and hasattr(exec.task_result, "last_stderr_lines")
                    and exec.task_result.last_stderr_lines
                ):
                    stderr_content = "\n".join(exec.task_result.last_stderr_lines)
                    error_text += f"\n\n```zsh\n{stderr_content}\n```"

                all_errors.append(error_text)

            # Timeout tasks
            for task in timeout_tasks:
                exec = task["rich_executable"]
                tamarin_version_obj = batch.tamarin_versions.get(
                    exec.task_config.tamarin_alias
                )
                version = (
                    tamarin_version_obj.version
                    if tamarin_version_obj and tamarin_version_obj.version
                    else "Unknown"
                )

                error_text = f"**⏳ TIMED OUT:** Task: {task['task_name']}, "
                error_text += f"on lemma: {exec.task_config.lemma}, with tamarin-prover: {exec.task_config.tamarin_alias} ({version})\n\n"

                all_errors.append(error_text)

            # Memory limit tasks
            for task in memory_limit_tasks:
                exec = task["rich_executable"]
                tamarin_version_obj = batch.tamarin_versions.get(
                    exec.task_config.tamarin_alias
                )
                version = (
                    tamarin_version_obj.version
                    if tamarin_version_obj and tamarin_version_obj.version
                    else "Unknown"
                )

                error_text = f"**🧠 MEMORY LIMIT:** Task: {task['task_name']}, "
                error_text += f"on lemma: {exec.task_config.lemma}, with tamarin-prover: {exec.task_config.tamarin_alias} ({version})\n\n"

                all_errors.append(error_text)

            # Join all errors with separators
            if all_errors:
                full_error_text = "\n---\n\n".join(all_errors)
                error_components.append(Markdown(full_error_text))
                rerun_file = (
                    Path(batch.config.output_directory).absolute()
                    / f"{batch.recipe.split('.')[0]}-rerun.json"
                )
                error_components.append(
                    Markdown(
                        f"\n\n\n---\n\n"
                        f"\n\nℹ️  You can rerun failed tasks using the generated file: "
                        f"[{rerun_file}]({rerun_file})"
                    )
                )

            # Create error panel with red border
            error_panel = Panel(
                Group(*error_components),
                title="🚨 Errors",
                border_style="red",
            )
            components.append(error_panel)

        # Build a proper file URI (with three slashes) so terminals recognize it as a local link
        html_file = Path(batch.config.output_directory).absolute() / "summary.html"
        file_uri = html_file.as_uri()

        details_text = (
            f"\nFor more details, see the HTML summary: "
            f"[blue][link={file_uri}]{html_file}[/link][/blue]"
        )
        components.append(details_text)

        # Final panel with all components
        final_panel = Panel(
            Group(*components),
            title="📊 Task Execution Summary",
            border_style="blue",
            padding=(1, 2),
        )

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

    def _format_bytes(self, size_bytes: int) -> str:
        """
        Format bytes in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted size string (e.g., "256 bytes", "1.5 kB", "2.0 MB", "1.2 GB")
        """
        if size_bytes == 0:
            return "0 bytes"

        volume = float(size_bytes)
        unit = "bytes"
        for unit in ["bytes", "kB", "MB", "GB"]:
            if volume < 1024 or unit == "GB":
                break
            volume /= 1024

        if unit == "bytes":
            return f"{int(volume)} {unit}"
        else:
            return f"{volume:.1f} {unit}"

    def check_report(
        self,
        recipe: TamarinRecipe,
        executable_tasks: List["ExecutableTask"],
        tamarin_errors: Optional[Dict[str, List[str]]] = None,
    ):
        """
        Display a comprehensive check report for executable tasks.

        Args:
            executable_tasks: List of ExecutableTask objects
            tamarin_errors: Optional dict of tamarin validation errors/warnings
        """
        from typing import Any

        from rich.columns import Columns
        from rich.console import Group
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.table import Table

        # Summary table
        summary_table = Table(show_header=True, header_style="bold magenta")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", justify="right")

        # Count tasks by version and type
        task_count = len(executable_tasks)
        version_counts: dict[str, int] = {}
        lemma_counts: dict[str, int] = {}

        for task in executable_tasks:
            version_counts[task.tamarin_version_name] = (
                version_counts.get(task.tamarin_version_name, 0) + 1
            )
            if task.lemma:
                lemma_counts[task.lemma] = lemma_counts.get(task.lemma, 0) + 1

        summary_table.add_row("Total Tasks", f"[bold]{task_count}[/bold]")
        summary_table.add_row(
            "Tamarin Versions", f"[bold blue]{len(version_counts)}[/bold blue]"
        )
        summary_table.add_row(
            "Global Max Cores",
            f"[bold #db9200]{resolve_resource_value(recipe.config.global_max_cores, 'cores')}[/bold #db9200]",
        )
        summary_table.add_row(
            "Global Max Memory",
            f"[bold violet]{resolve_resource_value(recipe.config.global_max_memory, 'memory')}GB[/bold violet]",
        )

        # Task details table
        details_table = Table(show_header=True, header_style="bold blue")
        details_table.add_column("Task", style="cyan")
        details_table.add_column("Lemma", style="blue")
        details_table.add_column("Tamarin Version", style="green")
        details_table.add_column("Cores", justify="right", style="#db9200")
        details_table.add_column("Memory", justify="right", style="violet")
        details_table.add_column("Timeout", justify="right")
        details_table.add_column("Options", style="yellow")
        details_table.add_column("Preprocessor flags", style="magenta")

        # Group tasks by original task name and lemma for proper formatting
        from collections import defaultdict

        from ..model.executable_task import ExecutableTask

        tasks_by_name: dict[str, list[ExecutableTask]] = {}
        for task in executable_tasks:
            if task.original_task_name not in tasks_by_name:
                tasks_by_name[task.original_task_name] = []
            tasks_by_name[task.original_task_name].append(task)

        prev_task_name: Optional[str] = None
        task_groups = list(tasks_by_name.items())

        for task_idx, (task_name, task_list) in enumerate(task_groups):
            # Group tasks by lemma within each task
            lemma_groups: dict[str, list[ExecutableTask]] = defaultdict(list)
            for task in task_list:
                lemma_key = task.lemma if task.lemma else "None"
                lemma_groups[lemma_key].append(task)

            lemma_items = list(lemma_groups.items())
            for lemma_idx, (lemma_name, lemma_tasks) in enumerate(lemma_items):
                # Format task name with theory file (same as execution summary)
                display_task_name = (
                    task_name + f"\n({lemma_tasks[0].theory_file})"
                    if prev_task_name != task_name
                    else "--"
                )

                # Display lemma name
                lemma_display = lemma_name

                # Collect all Tamarin version aliases for this lemma (comma-separated)
                version_aliases = [task.tamarin_version_name for task in lemma_tasks]
                version_display = ", ".join(version_aliases)

                # Use first task's config for resource values (they should be the same for same lemma)
                first_task = lemma_tasks[0]
                cores_display = f"{first_task.max_cores}c"
                memory_display = f"{first_task.max_memory}GB"
                timeout_display = f"{first_task.task_timeout}s"

                # Format options (display "None" if empty)
                options_display = (
                    ", ".join(first_task.tamarin_options)
                    if first_task.tamarin_options
                    else "None"
                )

                # Format preprocessor flags (display "None" if empty)
                preprocessor_display = (
                    ", ".join(first_task.preprocess_flags)
                    if first_task.preprocess_flags
                    else "None"
                )

                # Determine if we need separator after this row
                end_section = False

                # Check if this is the last lemma of the current task
                is_last_lemma_in_task = lemma_idx == len(lemma_items) - 1
                # Check if this is the last task overall
                is_last_task = task_idx == len(task_groups) - 1

                if is_last_lemma_in_task and not is_last_task:
                    # End of task - add separator
                    end_section = True

                details_table.add_row(
                    display_task_name,
                    lemma_display,
                    version_display,
                    cores_display,
                    memory_display,
                    timeout_display,
                    options_display,
                    preprocessor_display,
                    end_section=end_section,
                )

                # Add double separator for task changes (after the end_section=True row)
                if is_last_lemma_in_task and not is_last_task:
                    details_table.add_section()  # This adds the second separator line

                # Update previous values
                prev_task_name = task_name

        # Tamarin path panel
        tamarin_path: list[Markdown] = []
        binary_count = len(recipe.tamarin_versions)
        header_text = (
            "**📂 Tamarin binary path :**"
            if binary_count == 1
            else "**📂 Tamarin binaries paths :**"
        )
        tamarin_path.append(Markdown(header_text))
        for alias, version in recipe.tamarin_versions.items():
            tamarin_path.append(Markdown(f"**- Alias : '{alias}'** → {version.path}"))

        # Version breakdown table
        version_table = Table(show_header=True, header_style="bold yellow")
        version_table.add_column("Alias", style="yellow")
        version_table.add_column("Tasks", justify="right", style="bold")
        version_table.add_column("Reported version", justify="right")
        version_table.add_column("Integrity test", justify="right")

        seen_versions: set[str] = set()
        for task in executable_tasks:
            if task.tamarin_version_name not in seen_versions:
                seen_versions.add(task.tamarin_version_name)
                tamarin_version_obj = recipe.tamarin_versions.get(
                    task.tamarin_version_name
                )
                version_display = (
                    tamarin_version_obj.version if tamarin_version_obj else "N/A"
                )
                test_success = (
                    tamarin_version_obj.test_success if tamarin_version_obj else False
                )

                version_table.add_row(
                    task.tamarin_version_name,
                    str(version_counts[task.tamarin_version_name]),
                    version_display,
                    "✅" if test_success else "❌",
                )

        # Create components list
        # Combine summary and version tables side by side
        overview_panel = Panel(
            Columns([summary_table, version_table]),
            title="Overview",
            border_style="blue",
        )

        task_panel = Panel(details_table, title="Task Details", border_style="blue")

        components: List[Any] = [
            Group(*tamarin_path),
            overview_panel,
            task_panel,
        ]

        # Add tamarin validation errors if present
        if tamarin_errors:
            error_components: list[Markdown] = []
            for version, errors in tamarin_errors.items():
                if errors:
                    error_components.append(Markdown(f"**- ⚠️ Task :** *{version}*"))
                    for error in errors:
                        error_components.append(Markdown(f"{error}"))

            if error_components:
                components.append(
                    Panel(
                        Group(*error_components),
                        title="🧪 Tamarin Validation Issues",
                        border_style="red",
                    )
                )

        # Final panel
        final_panel = Panel(
            Group(*components),
            title="🔍 Configuration Check Report",
            border_style="blue",
            padding=(1, 2),
        )

        self._console.print("")  # spacing
        self._console.print(final_panel)


# Create a singleton instance that can be imported and used throughout the app
notification_manager = NotificationManager()
