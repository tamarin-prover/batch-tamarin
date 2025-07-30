"""
Report generator service for creating comprehensive execution reports.

This module provides the main service for generating reports from execution
results using Jinja2 templates and various output formats.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..model.report_data import ReportData
from ..utils.notifications import notification_manager
from .report_charts import ChartCollection


class ReportGenerator:
    """Service for generating comprehensive execution reports."""

    def __init__(self, template_dir: Optional[Path] = None):
        """
        Initialize the report generator.

        Args:
            template_dir: Directory containing Jinja2 templates. If None, uses default.
        """
        if template_dir is None:
            # Default to templates directory in the package
            template_dir = Path(__file__).parent.parent / "templates"

        self.template_dir = template_dir
        # Create standard environment for HTML/MD templates
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Create LaTeX-specific environment with custom delimiters
        self.latex_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            block_start_string="\\JBLOCK{",
            block_end_string="}",
            variable_start_string="\\VAR{",
            variable_end_string="}",
            comment_start_string="\\#{",
            comment_end_string="}",
            line_statement_prefix="%%",
            line_comment_prefix="%#",
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters to both environments
        filters: Dict[str, Callable[[Any], str]] = self.env.filters  # type: ignore
        filters["latex_escape"] = self._latex_escape
        filters["filter_traces_by_task"] = self._filter_traces_by_task  # type: ignore
        filters["relative_from_report"] = self._relative_from_report  # type: ignore
        filters["hyphenate"] = self._hyphenate  # type: ignore

        latex_filters: Dict[str, Callable[[Any], str]] = self.latex_env.filters  # type: ignore
        latex_filters["latex_escape"] = self._latex_escape
        latex_filters["filter_traces_by_task"] = self._filter_traces_by_task  # type: ignore
        latex_filters["relative_from_report"] = self._relative_from_report  # type: ignore
        latex_filters["hyphenate"] = self._hyphenate  # type: ignore

    def _latex_escape(self, text: str) -> str:
        """Escape special LaTeX characters."""
        text = str(text)

        # LaTeX special characters that need escaping
        latex_chars = {
            "\\": r"\textbackslash{}",
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "^": r"\textasciicircum{}",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "~": r"\textasciitilde{}",
        }

        # Process character by character to avoid double-escaping
        result: List[str] = []
        for char in text:
            if char in latex_chars:
                result.append(latex_chars[char])
            else:
                result.append(char)

        return "".join(result)

    def _hyphenate(self, text: str, max_length: int = 20) -> str:
        """
        Add hyphens to break long strings at the specified character limit.

        Args:
            text: The text to potentially hyphenate
            max_length: Maximum length before adding hyphen (default: 20)

        Returns:
            String with hyphens added if it exceeds max_length
        """
        text = str(text)

        if len(text) <= max_length:
            return text

        # Add hyphen every max_length characters
        result: List[str] = []
        for i in range(0, len(text), max_length):
            chunk = text[i : i + max_length]
            result.append(chunk)

        return "-".join(result)

    def _relative_from_report(self, file_path: str) -> str:
        """Convert absolute file path to relative path from report output location."""
        if not file_path or not hasattr(self, "_current_output_path"):
            return file_path

        try:
            abs_file_path = str(Path(file_path).absolute())
            abs_output_dir = str(Path(self._current_output_path).parent.absolute())

            # Calculate relative path from report output directory to file
            relative_path = os.path.relpath(abs_file_path, abs_output_dir)

            # Convert to forward slashes for web compatibility
            return relative_path.replace("\\", "/")
        except (ValueError, OSError):
            # If we can't make it relative, return the original path
            return file_path

    def _filter_traces_by_task(self, traces: List[Any], task: Any) -> List[Any]:
        """Filter traces by task's lemmas and output_prefix."""
        if not traces or not task:
            return []

        # Get task's lemmas
        task_lemmas = (  # type: ignore
            set(task.lemmas) if hasattr(task, "lemmas") else set()
        )

        # Filter traces by lemma first
        lemma_filtered_traces = [
            trace
            for trace in traces
            if hasattr(trace, "lemma") and trace.lemma in task_lemmas
        ]

        # Filter by output_prefix if available
        if (
            hasattr(task, "output_prefix")
            and task.output_prefix
            and lemma_filtered_traces
        ):
            # Check if any traces have output_prefix information
            traces_with_prefix = [
                trace
                for trace in lemma_filtered_traces
                if hasattr(trace, "output_prefix") and trace.output_prefix
            ]

            if traces_with_prefix:
                # Filter traces where output_prefix matches the task's output_prefix
                prefix_filtered_traces = [
                    trace
                    for trace in traces_with_prefix
                    if trace.output_prefix == task.output_prefix
                ]

                # If we found matches with prefix filtering, return those
                if prefix_filtered_traces:
                    return prefix_filtered_traces

        # If no output_prefix filtering was possible or successful, return lemma-filtered traces
        return lemma_filtered_traces

    def generate_report(
        self,
        results_directory: Path,
        output_path: Path,
        format_type: str,
        version: Optional[str] = None,
    ) -> None:
        """
        Generate a comprehensive report from execution results.

        Args:
            results_directory: Directory containing execution results
            output_path: Output file path
            format_type: Output format (md, html, tex, typ)
            version: Version string for the report footer
        """
        # Store output path for relative path filter
        self._current_output_path = str(output_path.absolute())

        # Load execution report
        execution_report_path = results_directory / "execution_report.json"
        if not execution_report_path.exists():
            raise FileNotFoundError(
                f"execution_report.json not found in {results_directory}"
            )

        notification_manager.info(
            f"Loading execution report from {execution_report_path}"
        )

        # Create report data
        report_data = ReportData.from_execution_report(
            execution_report_path, results_directory, format_type
        )

        # Generate charts
        charts = self._generate_charts(report_data)

        # Prepare template context
        context = self._prepare_template_context(
            report_data, charts, results_directory, version
        )

        # Render template using appropriate environment
        template_name = f"report.{format_type}.j2"
        try:
            # Use LaTeX environment for .tex format
            if format_type == "tex":
                template = self.latex_env.get_template(template_name)
            else:
                template = self.env.get_template(template_name)
        except Exception as e:
            raise ValueError(f"Template {template_name} not found or invalid: {e}")

        notification_manager.info(f"Rendering {format_type} template")
        rendered_content = template.render(**context)

        # Write output
        output_path.write_text(rendered_content, encoding="utf-8")
        notification_manager.success(f"Report generated successfully: {output_path}")

    def _generate_charts(self, report_data: ReportData) -> ChartCollection:
        """Generate charts from report data."""
        charts = ChartCollection()

        # Success rate chart
        charts.set_success_rate(
            report_data.statistics.successful_tasks, report_data.statistics.failed_tasks
        )

        # Cache hit rate chart
        cache_misses = (
            report_data.statistics.total_lemmas - report_data.statistics.cache_hits
        )
        charts.set_cache_hit_rate(report_data.statistics.cache_hits, cache_misses)

        # Runtime per task chart
        task_runtimes: Dict[str, float] = {}
        for task in report_data.tasks:
            if task.results:
                avg_runtime = sum(result.runtime for result in task.results) / len(
                    task.results
                )
                task_runtimes[task.name] = avg_runtime
        charts.set_runtime_per_task(task_runtimes)

        # Memory per task chart
        task_memory: Dict[str, float] = {}
        for task in report_data.tasks:
            if task.results:
                avg_memory = sum(result.peak_memory for result in task.results) / len(
                    task.results
                )
                task_memory[task.name] = avg_memory
        charts.set_memory_per_task(task_memory)

        # Execution timeline chart
        timeline_data: List[tuple[str, datetime, datetime]] = []
        base_time = datetime.now()  # Use a base time for relative positioning
        current_offset = 0

        for task in report_data.tasks:
            if task.results:
                # Calculate task duration from results
                total_runtime = sum(result.runtime for result in task.results)
                start_time = base_time + timedelta(seconds=current_offset)
                end_time = start_time + timedelta(seconds=total_runtime)
                timeline_data.append((task.name, start_time, end_time))
                current_offset += total_runtime

        charts.set_execution_timeline(timeline_data)

        # Error types chart (only if there are errors)
        error_types: Dict[str, Union[int, float]] = {}
        if report_data.error_details:
            for error in report_data.error_details:
                error_type = error.type if error.type else "Unknown"
                error_types[error_type] = error_types.get(error_type, 0) + 1
            charts.set_error_types(error_types)

        return charts

    def _prepare_template_context(
        self,
        report_data: ReportData,
        charts: ChartCollection,
        results_directory: Path,
        version: Optional[str],
    ) -> Dict[str, Any]:
        """Prepare context for template rendering."""
        return {
            "report_data": report_data,
            "charts": charts,
            "results_directory": str(results_directory),
            "batch_execution_date": report_data.batch_execution_date,
            "version": version,
        }

    def validate_results_directory(self, results_directory: Path) -> Dict[str, bool]:
        """
        Validate that the results directory has the expected structure.

        Returns:
            Dictionary mapping expected items to their existence status
        """
        expected_items = {
            "success": (results_directory / "success").is_dir(),
            "failed": (results_directory / "failed").is_dir(),
            "proofs": (results_directory / "proofs").is_dir(),
            "traces": (results_directory / "traces").is_dir(),
            "execution_report.json": (
                results_directory / "execution_report.json"
            ).is_file(),
        }
        return expected_items

    def check_template_availability(self, format_type: str) -> bool:
        """Check if template is available for the given format."""
        template_name = f"report.{format_type}.j2"
        template_path = self.template_dir / template_name
        return template_path.exists()

    def get_available_formats(self) -> List[str]:
        """Get list of available output formats."""
        formats: List[str] = []
        for template_file in self.template_dir.glob("report.*.j2"):
            # Extract format from filename (e.g., "report.md.j2" -> "md")
            format_type = template_file.stem.split(".", 1)[1]
            formats.append(format_type)
        return sorted(formats)
