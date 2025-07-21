"""
Report data model for processing execution results.

This module provides data models that process the execution_report.json
(Batch object) and transform it into a structure suitable for report templates.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, computed_field

from ..model.batch import Batch, TaskStatus
from ..utils.dot_utils import is_dot_file_empty, process_dot_file


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
    total_runtime: float = Field(0.0, description="Total runtime in seconds")
    total_memory_usage: float = Field(0.0, description="Total memory usage in MB")
    max_runtime: float = Field(0.0, description="Maximum runtime of a single task")
    max_memory_usage: float = Field(
        0.0, description="Maximum memory usage of a single task"
    )

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


class TaskResult(BaseModel):
    """Individual task result for template rendering."""

    lemma: str = Field(..., description="Lemma name")
    tamarin_options: List[str] = Field(
        default_factory=list, description="Tamarin options used"
    )
    max_cores: Optional[int] = Field(None, description="Maximum cores used")
    max_memory: Optional[int] = Field(None, description="Maximum memory used in GB")
    timeout: Optional[int] = Field(None, description="Timeout used in seconds")
    tamarin_version: str = Field(..., description="Tamarin version used")
    status: str = Field(..., description="Task status (success/failed)")
    peak_memory: float = Field(0.0, description="Peak memory usage in MB")
    runtime: float = Field(0.0, description="Runtime in seconds")
    cache_hit: bool = Field(False, description="Whether result was from cache")
    error_description: Optional[str] = Field(
        None, description="Error description if failed"
    )
    stderr_lines: List[str] = Field(
        default_factory=list, description="Last stderr lines if failed"
    )


class TaskSummary(BaseModel):
    """Summary of a task with all its results."""

    name: str = Field(..., description="Task name")
    theory_file: str = Field(..., description="Theory file path")
    results: List[TaskResult] = Field(  # type: ignore
        default_factory=list, description="Task results"
    )

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


class TraceInfo(BaseModel):
    """Trace information for visualization."""

    lemma: str = Field(..., description="Lemma name")
    tamarin_version: str = Field(..., description="Tamarin version")
    json_file: str = Field(..., description="JSON trace file path")
    dot_file: Optional[str] = Field(None, description="DOT trace file path")
    svg_content: Optional[str] = Field(None, description="SVG trace content")


class ErrorDetail(BaseModel):
    """Error detail for summary table."""

    task: str = Field(..., description="Task name")
    lemma: str = Field(..., description="Lemma name")
    version: str = Field(..., description="Tamarin version")
    options: str = Field(..., description="Tamarin options")
    resources: str = Field(..., description="Resource configuration")
    type: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")


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

    @computed_field
    @property
    def failed_results(self) -> List[TaskResult]:
        """Get all failed task results."""
        failed: List[TaskResult] = []
        for task in self.tasks:
            for result in task.results:
                if result.status == "failed":
                    failed.append(result)
        return failed

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
    def from_batch_and_output_dir(cls, batch: Batch, output_dir: Path) -> "ReportData":
        """Create ReportData from Batch object and output directory."""
        # Extract basic information
        results_directory = str(output_dir.absolute())

        # Parse batch execution date (assuming it's in the filename or metadata)
        batch_execution_date = datetime.now()  # Default to now if not available

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

        # Build statistics
        statistics = ReportStatistics(
            total_tasks=batch.execution_metadata.total_tasks,
            total_lemmas=batch.execution_metadata.total_tasks,  # Assuming 1:1 for now
            successful_tasks=batch.execution_metadata.total_successes,
            failed_tasks=batch.execution_metadata.total_failures,
            cache_hits=batch.execution_metadata.total_cache_hit,
            total_runtime=batch.execution_metadata.total_runtime,
            total_memory_usage=batch.execution_metadata.total_memory,
            max_runtime=batch.execution_metadata.max_runtime,
            max_memory_usage=batch.execution_metadata.max_memory,
        )

        # Build task summaries
        tasks: List[TaskSummary] = []
        error_details: List[ErrorDetail] = []

        for task_name, rich_task in batch.tasks.items():
            task_results: List[TaskResult] = []

            for subtask_key, executable_task in rich_task.subtasks.items():
                # Parse subtask key (format: lemma--version)
                parts = subtask_key.split("--")
                lemma = parts[0] if parts else "unknown"
                version = parts[1] if len(parts) > 1 else "unknown"

                # Build task result
                task_result = TaskResult(
                    lemma=lemma,
                    tamarin_options=executable_task.task_config.options or [],
                    max_cores=executable_task.task_config.resources.cores,
                    max_memory=executable_task.task_config.resources.memory,
                    timeout=executable_task.task_config.resources.timeout,
                    tamarin_version=version,
                    status=(
                        "success"
                        if executable_task.task_execution_metadata.status
                        == TaskStatus.COMPLETED
                        else "failed"
                    ),
                    peak_memory=executable_task.task_execution_metadata.peak_memory,
                    runtime=executable_task.task_execution_metadata.exec_duration_monotonic,
                    cache_hit=executable_task.task_execution_metadata.cache_hit,
                    error_description=None,
                )

                # Add error information if failed
                if executable_task.task_result and hasattr(
                    executable_task.task_result, "error_description"
                ):
                    error_desc = getattr(
                        executable_task.task_result,
                        "error_description",
                        "Unknown error",
                    )
                    task_result.error_description = error_desc

                    if hasattr(executable_task.task_result, "last_stderr_lines"):
                        stderr_lines = getattr(
                            executable_task.task_result, "last_stderr_lines", []
                        )
                        task_result.stderr_lines = (
                            stderr_lines if isinstance(stderr_lines, list) else []
                        )

                    # Add to error details
                    error_type = "unknown"
                    if hasattr(executable_task.task_result, "error_type"):
                        error_type_attr = getattr(
                            executable_task.task_result, "error_type", None
                        )
                        if error_type_attr and hasattr(error_type_attr, "value"):
                            error_type = error_type_attr.value

                    error_detail = ErrorDetail(
                        task=task_name,
                        lemma=lemma,
                        version=version,
                        options=" ".join(executable_task.task_config.options or []),
                        resources=f"{executable_task.task_config.resources.cores}c/{executable_task.task_config.resources.memory}GB/{executable_task.task_config.resources.timeout}s",
                        type=error_type,
                        message=error_desc,
                    )
                    error_details.append(error_detail)

                task_results.append(task_result)

            task_summary = TaskSummary(
                name=task_name, theory_file=rich_task.theory_file, results=task_results
            )
            tasks.append(task_summary)

        # Build trace information (scan traces directory)
        traces: List[TraceInfo] = []
        traces_dir = output_dir / "traces"
        if traces_dir.exists():
            for trace_file in traces_dir.glob("*.json"):
                # Parse trace filename to extract lemma and version
                filename = trace_file.stem
                parts = filename.split("--")
                if len(parts) >= 2:
                    lemma = parts[0]
                    version = parts[1]

                    # Look for corresponding DOT file
                    dot_file = trace_file.with_suffix(".dot")

                    # Validate DOT file and generate SVG
                    svg_content = None
                    dot_file_path = None

                    if dot_file.exists() and not is_dot_file_empty(dot_file):
                        dot_file_path = str(dot_file)
                        # Try to process DOT file to generate SVG
                        svg_content = process_dot_file(dot_file)

                    # If no SVG generated from DOT, check for existing SVG
                    if svg_content is None:
                        svg_file = trace_file.with_suffix(".svg")
                        if svg_file.exists():
                            try:
                                svg_content = svg_file.read_text(encoding="utf-8")
                            except Exception:
                                pass

                    trace_info = TraceInfo(
                        lemma=lemma,
                        tamarin_version=version,
                        json_file=str(trace_file),
                        dot_file=dot_file_path,
                        svg_content=svg_content,
                    )
                    traces.append(trace_info)

        return cls(
            results_directory=results_directory,
            batch_execution_date=batch_execution_date,
            config=config,
            statistics=statistics,
            tasks=tasks,
            traces=traces,
            error_details=error_details,
        )

    @classmethod
    def from_execution_report(
        cls, execution_report_path: Path, output_dir: Path
    ) -> "ReportData":
        """Create ReportData from execution_report.json file."""
        with open(execution_report_path, "r", encoding="utf-8") as f:
            batch_data = json.load(f)

        batch = Batch.model_validate(batch_data)
        return cls.from_batch_and_output_dir(batch, output_dir)
