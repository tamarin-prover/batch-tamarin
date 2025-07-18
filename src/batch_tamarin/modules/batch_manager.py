"""
BatchManager for handling batch operations and execution reporting.

This module provides the BatchManager class that consolidates batch-related
operations and generates execution reports from TaskRunner results.
"""

from datetime import datetime
from typing import Dict, List, Optional

from ..model.batch import (
    Batch,
    ErrorType,
    ExecMetadata,
    LemmaResult,
    Resources,
    RichExecutableTask,
    RichTask,
    TaskConfig,
    TaskExecMetadata,
    TaskFailedResult,
    TaskStatus,
    TaskSucceedResult,
)
from ..model.executable_task import (
    ExecutableTask,
    TaskResult,
)
from ..model.executable_task import TaskStatus as ExecutableTaskStatus
from ..model.tamarin_recipe import TamarinRecipe, TamarinVersion
from ..modules.output_manager import SuccessfulTaskResult, output_manager
from ..modules.tamarin_test_cmd import extract_tamarin_version
from ..modules.task_manager import ExecutionSummary
from ..runner import TaskRunner
from ..utils.notifications import notification_manager
from ..utils.system_resources import resolve_executable_path, resolve_resource_value


class BatchManager:
    """
    Manages batch operations and execution reporting.

    This class consolidates batch-related operations that were previously
    scattered across different modules, providing a clean interface for
    batch creation and execution report generation.
    """

    def __init__(self, recipe: TamarinRecipe, recipe_name: str):
        """
        Initialize BatchManager with recipe and name.

        Args:
            recipe: The TamarinRecipe configuration
            recipe_name: Name of the recipe file
        """
        self.recipe = recipe
        self.recipe_name = recipe_name

    async def generate_execution_report(
        self, runner: TaskRunner, executable_tasks: List[ExecutableTask]
    ) -> None:
        """
        Generate execution report from runner results.

        Args:
            runner: TaskRunner instance with execution results
            executable_tasks: List of executed tasks
        """
        try:
            # Create batch with resolved configuration
            batch = await self._create_batch_with_resolved_config()

            # Populate batch with execution results
            self._populate_batch_with_results(batch, runner, executable_tasks)

            # Generate execution report file
            await self._write_execution_report(batch)

        except Exception as e:
            notification_manager.error(
                f"[BatchManager] Failed to generate execution report: {e}"
            )
            # Don't raise - this is not a critical failure

    async def _create_batch_with_resolved_config(self) -> Batch:
        """Create batch with resolved configuration values."""
        # Initialize execution metadata with placeholder values
        execution_metadata = ExecMetadata(
            total_tasks=0,
            total_successes=0,
            total_failures=0,
            total_cache_hit=0,
            total_runtime=0,
            total_memory=0,
            max_runtime=0,
            max_memory=0,
        )

        # Resolve config values
        resolved_config = self.recipe.config.model_copy()
        resolved_config.global_max_cores = resolve_resource_value(
            self.recipe.config.global_max_cores, "cores"
        )
        resolved_config.global_max_memory = resolve_resource_value(
            self.recipe.config.global_max_memory, "memory"
        )

        # Resolve tamarin versions
        resolved_tamarin_versions: Dict[str, TamarinVersion] = {}
        for version_name, version_info in self.recipe.tamarin_versions.items():
            resolved_version = version_info.model_copy()

            try:
                tamarin_path = resolve_executable_path(version_info.path)
                extracted_version = await extract_tamarin_version(tamarin_path)
                resolved_version.version = extracted_version
            except Exception:
                resolved_version.version = None

            resolved_tamarin_versions[version_name] = resolved_version

        # Create batch with resolved values
        return Batch(
            recipe=self.recipe_name,
            config=resolved_config,
            tamarin_versions=resolved_tamarin_versions,
            execution_metadata=execution_metadata,
            tasks={},
        )

    def _populate_batch_with_results(
        self, batch: Batch, runner: TaskRunner, executable_tasks: List[ExecutableTask]
    ) -> None:
        """Populate batch with execution results."""
        # Update global execution metadata
        execution_summary: ExecutionSummary = (
            runner.task_manager.generate_execution_summary()
        )
        batch.execution_metadata.total_tasks = len(executable_tasks)
        batch.execution_metadata.total_successes = len(runner.completed_tasks)
        batch.execution_metadata.total_failures = len(runner.failed_tasks)
        batch.execution_metadata.total_cache_hit = execution_summary.cached_tasks

        # Calculate totals and maxima
        total_memory = 0
        total_runtime = 0
        max_runtime = 0
        max_memory = 0

        for task_result in runner.task_results.values():
            if task_result.memory_stats:
                total_memory += task_result.memory_stats.peak_memory_mb
                max_memory = max(max_memory, task_result.memory_stats.peak_memory_mb)
            total_runtime += task_result.duration
            max_runtime = max(max_runtime, task_result.duration)

        batch.execution_metadata.total_memory = total_memory
        batch.execution_metadata.total_runtime = total_runtime
        batch.execution_metadata.max_runtime = max_runtime
        batch.execution_metadata.max_memory = max_memory

        # Create RichTask structure from executable tasks
        batch.tasks = self._create_rich_tasks_from_executable_tasks(
            executable_tasks, runner, execution_summary
        )

    def _create_rich_tasks_from_executable_tasks(
        self,
        executable_tasks: List[ExecutableTask],
        runner: TaskRunner,
        execution_summary: ExecutionSummary,
    ) -> Dict[str, RichTask]:
        """Create RichTask objects from executable tasks and results."""
        # Group tasks by original task name
        task_groups: Dict[str, List[ExecutableTask]] = {}
        for executable_task in executable_tasks:
            # Extract original task name from executable task name
            original_task_name = self._extract_original_task_name(
                executable_task.task_name
            )

            if original_task_name not in task_groups:
                task_groups[original_task_name] = []
            task_groups[original_task_name].append(executable_task)

        # Create RichTask objects
        rich_tasks: Dict[str, RichTask] = {}
        for original_task_name, tasks in task_groups.items():
            subtasks: Dict[str, RichExecutableTask] = {}
            theory_file = None

            for executable_task in tasks:
                theory_file = str(executable_task.theory_file)

                # Create RichExecutableTask
                rich_executable_task = self._create_rich_executable_task(
                    executable_task, runner, execution_summary
                )
                subtasks[executable_task.task_name] = rich_executable_task

            # Create RichTask
            rich_task = RichTask(
                theory_file=theory_file or "",
                subtasks=subtasks,
            )
            rich_tasks[original_task_name] = rich_task

        return rich_tasks

    def _create_rich_executable_task(
        self,
        executable_task: ExecutableTask,
        runner: TaskRunner,
        execution_summary: ExecutionSummary,
    ) -> RichExecutableTask:
        """Create RichExecutableTask from ExecutableTask and results."""
        # Create TaskConfig
        task_config = TaskConfig(
            tamarin_alias=executable_task.tamarin_version_name,
            lemma=executable_task.lemma,
            output_theory_file=executable_task.output_file,
            output_trace_file=executable_task.traces_dir
            / f"{executable_task.task_name}.json",
            options=executable_task.tamarin_options,
            preprocessor_flags=executable_task.preprocess_flags,
            resources=Resources(
                cores=executable_task.max_cores,
                memory=executable_task.max_memory,
                timeout=executable_task.task_timeout,
            ),
        )

        # Create TaskExecMetadata
        task_result: Optional[TaskResult] = runner.task_results.get(
            executable_task.task_name
        )
        if task_result:
            task_execution_metadata = TaskExecMetadata(
                command=[],  # Would be populated during execution
                status=self._convert_task_status(task_result.status),
                cache_hit=executable_task.task_name
                in execution_summary.cached_task_ids,
                exec_start=datetime.fromtimestamp(task_result.start_time).isoformat(),
                exec_end=datetime.fromtimestamp(task_result.end_time).isoformat(),
                exec_duration_monotonic=task_result.duration,
                avg_memory=(
                    task_result.memory_stats.avg_memory_mb
                    if task_result.memory_stats
                    else 0.0
                ),
                peak_memory=(
                    task_result.memory_stats.peak_memory_mb
                    if task_result.memory_stats
                    else 0.0
                ),
            )

            # Create task result
            if task_result.status == ExecutableTaskStatus.COMPLETED:
                task_result_obj = self._create_task_succeed_result(task_result)
            else:
                task_result_obj = self._create_task_failed_result(task_result)
        else:
            # Create placeholder for missing results
            task_execution_metadata = TaskExecMetadata(
                command=[],
                status=TaskStatus.PENDING,
                cache_hit=False,
                exec_start="",
                exec_end="",
                exec_duration_monotonic=0.0,
                avg_memory=0.0,
                peak_memory=0.0,
            )
            task_result_obj = None

        return RichExecutableTask(
            task_config=task_config,
            task_execution_metadata=task_execution_metadata,
            task_result=task_result_obj,
        )

    def _convert_task_status(self, old_status: ExecutableTaskStatus) -> TaskStatus:
        """Convert ExecutableTaskStatus to BatchTaskStatus."""
        status_mapping = {
            ExecutableTaskStatus.PENDING: TaskStatus.PENDING,
            ExecutableTaskStatus.RUNNING: TaskStatus.RUNNING,
            ExecutableTaskStatus.COMPLETED: TaskStatus.COMPLETED,
            ExecutableTaskStatus.FAILED: TaskStatus.FAILED,
            ExecutableTaskStatus.TIMEOUT: TaskStatus.TIMEOUT,
            ExecutableTaskStatus.MEMORY_LIMIT_EXCEEDED: TaskStatus.MEMORY_LIMIT_EXCEEDED,
        }
        return status_mapping.get(old_status, TaskStatus.FAILED)

    def _create_task_succeed_result(self, task_result: TaskResult) -> TaskSucceedResult:
        """Create TaskSucceedResult from TaskResult."""
        # Use existing output_manager parsing logic
        parsed_result = output_manager.parse_task_result(
            task_result, f"{task_result.task_id}.spthy"
        )

        if not isinstance(parsed_result, SuccessfulTaskResult):
            return TaskSucceedResult(
                warnings=[],
                real_time_tamarin_measure=task_result.duration,
                lemma_result=LemmaResult.VERIFIED,
                steps=0,
                analysis_type="unknown",
            )

        # Extract lemma information
        lemma_name = self._extract_lemma_name_from_task_id(task_result.task_id)

        steps = 0
        analysis_type = "unknown"
        lemma_result = LemmaResult.VERIFIED

        # Check verified lemmas first
        if lemma_name in parsed_result.verified_lemma:
            lemma_info = parsed_result.verified_lemma[lemma_name]
            steps = lemma_info.steps
            analysis_type = lemma_info.analysis_type
            lemma_result = LemmaResult.VERIFIED
        # Check falsified lemmas
        elif lemma_name in parsed_result.falsified_lemma:
            lemma_info = parsed_result.falsified_lemma[lemma_name]
            steps = lemma_info.steps
            analysis_type = lemma_info.analysis_type
            lemma_result = LemmaResult.FALSIFIED
        # Check unterminated lemmas
        elif lemma_name in parsed_result.unterminated_lemma:
            lemma_result = LemmaResult.UNTERMINATED

        return TaskSucceedResult(
            warnings=parsed_result.warnings,
            real_time_tamarin_measure=parsed_result.tamarin_timing,
            lemma_result=lemma_result,
            steps=steps,
            analysis_type=analysis_type,
        )

    def _create_task_failed_result(self, task_result: TaskResult) -> TaskFailedResult:
        """Create TaskFailedResult from TaskResult."""
        # Determine error type based on task result
        if task_result.status == ExecutableTaskStatus.TIMEOUT:
            error_type = ErrorType.TIMEOUT
        elif task_result.status == ExecutableTaskStatus.MEMORY_LIMIT_EXCEEDED:
            error_type = ErrorType.MEMORY_LIMIT
        else:
            error_type = ErrorType.TAMARIN_ERROR

        return TaskFailedResult(
            return_code=str(task_result.return_code),
            error_type=error_type,
            error_description=self._get_error_description(task_result),
            last_stderr_lines=(
                task_result.stderr.split("\n")[-10:] if task_result.stderr else []
            ),
        )

    def _extract_original_task_name(self, task_name: str) -> str:
        """Extract original task name from executable task name."""
        # Format: {output_file_prefix}--{lemma_name}--{tamarin_version}
        parts = task_name.split("--")
        if len(parts) >= 3:
            # Get the base task name from the prefix
            return parts[0].split("_")[0]
        return task_name

    def _extract_lemma_name_from_task_id(self, task_id: str) -> str:
        """Extract lemma name from task ID format: prefix--lemma_name--tamarin_version"""
        parts = task_id.split("--")
        if len(parts) >= 3:
            return parts[-2]
        return task_id

    def _get_error_description(self, task_result: TaskResult) -> str:
        """Get error description from task result."""
        if task_result.status == ExecutableTaskStatus.TIMEOUT:
            return "Task timed out during execution"
        elif task_result.status == ExecutableTaskStatus.MEMORY_LIMIT_EXCEEDED:
            return "Task exceeded memory limit"
        else:
            return f"Task failed with return code {task_result.return_code}"

    async def _write_execution_report(self, batch: Batch) -> None:
        """Write execution report to JSON file."""
        try:
            # Get output directory paths
            output_paths = output_manager.get_output_paths()
            report_path = output_paths["base"] / "execution_report.json"

            # Write the batch object as JSON, excluding null fields
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(batch.model_dump_json(indent=2, exclude_none=True))

            notification_manager.success(
                f"[BatchManager] Generated execution report: {report_path}"
            )

        except Exception as e:
            notification_manager.error(
                f"[BatchManager] Failed to write execution report: {e}"
            )
            raise
