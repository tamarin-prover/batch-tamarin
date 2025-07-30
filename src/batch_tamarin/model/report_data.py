"""
Report data model for processing execution results.

This module provides data models that process the execution_report.json
(Batch object) and transform it into a structure suitable for report templates.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    pass

from pydantic import BaseModel, Field, computed_field

from ..utils.dot_utils import is_dot_file_empty, process_dot_file
from .batch import (
    Batch,
    LemmaResult,
    TaskFailedResult,
    TaskStatus,
    TaskSucceedResult,
)


def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse timestamp string to datetime object."""
    # Common timestamp formats used by batch-tamarin
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f",  # ISO format with microseconds
        "%Y-%m-%dT%H:%M:%S",  # ISO format without microseconds
        "%Y-%m-%d %H:%M:%S.%f",  # Space-separated with microseconds
        "%Y-%m-%d %H:%M:%S",  # Space-separated without microseconds
        "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO format with microseconds and Z
        "%Y-%m-%dT%H:%M:%SZ",  # ISO format without microseconds and Z
    ]

    for fmt in formats:
        try:
            return datetime.strptime(timestamp_str, fmt)
        except ValueError:
            continue

    # If none of the formats work, try fromisoformat (Python 3.7+)
    try:
        # Remove trailing Z if present and handle it
        clean_timestamp = (
            timestamp_str.replace("Z", "+00:00")
            if timestamp_str.endswith("Z")
            else timestamp_str
        )
        return datetime.fromisoformat(clean_timestamp.replace("Z", ""))
    except Exception:
        # Last resort: return current time
        return datetime.now()


class ReportConfig(BaseModel):
    """Configuration information for the report."""

    global_max_cores: Optional[int] = Field(
        None, description="Maximum cores configured"
    )
    global_max_memory: Optional[int] = Field(
        None, description="Maximum memory configured in GB"
    )
    default_timeout: Optional[int] = Field(
        None, description="Default timeout in seconds"
    )
    output_directory: Optional[str] = Field(None, description="Output directory path")
    tamarin_versions: Dict[str, Dict[str, str]] = Field(
        default_factory=dict, description="Tamarin version configurations"
    )


class ReportStatistics(BaseModel):
    """Global statistics for the report."""

    total_tasks: int = Field(0, description="Total number of tasks")
    total_lemmas: int = Field(0, description="Total number of lemmas processed")
    successful_tasks: int = Field(0, description="Number of successful tasks")
    failed_tasks: int = Field(0, description="Number of failed tasks")
    cache_hits: int = Field(0, description="Number of cache hits")
    fresh_executions: int = Field(0, description="Number of fresh executions")
    total_runtime: float = Field(0.0, description="Total runtime in seconds")
    total_memory_usage: float = Field(0.0, description="Total memory usage in MB")
    max_runtime: float = Field(0.0, description="Maximum runtime of a single task")
    max_memory_usage: float = Field(
        0.0, description="Maximum memory usage of a single task"
    )

    # Lemma result statistics
    verified_lemmas: int = Field(0, description="Number of verified lemmas")
    falsified_lemmas: int = Field(0, description="Number of falsified lemmas")
    unterminated_lemmas: int = Field(0, description="Number of unterminated lemmas")
    failed_lemmas: int = Field(0, description="Number of failed lemmas")
    timeout_lemmas: int = Field(0, description="Number of timeout lemmas")
    memory_limit_lemmas: int = Field(0, description="Number of memory limit lemmas")

    @computed_field
    @property
    def successful_tasks_percentage(self) -> float:
        """Calculate successful tasks percentage."""
        if self.total_tasks == 0:
            return 0.0
        return (self.successful_tasks / self.total_tasks) * 100

    @computed_field
    @property
    def failed_tasks_percentage(self) -> float:
        """Calculate failed tasks percentage."""
        if self.total_tasks == 0:
            return 0.0
        return (self.failed_tasks / self.total_tasks) * 100

    @computed_field
    @property
    def cache_hit_percentage(self) -> float:
        """Calculate cache hit percentage."""
        if self.total_lemmas == 0:
            return 0.0
        return (self.cache_hits / self.total_lemmas) * 100

    @computed_field
    @property
    def fresh_percentage(self) -> float:
        """Calculate fresh execution percentage."""
        if self.total_lemmas == 0:
            return 0.0
        return (self.fresh_executions / self.total_lemmas) * 100

    @computed_field
    @property
    def verified_percentage(self) -> float:
        """Calculate verified lemmas percentage."""
        if self.total_lemmas == 0:
            return 0.0
        return (self.verified_lemmas / self.total_lemmas) * 100

    @computed_field
    @property
    def falsified_percentage(self) -> float:
        """Calculate falsified lemmas percentage."""
        if self.total_lemmas == 0:
            return 0.0
        return (self.falsified_lemmas / self.total_lemmas) * 100

    @computed_field
    @property
    def unterminated_percentage(self) -> float:
        """Calculate unterminated lemmas percentage."""
        if self.total_lemmas == 0:
            return 0.0
        return (self.unterminated_lemmas / self.total_lemmas) * 100

    @computed_field
    @property
    def failed_percentage(self) -> float:
        """Calculate failed lemmas percentage."""
        if self.total_lemmas == 0:
            return 0.0
        return (self.failed_lemmas / self.total_lemmas) * 100

    @computed_field
    @property
    def timeout_percentage(self) -> float:
        """Calculate timeout lemmas percentage."""
        if self.total_lemmas == 0:
            return 0.0
        return (self.timeout_lemmas / self.total_lemmas) * 100

    @computed_field
    @property
    def memory_limit_percentage(self) -> float:
        """Calculate memory limit lemmas percentage."""
        if self.total_lemmas == 0:
            return 0.0
        return (self.memory_limit_lemmas / self.total_lemmas) * 100


class TaskResult(BaseModel):
    """Individual task result for template rendering."""

    lemma: str = Field(..., description="Lemma name")
    tamarin_options: List[str] = Field(
        default_factory=list, description="Tamarin options used"
    )
    cores: Optional[int] = Field(None, description="Cores used")
    memory: Optional[int] = Field(None, description="Memory used in GB")
    timeout: Optional[int] = Field(None, description="Timeout used in seconds")
    options: Optional[str] = Field(None, description="Options string")
    preprocessor: Optional[str] = Field(None, description="Preprocessor used")
    tamarin_version: str = Field(..., description="Tamarin version used")
    status: str = Field(
        ...,
        description="Detailed status (verified/falsified/unterminated/timeout/memory_limit/failed)",
    )
    peak_memory: float = Field(0.0, description="Peak memory usage in MB")
    runtime: float = Field(0.0, description="Runtime in seconds")
    cache_hit: bool = Field(False, description="Whether result was from cache")
    error_description: Optional[str] = Field(
        None, description="Error description if failed"
    )
    stderr_lines: List[str] = Field(
        default_factory=list, description="Last stderr lines if failed"
    )
    error_type: Optional[str] = Field(None, description="Error type classification")


class LemmaGroup(BaseModel):
    """Group of results for the same lemma."""

    lemma: str = Field(..., description="Lemma name")
    results: List[TaskResult] = Field(default_factory=list, description="Results for this lemma")  # type: ignore[misc]


class VersionComparison(BaseModel):
    """Version comparison data for charts."""

    label: str = Field(..., description="Comparison label")
    runtime: float = Field(0.0, description="Runtime in seconds")
    memory: float = Field(0.0, description="Memory usage in MB")


class ExecutionTimelineItem(BaseModel):
    """Execution timeline item."""

    label: str = Field(..., description="Timeline label")
    start: int = Field(..., description="Start time (seconds from batch start)")
    end: int = Field(..., description="End time (seconds from batch start)")
    actual_start: datetime = Field(..., description="Actual start timestamp")
    actual_end: datetime = Field(..., description="Actual end timestamp")


class TaskSummary(BaseModel):
    """Summary of a task with all its results."""

    name: str = Field(..., description="Task name")
    theory_file: str = Field(..., description="Theory file path")
    output_prefix: Optional[str] = Field(
        None, description="Output file prefix from recipe"
    )
    results: List[TaskResult] = Field(  # type: ignore
        default_factory=list, description="Task results"
    )
    lemma_groups: List[LemmaGroup] = Field(default_factory=list, description="Grouped results by lemma")  # type: ignore[misc]
    total_runtime: float = Field(0.0, description="Total runtime for this task")
    peak_memory: float = Field(0.0, description="Peak memory for this task")
    execution_timeline_data: List[ExecutionTimelineItem] = Field(default_factory=list, description="Execution timeline with actual timestamps")  # type: ignore[misc]

    @computed_field
    @property
    def lemmas(self) -> List[str]:
        """Get list of lemmas in this task."""
        return list(set(result.lemma for result in self.results))

    @computed_field
    @property
    def tamarin_versions(self) -> List[str]:
        """Get list of Tamarin versions used in this task."""
        return list(set(result.tamarin_version for result in self.results))

    @computed_field
    @property
    def total_results(self) -> int:
        """Get total number of results."""
        return len(self.results)

    @computed_field
    @property
    def has_version_comparisons(self) -> bool:
        """Check if task has multiple versions for comparison."""
        return len(self.tamarin_versions) > 1

    @computed_field
    @property
    def version_comparisons(self) -> List[VersionComparison]:
        """Get version comparison data."""
        comparisons: List[VersionComparison] = []
        for result in self.results:
            label = f"{result.lemma}_{result.tamarin_version}"
            comparisons.append(
                VersionComparison(
                    label=label, runtime=result.runtime, memory=result.peak_memory
                )
            )
        return comparisons

    @computed_field
    @property
    def execution_timeline(self) -> List[ExecutionTimelineItem]:
        """Get execution timeline data with actual timestamps."""
        return self.execution_timeline_data

    @computed_field
    @property
    def traces(self) -> List["TraceInfo"]:
        """Get traces for this task (will be populated from ReportData)."""
        return []


class TraceInfo(BaseModel):
    """Trace information for visualization."""

    lemma: str = Field(..., description="Lemma name")
    tamarin_version: str = Field(..., description="Tamarin version")
    json_file: str = Field(..., description="JSON trace file path")
    dot_file: Optional[str] = Field(None, description="DOT trace file path")
    svg_content: Optional[str] = Field(None, description="SVG trace content")
    png_file: Optional[Path] = Field(
        None, description="PNG trace file path (for LaTeX)"
    )
    output_prefix: Optional[str] = Field(None, description="Output prefix for the task")


class ErrorDetail(BaseModel):
    """Error detail for summary table."""

    task: str = Field(..., description="Task name")
    lemma: str = Field(..., description="Lemma name")
    version: str = Field(..., description="Tamarin version")
    options: str = Field(..., description="Tamarin options")
    resources: str = Field(..., description="Resource configuration")
    type: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")


class ErrorTypeDistribution(BaseModel):
    """Error type distribution for charts."""

    name: str = Field(..., description="Error type name")
    percentage: float = Field(..., description="Percentage of this error type")


class LemmaErrorGroup(BaseModel):
    """Group of error results for the same lemma."""

    lemma: str = Field(..., description="Lemma name")
    results: List[TaskResult] = Field(default_factory=list, description="Error results for this lemma")  # type: ignore[misc]


class ErrorSummaryItem(BaseModel):
    """Error summary item for grouped error display."""

    task_name: str = Field(..., description="Task name")
    total_errors: int = Field(..., description="Total errors in this task")
    lemma_errors: List[LemmaErrorGroup] = Field(default_factory=list, description="Errors grouped by lemma")  # type: ignore[misc]


class DetailedError(BaseModel):
    """Detailed error information."""

    task_name: str = Field(..., description="Task name")
    lemma: str = Field(..., description="Lemma name")
    tamarin_version: str = Field(..., description="Tamarin version")
    type: str = Field(..., description="Error type")
    description: str = Field(..., description="Error description")
    stderr_output: Optional[str] = Field(None, description="Standard error output")


class ReportData(BaseModel):
    """Main report data model."""

    results_directory: str = Field(..., description="Results directory path")
    generation_date: datetime = Field(
        default_factory=datetime.now, description="Report generation date"
    )
    batch_execution_date: datetime = Field(..., description="Batch execution date")
    config: ReportConfig = Field(..., description="Configuration information")
    statistics: ReportStatistics = Field(..., description="Global statistics")
    tasks: List[TaskSummary] = Field(  # type: ignore
        default_factory=list, description="Task summaries"
    )
    traces: List[TraceInfo] = Field(  # type: ignore
        default_factory=list, description="Trace information"
    )
    error_details: List[ErrorDetail] = Field(  # type: ignore
        default_factory=list, description="Error details"
    )
    rerun_file: str = Field(default="rerun.json", description="Rerun file name")
    global_timeline_data: List[ExecutionTimelineItem] = Field(default_factory=list, description="Global execution timeline with actual timestamps")  # type: ignore[misc]

    @computed_field
    @property
    def failed_results(self) -> List[TaskResult]:
        """Get all failed task results."""
        failed: List[TaskResult] = []
        for task in self.tasks:
            for result in task.results:
                if result.status in ["failed", "timeout", "memory_limit"]:
                    failed.append(result)
        return failed

    @computed_field
    @property
    def start_time(self) -> int:
        """Get global start time."""
        return 0

    @computed_field
    @property
    def end_time(self) -> int:
        """Get global end time."""
        return int(self.statistics.total_runtime)

    @computed_field
    @property
    def global_timeline(self) -> List[ExecutionTimelineItem]:
        """Get global execution timeline with actual timestamps."""
        return self.global_timeline_data

    @computed_field
    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.failed_results) > 0

    @computed_field
    @property
    def error_type_distribution(self) -> List[ErrorTypeDistribution]:
        """Get error type distribution for charts."""
        if not self.failed_results:
            return []

        error_counts: Dict[str, int] = {}
        total_errors = len(self.failed_results)

        for result in self.failed_results:
            error_type = result.error_type or result.status
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

        distribution: List[ErrorTypeDistribution] = []
        for error_type, count in error_counts.items():
            percentage: float = (count / total_errors) * 100
            # Map internal error types to display names
            display_name = {
                "timeout": "Timeout",
                "memory_limit": "Memory Limit",
                "failed": "Tamarin Error",
                "tamarin_error": "Tamarin Error",
            }.get(error_type, error_type.title() if error_type else "Unknown")

            distribution.append(
                ErrorTypeDistribution(name=display_name, percentage=percentage)
            )

        return distribution

    @computed_field
    @property
    def error_summary(self) -> List[ErrorSummaryItem]:
        """Get error summary grouped by task and lemma."""
        error_summary: List[ErrorSummaryItem] = []

        for task in self.tasks:
            error_results = [
                r
                for r in task.results
                if r.status in ["failed", "timeout", "memory_limit"]
            ]
            if not error_results:
                continue

            # Group by lemma
            lemma_groups: Dict[str, List[TaskResult]] = {}
            for result in error_results:
                if result.lemma not in lemma_groups:
                    lemma_groups[result.lemma] = []
                lemma_groups[result.lemma].append(result)

            lemma_error_groups: List[LemmaErrorGroup] = []
            for lemma, results in lemma_groups.items():
                lemma_error_groups.append(LemmaErrorGroup(lemma=lemma, results=results))

            error_summary.append(
                ErrorSummaryItem(
                    task_name=task.name,
                    total_errors=len(error_results),
                    lemma_errors=lemma_error_groups,
                )
            )

        return error_summary

    @computed_field
    @property
    def detailed_errors(self) -> List[DetailedError]:
        """Get detailed error information."""
        detailed: List[DetailedError] = []
        for result in self.failed_results:
            error_type = result.error_type or result.status
            # Map to display error types
            display_type = {
                "timeout": "timeout",
                "memory_limit": "memory_limit",
                "failed": "tamarin_error",
                "tamarin_error": "tamarin_error",
            }.get(error_type, error_type)

            stderr_output = None
            if result.stderr_lines:
                stderr_output = "\n".join(result.stderr_lines)

            detailed.append(
                DetailedError(
                    task_name=next(
                        (
                            t.name
                            for t in self.tasks
                            if any(r.lemma == result.lemma for r in t.results)
                        ),
                        "Unknown",
                    ),
                    lemma=result.lemma,
                    tamarin_version=result.tamarin_version,
                    type=display_type,
                    description=result.error_description or "Unknown error",
                    stderr_output=stderr_output,
                )
            )

        return detailed

    def has_version_comparisons(self, task_name: str) -> bool:
        """Check if a task has multiple Tamarin versions for comparison."""
        task = next((t for t in self.tasks if t.name == task_name), None)
        if not task:
            return False
        return len(task.tamarin_versions) > 1

    def get_results_by_lemma(self, lemma: str) -> List[TaskResult]:
        """Get all results for a specific lemma."""
        results: List[TaskResult] = []
        for task in self.tasks:
            for result in task.results:
                if result.lemma == lemma:
                    results.append(result)
        return results

    @classmethod
    def from_batch_and_output_dir(
        cls, batch: Batch, output_dir: Path, format_type: str
    ) -> "ReportData":
        """Create ReportData from Batch object and output directory."""
        # Extract basic information
        results_directory = str(output_dir.absolute())

        # Find the earliest start time from all tasks to determine batch start
        earliest_start: Optional[datetime] = None
        all_timestamps: List[datetime] = []

        for rich_task in batch.tasks.values():
            for executable_task in rich_task.subtasks.values():
                try:
                    start_time = parse_timestamp(
                        executable_task.task_execution_metadata.exec_start
                    )
                    all_timestamps.append(start_time)
                    if earliest_start is None or start_time < earliest_start:
                        earliest_start = start_time
                except Exception:
                    continue

        batch_execution_date = earliest_start or datetime.now()

        # Build configuration
        config = ReportConfig(
            global_max_cores=(
                batch.config.global_max_cores
                if isinstance(batch.config.global_max_cores, int)
                else None
            ),
            global_max_memory=(
                batch.config.global_max_memory
                if isinstance(batch.config.global_max_memory, int)
                else None
            ),
            default_timeout=batch.config.default_timeout,
            output_directory=batch.config.output_directory,
            tamarin_versions={
                alias: {"path": version.path, "version": version.version or ""}
                for alias, version in batch.tamarin_versions.items()
            },
        )

        # Count lemma results by analyzing all executable tasks
        verified_count = 0
        falsified_count = 0
        unterminated_count = 0
        failed_count = 0
        timeout_count = 0
        memory_limit_count = 0

        total_lemmas = 0
        for rich_task in batch.tasks.values():
            for executable_task in rich_task.subtasks.values():
                total_lemmas += 1
                status = executable_task.task_execution_metadata.status

                if status == TaskStatus.COMPLETED and executable_task.task_result:
                    if isinstance(executable_task.task_result, TaskSucceedResult):
                        lemma_result = executable_task.task_result.lemma_result
                        if lemma_result == LemmaResult.VERIFIED:
                            verified_count += 1
                        elif lemma_result == LemmaResult.FALSIFIED:
                            falsified_count += 1
                        elif lemma_result == LemmaResult.UNTERMINATED:
                            unterminated_count += 1
                elif status == TaskStatus.TIMEOUT:
                    timeout_count += 1
                elif status == TaskStatus.MEMORY_LIMIT_EXCEEDED:
                    memory_limit_count += 1
                else:
                    failed_count += 1

        fresh_executions = total_lemmas - batch.execution_metadata.total_cache_hit

        # Build statistics with detailed counts
        statistics = ReportStatistics(
            total_tasks=batch.execution_metadata.total_tasks,
            total_lemmas=total_lemmas,
            successful_tasks=batch.execution_metadata.total_successes,
            failed_tasks=batch.execution_metadata.total_failures,
            cache_hits=batch.execution_metadata.total_cache_hit,
            fresh_executions=fresh_executions,
            total_runtime=batch.execution_metadata.total_runtime,
            total_memory_usage=batch.execution_metadata.total_memory,
            max_runtime=batch.execution_metadata.max_runtime,
            max_memory_usage=batch.execution_metadata.max_memory,
            verified_lemmas=verified_count,
            falsified_lemmas=falsified_count,
            unterminated_lemmas=unterminated_count,
            failed_lemmas=failed_count,
            timeout_lemmas=timeout_count,
            memory_limit_lemmas=memory_limit_count,
        )

        # Build task summaries
        tasks: List[TaskSummary] = []
        error_details: List[ErrorDetail] = []

        # Store all timeline items for global timeline
        all_timeline_items: List[ExecutionTimelineItem] = []

        for task_name, rich_task in batch.tasks.items():
            task_results: List[TaskResult] = []
            task_total_runtime = 0.0
            task_peak_memory = 0.0
            task_timeline_items: List[ExecutionTimelineItem] = []

            for subtask_key, executable_task in rich_task.subtasks.items():
                # Extract lemma and version directly from the task config
                lemma = executable_task.task_config.lemma
                version = executable_task.task_config.tamarin_alias
                status = executable_task.task_execution_metadata.status

                # Update task totals
                task_total_runtime += (
                    executable_task.task_execution_metadata.exec_duration_monotonic
                )
                task_peak_memory = max(
                    task_peak_memory,
                    executable_task.task_execution_metadata.peak_memory,
                )

                # Determine detailed status based on task execution status and result
                detailed_status = "failed"  # default
                error_description = None
                error_type = None
                stderr_lines = []

                if status == TaskStatus.COMPLETED and executable_task.task_result:
                    if isinstance(executable_task.task_result, TaskSucceedResult):
                        lemma_result = executable_task.task_result.lemma_result
                        if lemma_result == LemmaResult.VERIFIED:
                            detailed_status = "verified"
                        elif lemma_result == LemmaResult.FALSIFIED:
                            detailed_status = "falsified"
                        elif lemma_result == LemmaResult.UNTERMINATED:
                            detailed_status = "unterminated"
                elif status == TaskStatus.TIMEOUT:
                    detailed_status = "timeout"
                    error_description = "Task timed out during execution"
                    error_type = "timeout"
                elif status == TaskStatus.MEMORY_LIMIT_EXCEEDED:
                    detailed_status = "memory_limit"
                    error_description = "Task killed for exceeding memory limit"
                    error_type = "memory_limit"
                else:
                    # Handle failed tasks with error information
                    detailed_status = "failed"
                    if isinstance(executable_task.task_result, TaskFailedResult):
                        error_description = (
                            executable_task.task_result.error_description
                        )
                        stderr_lines = executable_task.task_result.last_stderr_lines
                        error_type = (
                            executable_task.task_result.error_type.value
                            if executable_task.task_result.error_type
                            else "unknown"
                        )

                # Format options and preprocessor
                options_str = (
                    " ".join(executable_task.task_config.options or [])
                    if executable_task.task_config.options
                    else None
                )
                preprocessor_str = (
                    " ".join(executable_task.task_config.preprocessor_flags or [])
                    if executable_task.task_config.preprocessor_flags
                    else None
                )

                # Build task result
                task_result = TaskResult(
                    lemma=lemma,
                    tamarin_options=executable_task.task_config.options or [],
                    cores=executable_task.task_config.resources.cores,
                    memory=executable_task.task_config.resources.memory,
                    timeout=executable_task.task_config.resources.timeout,
                    options=options_str,
                    preprocessor=preprocessor_str,
                    tamarin_version=version,
                    status=detailed_status,
                    peak_memory=executable_task.task_execution_metadata.peak_memory,
                    runtime=executable_task.task_execution_metadata.exec_duration_monotonic,
                    cache_hit=executable_task.task_execution_metadata.cache_hit,
                    error_description=error_description,
                    stderr_lines=stderr_lines,
                    error_type=error_type,
                )

                # Add to error details if failed
                if detailed_status in ["failed", "timeout", "memory_limit"]:
                    error_detail = ErrorDetail(
                        task=task_name,
                        lemma=lemma,
                        version=version,
                        options=options_str or "None",
                        resources=f"{executable_task.task_config.resources.cores}c / {executable_task.task_config.resources.memory}GB / {executable_task.task_config.resources.timeout}s",
                        type=error_type or "unknown",
                        message=error_description or "Unknown error",
                    )
                    error_details.append(error_detail)

                task_results.append(task_result)

                # Create timeline item with actual timestamps
                try:
                    actual_start = parse_timestamp(
                        executable_task.task_execution_metadata.exec_start
                    )
                    actual_end = parse_timestamp(
                        executable_task.task_execution_metadata.exec_end
                    )

                    # Calculate seconds from batch start
                    start_seconds = int(
                        (actual_start - batch_execution_date).total_seconds()
                    )
                    end_seconds = int(
                        (actual_end - batch_execution_date).total_seconds()
                    )

                    # Ensure positive values
                    start_seconds = max(0, start_seconds)
                    end_seconds = max(
                        start_seconds + 1, end_seconds
                    )  # Ensure end > start

                    timeline_item = ExecutionTimelineItem(
                        label=f"{lemma}_{version.replace(' ', '_')}",
                        start=start_seconds,
                        end=end_seconds,
                        actual_start=actual_start,
                        actual_end=actual_end,
                    )

                    task_timeline_items.append(timeline_item)
                    all_timeline_items.append(timeline_item)

                except Exception:
                    # Skip timeline item if timestamp parsing fails
                    continue

            # Group results by lemma for the template
            lemma_groups: Dict[str, List[TaskResult]] = {}
            for result in task_results:
                if result.lemma not in lemma_groups:
                    lemma_groups[result.lemma] = []
                lemma_groups[result.lemma].append(result)

            lemma_group_objects: List[LemmaGroup] = []
            for lemma, results in lemma_groups.items():
                lemma_group_objects.append(LemmaGroup(lemma=lemma, results=results))

            # Extract output_prefix from subtask names (format: {output_prefix}--{lemma}--{version})
            output_prefix = None
            if rich_task.subtasks:
                # Get the first subtask name and extract prefix
                first_subtask_name = next(iter(rich_task.subtasks.keys()))
                if "--" in first_subtask_name:
                    output_prefix = first_subtask_name.split("--")[0]

            task_summary = TaskSummary(
                name=task_name,
                theory_file=rich_task.theory_file,
                output_prefix=output_prefix,
                results=task_results,
                lemma_groups=lemma_group_objects,
                total_runtime=task_total_runtime,
                peak_memory=task_peak_memory,
                execution_timeline_data=task_timeline_items,
            )
            tasks.append(task_summary)

        # Build trace information using batch data (avoid filename parsing)
        traces: List[TraceInfo] = []
        traces_dir = output_dir / "traces"
        if traces_dir.exists():
            # Build mapping from subtask_key to (lemma, version) for trace lookup
            subtask_mapping: Dict[str, tuple[str, str]] = {}
            for task_name, rich_task in batch.tasks.items():
                for subtask_key, executable_task in rich_task.subtasks.items():
                    subtask_mapping[subtask_key] = (
                        executable_task.task_config.lemma,
                        executable_task.task_config.tamarin_alias,
                    )

            for trace_file in traces_dir.glob("*.json"):
                # Use subtask key to lookup lemma and version from batch data
                filename = trace_file.stem
                if filename in subtask_mapping:
                    lemma: str
                    version: str
                    lemma, version = subtask_mapping[filename]

                    # Extract output_prefix from filename (format: {output_prefix}--{lemma}--{version})
                    output_prefix = None
                    if "--" in filename:
                        output_prefix = filename.split("--")[0]
                else:
                    # Skip files that don't match any subtask
                    continue

                # Look for corresponding DOT file
                dot_file = trace_file.with_suffix(".dot")

                # Validate DOT file and generate SVG
                svg_content = None
                dot_file_path = None
                png_file = None

                if dot_file.exists() and not is_dot_file_empty(dot_file):
                    dot_file_path = str(dot_file)
                    # Try to process DOT file to generate SVG
                    svg_content = process_dot_file(dot_file, format_type)

                if format_type == "tex":
                    # For LaTeX format, check if PNG file was created by process_dot_file
                    potential_png_file = trace_file.with_suffix(".png")
                    if potential_png_file.exists():
                        png_file = potential_png_file

                trace_info = TraceInfo(
                    lemma=lemma,
                    tamarin_version=version,
                    json_file=str(trace_file.absolute()),
                    dot_file=(
                        str(Path(dot_file_path).absolute()) if dot_file_path else None
                    ),
                    svg_content=svg_content,
                    png_file=png_file.absolute() if png_file is not None else None,
                    output_prefix=output_prefix,
                )
                traces.append(trace_info)

        # Determine rerun file name with absolute path
        recipe_name = (
            Path(batch.recipe).stem
            if hasattr(Path(batch.recipe), "stem")
            else str(batch.recipe)
        )
        rerun_file = str(
            (Path(results_directory) / f"{recipe_name}-rerun.json").absolute()
        )

        return cls(
            results_directory=results_directory,
            batch_execution_date=batch_execution_date,
            config=config,
            statistics=statistics,
            tasks=tasks,
            traces=traces,
            error_details=error_details,
            rerun_file=rerun_file,
            global_timeline_data=all_timeline_items,
        )

    @classmethod
    def from_execution_report(
        cls, execution_report_path: Path, output_dir: Path, format_type: str
    ) -> "ReportData":
        """Create ReportData from execution_report.json file."""
        with open(execution_report_path, "r", encoding="utf-8") as f:
            batch_data = json.load(f)

        batch = Batch.model_validate(batch_data)
        return cls.from_batch_and_output_dir(batch, output_dir, format_type)
