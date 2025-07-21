"""
Report generator service for creating comprehensive execution reports.

This module provides the main service for generating reports from execution
results using Jinja2 templates and various output formats.
"""

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
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        filters: Dict[str, Callable[[Any], str]] = self.env.filters  # type: ignore
        filters["latex_escape"] = self._latex_escape

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
            execution_report_path, results_directory
        )

        # Generate charts
        charts = self._generate_charts(report_data)

        # Prepare template context
        context = self._prepare_template_context(
            report_data, charts, results_directory, version
        )

        # Render template
        template_name = f"report.{format_type}.j2"
        try:
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
