"""
Chart classes for report visualization.

This module provides chart classes that can render data in different formats
for use in report templates (Mermaid, Typst, LaTeX, etc.).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union


class BaseChart(ABC):
    """Abstract base class for chart visualization."""

    def __init__(
        self,
        title: str,
        data: Union[Dict[str, Union[int, float]], List[Tuple[str, datetime, datetime]]],
    ):
        self.title = title
        self.data = data

    @abstractmethod
    def to_mermaid(self) -> str:
        """Render chart as Mermaid diagram."""

    @abstractmethod
    def to_typst_table(self) -> str:
        """Render chart as Typst table."""


class PieChart(BaseChart):
    """Pie chart for categorical data with percentages."""

    def __init__(self, title: str, data: Dict[str, Union[int, float]]):
        """
        Initialize pie chart.

        Args:
            title: Chart title
            data: Dictionary mapping category names to values
        """
        super().__init__(title, data)
        self.data: Dict[str, Union[int, float]] = data
        self.total = sum(data.values()) if data else 0

    def to_mermaid_pie(self) -> str:
        """Render as Mermaid pie chart."""
        if not self.data or self.total == 0:
            return f'pie title {self.title}\n    "No data": 100'

        lines = [f"pie title {self.title}"]
        for category, value in self.data.items():
            percentage = (value / self.total) * 100
            lines.append(f'    "{category}": {percentage:.1f}')

        return "\n".join(lines)

    def to_mermaid(self) -> str:
        """Render as Mermaid diagram."""
        return self.to_mermaid_pie()

    def to_typst_table(self) -> str:
        """Render as Typst table."""
        if not self.data or self.total == 0:
            return f"*{self.title}*\n\n#table(\n  columns: 2,\n  [*Category*], [*Value*],\n  [No data], [0]\n)"

        lines = [
            f"*{self.title}*",
            "",
            "#table(",
            "  columns: 2,",
            "  [*Category*], [*Value*],",
        ]
        for category, value in self.data.items():
            percentage = (value / self.total) * 100
            lines.append(f"  [{category}], [{value} ({percentage:.1f}%)],")
        lines.append(")")

        return "\n".join(lines)


class BarChart(BaseChart):
    """Bar chart for numerical data comparison."""

    def __init__(self, title: str, data: Dict[str, Union[int, float]], unit: str = ""):
        """
        Initialize bar chart.

        Args:
            title: Chart title
            data: Dictionary mapping category names to values
            unit: Unit of measurement (e.g., "seconds", "MB")
        """
        super().__init__(title, data)
        self.data: Dict[str, Union[int, float]] = data
        self.unit = unit

    def to_mermaid_bar(self) -> str:
        """Render as Mermaid bar chart."""
        if not self.data:
            return f'xychart-beta\n    title "{self.title}"\n    x-axis ["No data"]\n    y-axis "{self.unit}"\n    bar [0]'

        # Sort data by value for better visualization
        sorted_data = sorted(self.data.items(), key=lambda x: x[1], reverse=True)

        categories = [f'"{cat}"' for cat, _ in sorted_data]
        values = [str(val) for _, val in sorted_data]

        lines = [
            "xychart-beta",
            f'    title "{self.title}"',
            f'    x-axis [{", ".join(categories)}]',
            f'    y-axis "{self.unit}"',
            f'    bar [{", ".join(values)}]',
        ]

        return "\n".join(lines)

    def to_mermaid(self) -> str:
        """Render as Mermaid diagram."""
        return self.to_mermaid_bar()

    def to_typst_table(self) -> str:
        """Render as Typst table."""
        if not self.data:
            return f"*{self.title}*\n\n#table(\n  columns: 2,\n  [*Category*], [*Value*],\n  [No data], [0]\n)"

        # Sort data by value for better visualization
        sorted_data = sorted(self.data.items(), key=lambda x: x[1], reverse=True)

        lines = [
            f"*{self.title}*",
            "",
            "#table(",
            "  columns: 2,",
            "  [*Category*], [*Value*],",
        ]
        for category, value in sorted_data:
            unit_str = f" {self.unit}" if self.unit else ""
            lines.append(f"  [{category}], [{value:.2f}{unit_str}],")
        lines.append(")")

        return "\n".join(lines)


class GanttChart(BaseChart):
    """Gantt chart for timeline visualization."""

    def __init__(self, title: str, data: List[Tuple[str, datetime, datetime]]):
        """
        Initialize Gantt chart.

        Args:
            title: Chart title
            data: List of tuples (task_name, start_time, end_time)
        """
        super().__init__(title, data)
        self.data: List[Tuple[str, datetime, datetime]] = data

    def to_mermaid_gantt(self) -> str:
        """Render as Mermaid Gantt chart."""
        if not self.data:
            return f"gantt\n    title {self.title}\n    dateFormat X\n    axisFormat %s\n    section No Data\n    Empty : 0, 1"

        lines = [
            "gantt",
            f"    title {self.title}",
            "    dateFormat X",
            "    axisFormat %H:%M:%S",
            "    section Tasks",
        ]

        # Calculate relative timestamps
        try:
            if self.data:
                start_time = min(start for _, start, _ in self.data)
                for task_name, start, end in self.data:
                    start_offset = int((start - start_time).total_seconds())
                    end_offset = int((end - start_time).total_seconds())
                    # Ensure end_offset is at least start_offset + 1 to avoid zero-duration tasks
                    if end_offset <= start_offset:
                        end_offset = start_offset + 1
                    # Clean task name for Mermaid compatibility
                    clean_task_name = task_name.replace(" ", "_").replace("-", "_")
                    lines.append(
                        f"    {clean_task_name} : {start_offset}, {end_offset}"
                    )
        except Exception:
            # Fallback to simple representation if timestamp calculation fails
            lines = [
                "gantt",
                f"    title {self.title}",
                "    dateFormat X",
                "    axisFormat %s",
                "    section Tasks",
            ]
            for i, (task_name, _, _) in enumerate(self.data):
                clean_task_name = task_name.replace(" ", "_").replace("-", "_")
                lines.append(f"    {clean_task_name} : {i}, {i+1}")

        return "\n".join(lines)

    def to_mermaid(self) -> str:
        """Render as Mermaid diagram."""
        return self.to_mermaid_gantt()

    def to_typst_table(self) -> str:
        """Render as Typst table."""
        if not self.data:
            return f"*{self.title}*\n\n#table(\n  columns: 3,\n  [*Task*], [*Start*], [*End*],\n  [No data], [-], [-]\n)"

        lines = [
            f"*{self.title}*",
            "",
            "#table(",
            "  columns: 4,",
            "  [*Task*], [*Start*], [*End*], [*Duration*],",
        ]
        for task_name, start, end in self.data:
            try:
                start_str = start.strftime("%H:%M:%S")
                end_str = end.strftime("%H:%M:%S")
                duration = (end - start).total_seconds()
                duration_str = f"{duration:.1f}s"
            except Exception:
                start_str = "N/A"
                end_str = "N/A"
                duration_str = "N/A"
            lines.append(
                f"  [{task_name}], [{start_str}], [{end_str}], [{duration_str}],"
            )
        lines.append(")")

        return "\n".join(lines)


class ChartCollection:
    """Collection of charts for report generation."""

    def __init__(self):
        self.success_rate: Optional[PieChart] = None
        self.cache_hit_rate: Optional[PieChart] = None
        self.runtime_per_task: Optional[BarChart] = None
        self.memory_per_task: Optional[BarChart] = None
        self.execution_timeline: Optional[GanttChart] = None
        self.error_types: Optional[PieChart] = None

    def set_success_rate(self, successful: int, failed: int) -> None:
        """Set success rate chart data."""
        # Only create chart if there are any tasks
        if successful + failed > 0:
            data: Dict[str, Any] = {}
            if successful > 0:
                data["Successful"] = successful
            if failed > 0:
                data["Failed"] = failed
            self.success_rate = PieChart("Success Rate", data)

    def set_cache_hit_rate(self, cache_hits: int, cache_misses: int) -> None:
        """Set cache hit rate chart data."""
        # Only create chart if there are any lemmas
        if cache_hits + cache_misses > 0:
            data: Dict[str, Any] = {}
            if cache_hits > 0:
                data["Cache Hit"] = cache_hits
            if cache_misses > 0:
                data["Cache Miss"] = cache_misses
            self.cache_hit_rate = PieChart("Cache Hit Rate", data)

    def set_runtime_per_task(self, task_runtimes: Dict[str, float]) -> None:
        """Set runtime per task chart data."""
        if task_runtimes:
            self.runtime_per_task = BarChart(
                "Runtime per Task", task_runtimes, "seconds"
            )

    def set_memory_per_task(self, task_memory: Dict[str, float]) -> None:
        """Set memory per task chart data."""
        if task_memory:
            self.memory_per_task = BarChart("Memory Usage per Task", task_memory, "MB")

    def set_execution_timeline(
        self, timeline_data: List[Tuple[str, datetime, datetime]]
    ) -> None:
        """Set execution timeline chart data."""
        if timeline_data:
            self.execution_timeline = GanttChart("Execution Timeline", timeline_data)

    def set_error_types(self, error_data: Dict[str, Union[int, float]]) -> None:
        """Set error types chart data."""
        if error_data:
            self.error_types = PieChart("Error Types", error_data)
