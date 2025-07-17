"""
Task runner system for coordinating the entire execution pipeline.

This module provides the TaskRunner class that manages task lifecycle,
resource allocation, scheduling coordination, and real-time progress updates
for parallel Tamarin proof execution.
"""

import asyncio
import signal
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .model.batch import (
    Batch,
    ErrorType,
    LemmaResult,
    RichExecutableTask,
    TaskFailedResult,
)
from .model.batch import TaskStatus as BatchTaskStatus
from .model.batch import (
    TaskSucceedResult,
)
from .model.executable_task import (
    ExecutableTask,
    TaskResult,
    TaskStatus,
)
from .model.tamarin_recipe import TamarinRecipe
from .modules.output_manager import SuccessfulTaskResult, output_manager
from .modules.process_manager import process_manager
from .modules.resource_manager import ResourceManager
from .modules.task_manager import TaskManager
from .utils.notifications import notification_manager


class TaskRunner:
    """
    Coordinates the entire execution pipeline for Tamarin proof tasks.

    This class manages task lifecycle from pending to completion, handles
    resource allocation and scheduling coordination, and provides real-time
    progress updates throughout the execution process.
    """

    def __init__(self, recipe: TamarinRecipe) -> None:
        """
        Initialize the TaskRunner with a recipe containing global configuration.

        Args:
            recipe: TamarinRecipe object containing global configuration and tasks
        """
        self.recipe = recipe

        # Initialize ResourceManager with recipe (will validate and potentially correct resource limits)
        self.resource_manager = ResourceManager(recipe)

        # Initialize TaskManager for execution
        self.task_manager = TaskManager()

        # Initialize OutputManager for reporting
        output_directory = Path(recipe.config.output_directory)
        output_manager.initialize(output_directory)

        # Internal state for task management
        self._pending_tasks: List[ExecutableTask] = []
        self._running_tasks: Dict[str, asyncio.Task[TaskResult]] = {}
        self._completed_tasks: Set[str] = set()
        self._failed_tasks: Set[str] = set()
        self._task_results: Dict[str, TaskResult] = {}

        # Track shutdown state
        self._shutdown_requested = False
        self._force_shutdown_requested = False
        self._signal_count = 0

    async def execute_all_tasks(self, tasks: List[ExecutableTask]) -> None:
        """
        Main orchestration method to coordinate resource allocation and task execution.

        This method manages the complete lifecycle of task execution:
        1. Initialize resource tracking for all tasks
        2. Display initial status (total tasks, available resources)
        3. Start main scheduling loop
        4. Monitor running tasks and schedule new ones as resources become available
        5. Handle task completions and resource cleanup
        6. Provide regular progress updates
        7. Generate final execution summary

        Args:
            tasks: List of ExecutableTask instances to execute

        Returns:
            ExecutionSummary: Final execution summary with statistics
        """
        notification_manager.phase_separator("Task Execution")

        if not tasks:
            notification_manager.error("[TaskRunner] No tasks provided for execution")

        # Initialize task tracking
        self._pending_tasks = tasks.copy()
        self._running_tasks.clear()
        self._completed_tasks.clear()
        self._failed_tasks.clear()
        self._task_results.clear()
        self._shutdown_requested = False

        # Set up shutdown handler
        def signal_handler(_signum: int, _frame: Any) -> None:
            self._signal_count += 1

            if self._signal_count == 1:
                notification_manager.info(
                    "[TaskRunner] Shutdown signal received (CTRL+C). Initiating graceful shutdown... \nPress CTRL+C again to force immediate termination of all tasks."
                )
                self._shutdown_requested = True
            elif self._signal_count >= 2:
                notification_manager.warning(
                    "[TaskRunner] Force shutdown signal received (CTRL+C x2). Killing all tasks immediately!"
                )
                self._force_shutdown_requested = True

        # Register signal handler for CTRL+C
        original_handler = signal.signal(signal.SIGINT, signal_handler)

        try:
            # Display initial status
            notification_manager.info(
                f"[TaskRunner] Starting execution of {len(tasks)} tasks. \n"
                f"Available resources: {self.resource_manager.get_available_cores()} cores, "
                f"{self.resource_manager.get_available_memory()}GB memory"
            )

            # Start main scheduling loop
            await self._execute_task_pool(tasks)

            # Generate final execution summary
            summary = self.task_manager.generate_execution_summary()
            notification_manager.task_execution_summary(summary)

        except Exception as e:
            notification_manager.error(
                f"[TaskRunner] Unexpected error during task execution: {e}"
            )
            # Clean up any running tasks
            if self._force_shutdown_requested:
                await self._force_kill_all_tasks()
            else:
                await self._cleanup_running_tasks()
            raise
        finally:
            # Clean up any remaining tasks if shutdown was requested
            if self._force_shutdown_requested and (
                self._running_tasks or self._pending_tasks
            ):
                await self._force_kill_all_tasks()
            elif self._shutdown_requested and self._running_tasks:
                await self._cleanup_running_tasks()

            # Restore original signal handler
            signal.signal(signal.SIGINT, original_handler)

    async def _execute_task_pool(self, all_tasks: List[ExecutableTask]) -> None:
        """
        Internal method to manage task pool execution.

        Implements the main scheduling loop:
        - Get next schedulable tasks from ResourceManager
        - Start tasks as background coroutines
        - Monitor completions and update progress
        - Release resources when tasks complete
        - Continue until all tasks are complete or shutdown is requested

        Args:
            all_tasks: Complete list of tasks to execute
        """
        last_progress_update = 0
        progress_update_interval = 3.0  # Update progress every 3 seconds

        while self._should_continue_execution():
            # Get next schedulable tasks
            schedulable_tasks = self.resource_manager.get_next_schedulable_tasks(
                self._pending_tasks
            )

            # Start new tasks as background coroutines (only if not shutting down)
            self._start_schedulable_tasks(schedulable_tasks)

            # Handle completed tasks
            await self._handle_completed_tasks(all_tasks)

            # Display progress update periodically
            current_time = asyncio.get_event_loop().time()
            if current_time - last_progress_update >= progress_update_interval:
                self._display_progress_update()
                last_progress_update = current_time

            # Check for force shutdown more frequently
            if self._force_shutdown_requested:
                break

            # Small sleep to prevent busy loop
            await asyncio.sleep(1)

        # Handle shutdown scenarios
        await self._handle_shutdown()

        # Final progress update
        self._display_progress_update()

    def _should_continue_execution(self) -> bool:
        """Check if the task pool execution should continue."""
        return (
            bool(self._pending_tasks or self._running_tasks)
            and not self._shutdown_requested
            and not self._force_shutdown_requested
        )

    def _start_schedulable_tasks(self, schedulable_tasks: List[ExecutableTask]) -> None:
        """Start schedulable tasks as background coroutines."""
        if self._shutdown_requested or self._force_shutdown_requested:
            return

        for task in schedulable_tasks:
            if self.resource_manager.allocate_resources(task):
                task_id = task.task_name

                # Create and start background coroutine
                coroutine = self._execute_single_task(task)
                asyncio_task = asyncio.create_task(coroutine)
                self._running_tasks[task_id] = asyncio_task

                # Remove from pending tasks
                self._pending_tasks.remove(task)

                notification_manager.info(f"[TaskRunner] Started task: {task_id}")

    async def _handle_completed_tasks(self, all_tasks: List[ExecutableTask]) -> None:
        """Check for and handle completed tasks."""
        # Check for completed tasks
        completed_task_ids: List[str] = []
        for task_id, asyncio_task in self._running_tasks.items():
            if asyncio_task.done():
                completed_task_ids.append(task_id)

        # Handle completed tasks
        for task_id in completed_task_ids:
            asyncio_task = self._running_tasks.pop(task_id)
            try:
                # Get the task and result
                task_result: TaskResult = await asyncio_task

                # Find the corresponding ExecutableTask
                corresponding_task: Optional[ExecutableTask] = None
                for task in all_tasks:
                    if task.task_name == task_id:
                        corresponding_task = task
                        break

                if corresponding_task:
                    self._handle_task_completion(corresponding_task, task_result)
                else:
                    notification_manager.error(
                        f"[TaskRunner] Could not find corresponding task for {task_id}"
                    )

            except Exception as e:
                notification_manager.error(
                    f"[TaskRunner] Error retrieving result for task {task_id}: {e}"
                )

    async def _handle_shutdown(self) -> None:
        """Handle shutdown scenarios."""
        if self._force_shutdown_requested:
            notification_manager.debug(
                "[TaskRunner] Force shutdown requested. Killing all running tasks immediately..."
            )
            await self._force_kill_all_tasks()
        elif self._shutdown_requested:
            notification_manager.debug(
                "[TaskRunner] Graceful shutdown requested. Waiting for running tasks to complete..."
            )
            await self._cleanup_running_tasks()

    async def _execute_single_task(self, task: ExecutableTask) -> TaskResult:
        """
        Execute a single task using the TaskManager.

        Args:
            task: The ExecutableTask to execute

        Returns:
            TaskResult: Result of the task execution
        """
        try:
            return await self.task_manager.run_executable_task(task)
        except Exception as e:
            # Create error result if task execution fails unexpectedly
            task_id = task.task_name
            notification_manager.error(
                f"[TaskRunner] Unexpected error executing task {task_id}: {e}"
            )

            # Create a failed TaskResult
            current_time = asyncio.get_event_loop().time()
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                return_code=-1,
                stdout="",
                stderr=str(e),
                start_time=current_time,
                end_time=current_time,
                duration=0.0,
            )

    def _handle_task_completion(self, task: ExecutableTask, result: TaskResult) -> None:
        """
        Handle individual task completion.

        - Release resources via ResourceManager
        - Log completion status
        - Update internal tracking

        Args:
            task: The ExecutableTask that completed
            result: The TaskResult from execution
        """
        task_id = task.task_name

        # Release resources
        self.resource_manager.release_resources(task)

        # Update internal tracking
        self._task_results[task_id] = result

        if result.status == TaskStatus.COMPLETED:
            self._completed_tasks.add(task_id)
            notification_manager.success(
                f"[TaskRunner] Task completed successfully: {task_id} (duration: {result.duration:.2f}s)"
            )
        elif result.status == TaskStatus.TIMEOUT:
            self._failed_tasks.add(task_id)
            notification_manager.warning(
                f"[TaskRunner] Task timed out: {task_id} (duration: {result.duration:.2f}s)"
            )
        elif result.status == TaskStatus.MEMORY_LIMIT_EXCEEDED:
            self._failed_tasks.add(task_id)
            notification_manager.warning(
                f"[TaskRunner] Task exceeded memory limit: {task_id} (duration: {result.duration:.2f}s)"
            )
        else:
            self._failed_tasks.add(task_id)
            notification_manager.error(
                f"[TaskRunner] Task failed: {task_id} (status: {result.status.value}, "
                f"return_code: {result.return_code}, duration: {result.duration:.2f}s)"
            )

    def _display_progress_update(self) -> None:
        """
        Display real-time progress updates.

        Shows:
        - Running/queued/completed/failed counts
        - Resource utilization
        - Uses notification_manager for output
        """
        total_tasks = (
            len(self._pending_tasks)
            + len(self._running_tasks)
            + len(self._completed_tasks)
            + len(self._failed_tasks)
        )
        running_count = len(self._running_tasks)
        pending_count = len(self._pending_tasks)
        completed_count = len(self._completed_tasks)
        failed_count = len(self._failed_tasks)

        # Resource utilization
        allocated_cores = self.resource_manager.get_allocated_cores()
        total_cores = self.resource_manager.global_max_cores
        allocated_memory = self.resource_manager.get_allocated_memory()
        total_memory = self.resource_manager.global_max_memory

        progress_msg = (
            f"[TaskRunner] Progress: {completed_count + failed_count}/{total_tasks} complete "
            f"(Running: {running_count}, Pending: {pending_count}, "
            f"Completed: {completed_count}, Failed: {failed_count}) | "
            f"Allocated: {allocated_cores}/{total_cores} cores, "
            f"{allocated_memory}/{total_memory}GB memory"
        )

        notification_manager.info(progress_msg)

        task_msg = (
            f"[TaskRunner] Running tasks: {', '.join(self._running_tasks.keys())}"
            if self._running_tasks
            else "No running tasks"
        )

        notification_manager.info(task_msg)

    async def _cleanup_running_tasks(self) -> None:
        """
        Clean up running tasks during graceful shutdown.

        Waits for currently running tasks to complete and releases their resources.
        """
        if not self._running_tasks:
            return

        notification_manager.info(
            f"[TaskRunner] Waiting for {len(self._running_tasks)} running tasks to complete..."
        )

        # Wait for all running tasks to complete
        running_tasks: List[asyncio.Task[TaskResult]] = list(
            self._running_tasks.values()
        )
        if running_tasks:
            # Wait for tasks currently running
            await asyncio.gather(*running_tasks, return_exceptions=True)

        # Clear tracking
        self._running_tasks.clear()
        self._pending_tasks.clear()

        notification_manager.info("[TaskRunner] Graceful shutdown cleanup completed")

    async def _force_kill_all_tasks(self) -> None:
        """
        Force kill all running tasks immediately.

        Cancels all asyncio tasks and kills underlying processes via ProcessManager.
        """
        if not self._running_tasks:
            return

        # Cancel all asyncio tasks immediately
        running_tasks: List[asyncio.Task[TaskResult]] = list(
            self._running_tasks.values()
        )

        for task in running_tasks:
            if not task.done():
                task.cancel()

        # Force kill all processes via ProcessManager
        await process_manager.kill_all_processes()

        # Wait briefly for cancellations to complete
        if running_tasks:
            _, pending = await asyncio.wait(running_tasks, timeout=5.0)
            if pending:
                notification_manager.warning(
                    "[TaskRunner] Some tasks did not respond to cancellation within timeout"
                )

        # Clear all tracking - both running and pending tasks
        self._running_tasks.clear()
        self._pending_tasks.clear()

        notification_manager.info("[TaskRunner] Force shutdown cleanup completed")

    async def execute_batch(self, batch: Batch) -> Batch:
        """
        Execute tasks from a Batch model and populate execution metadata.

        This method is the new unified way to execute tasks using the Batch model.
        It converts RichExecutableTask objects to ExecutableTask objects, executes them,
        and then populates the batch with execution results.

        Args:
            batch: Batch object containing tasks to execute

        Returns:
            Updated Batch object with execution results
        """
        import time

        notification_manager.phase_separator("Batch Execution")

        if not batch.tasks:
            notification_manager.error("[TaskRunner] No tasks provided for execution")
            return batch

        # Record start time
        start_time = time.time()

        # Convert RichExecutableTask objects to ExecutableTask objects
        executable_tasks: List[ExecutableTask] = []
        for _, rich_task in batch.tasks.items():
            # Extract all RichExecutableTask objects from subtasks
            for subtask_id, rich_executable_task in rich_task.subtasks.items():
                executable_task = self._convert_rich_to_executable_task(
                    rich_executable_task, rich_task.theory_file
                )
                # Set the task name to match the subtask ID
                executable_task.task_name = subtask_id
                executable_tasks.append(executable_task)

        # Execute tasks using the existing execution pipeline
        await self.execute_all_tasks(executable_tasks)

        # Record end time
        end_time = time.time()
        total_runtime = end_time - start_time

        # Update batch with execution results
        await self._update_batch_with_results(batch, total_runtime)

        return batch

    def _convert_rich_to_executable_task(
        self, rich_task: RichExecutableTask, theory_file: str
    ) -> ExecutableTask:
        """
        Convert a RichExecutableTask to an ExecutableTask for execution.

        Args:
            rich_task: RichExecutableTask to convert
            theory_file: Path to the theory file (from parent RichTask)

        Returns:
            ExecutableTask ready for execution
        """
        task_config = rich_task.task_config

        # Create ExecutableTask from the resolved task config
        executable_task = ExecutableTask(
            task_name=f"{task_config.lemma}--{task_config.tamarin_alias}",  # Will be updated with unique ID
            tamarin_version_name=task_config.tamarin_alias,
            tamarin_executable=Path(theory_file).parent
            / "tamarin",  # This will be resolved properly
            theory_file=Path(theory_file),
            output_file=task_config.output_theory_file,
            lemma=task_config.lemma,
            tamarin_options=task_config.options,
            preprocess_flags=task_config.preprocessor_flags,
            max_cores=task_config.resources.cores,
            max_memory=task_config.resources.memory,
            task_timeout=task_config.resources.timeout,
            traces_dir=task_config.output_trace_file.parent,
        )

        # Set tamarin executable path based on the recipe's tamarin_versions
        for version_name, version_info in self.recipe.tamarin_versions.items():
            if version_name == task_config.tamarin_alias:
                from .utils.system_resources import resolve_executable_path

                executable_task.tamarin_executable = resolve_executable_path(
                    version_info.path
                )
                break

        return executable_task

    async def _update_batch_with_results(
        self, batch: Batch, total_runtime: float
    ) -> None:
        """
        Update the Batch object with execution results.

        Args:
            batch: Batch object to update
            total_runtime: Total runtime in seconds
        """
        from datetime import datetime

        # Update global execution metadata
        total_successes = len(self._completed_tasks)
        total_failures = len(self._failed_tasks)

        # Get cached tasks information through proper method
        execution_summary = self.task_manager.generate_execution_summary()
        total_cache_hit = execution_summary.cached_tasks

        # Calculate total memory usage (sum of peak memory for all tasks)
        total_memory = 0
        for task_result in self._task_results.values():
            if task_result.memory_stats:
                total_memory += task_result.memory_stats.peak_memory_mb

        batch.execution_metadata.total_successes = total_successes
        batch.execution_metadata.total_failures = total_failures
        batch.execution_metadata.total_cache_hit = total_cache_hit
        batch.execution_metadata.total_runtime = total_runtime
        batch.execution_metadata.total_memory = total_memory
        batch.execution_metadata.max_runtime = max(
            (task_result.duration for task_result in self._task_results.values()),
            default=0,
        )
        batch.execution_metadata.max_memory = max(
            (
                task_result.memory_stats.peak_memory_mb
                for task_result in self._task_results.values()
                if task_result.memory_stats
            ),
            default=0,
        )

        # Update individual task results
        for _, rich_task in batch.tasks.items():
            # Update subtasks with their results
            for subtask_id, rich_executable_task in rich_task.subtasks.items():
                # Find the corresponding task result
                task_result = self._task_results.get(subtask_id)
                if task_result:
                    # Update execution metadata
                    rich_executable_task.task_execution_metadata.status = (
                        self._convert_task_status(task_result.status)
                    )
                    rich_executable_task.task_execution_metadata.exec_start = (
                        datetime.fromtimestamp(task_result.start_time).isoformat()
                    )
                    rich_executable_task.task_execution_metadata.exec_end = (
                        datetime.fromtimestamp(task_result.end_time).isoformat()
                    )
                    rich_executable_task.task_execution_metadata.exec_duration_monotonic = (
                        task_result.duration
                    )
                    # Use execution summary to check if task was cached
                    execution_summary = self.task_manager.generate_execution_summary()
                    rich_executable_task.task_execution_metadata.cache_hit = (
                        subtask_id in execution_summary.cached_task_ids
                    )

                    # Use output_manager to get properly parsed memory statistics
                    parsed_result = output_manager.parse_task_result(
                        task_result, f"{task_result.task_id}.spthy"
                    )

                    if isinstance(parsed_result, SuccessfulTaskResult):
                        rich_executable_task.task_execution_metadata.avg_memory = (
                            parsed_result.wrapper_measures.avg_memory
                        )
                        rich_executable_task.task_execution_metadata.peak_memory = (
                            parsed_result.wrapper_measures.peak_memory
                        )
                    elif task_result.memory_stats:
                        # Fallback to raw memory stats if parsing fails
                        rich_executable_task.task_execution_metadata.avg_memory = (
                            task_result.memory_stats.avg_memory_mb
                        )
                        rich_executable_task.task_execution_metadata.peak_memory = (
                            task_result.memory_stats.peak_memory_mb
                        )

                    # Create task result based on success/failure
                    if task_result.status == TaskStatus.COMPLETED:
                        rich_executable_task.task_result = (
                            self._create_task_succeed_result(task_result)
                        )
                    else:
                        rich_executable_task.task_result = (
                            self._create_task_failed_result(task_result)
                        )

    def _convert_task_status(self, old_status: TaskStatus) -> BatchTaskStatus:
        """Convert TaskStatus to BatchTaskStatus."""
        status_mapping = {
            TaskStatus.PENDING: BatchTaskStatus.PENDING,
            TaskStatus.RUNNING: BatchTaskStatus.RUNNING,
            TaskStatus.COMPLETED: BatchTaskStatus.COMPLETED,
            TaskStatus.FAILED: BatchTaskStatus.FAILED,
            TaskStatus.TIMEOUT: BatchTaskStatus.TIMEOUT,
            TaskStatus.MEMORY_LIMIT_EXCEEDED: BatchTaskStatus.MEMORY_LIMIT_EXCEEDED,
        }
        return status_mapping.get(old_status, BatchTaskStatus.FAILED)

    def _create_task_succeed_result(self, task_result: TaskResult) -> TaskSucceedResult:
        """Create TaskSucceedResult from TaskResult using existing output_manager parsing."""
        # Use the existing output_manager parsing logic to get properly parsed data
        parsed_result = output_manager.parse_task_result(
            task_result, f"{task_result.task_id}.spthy"  # output_file_name
        )

        # Ensure we have a successful result
        if not isinstance(parsed_result, SuccessfulTaskResult):
            # This shouldn't happen for successful tasks, but handle gracefully
            return TaskSucceedResult(
                warnings=[],
                real_time_tamarin_measure=task_result.duration,
                lemma_result=LemmaResult.VERIFIED,
                steps=0,
                analysis_type="unknown",
            )

        # Extract lemma information for the current task
        # The task_result.task_id should match the lemma name pattern
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
            # For unterminated lemmas, we don't have steps/analysis_type from the parser

        return TaskSucceedResult(
            warnings=parsed_result.warnings,
            real_time_tamarin_measure=parsed_result.tamarin_timing,
            lemma_result=lemma_result,
            steps=steps,
            analysis_type=analysis_type,
        )

    def _extract_lemma_name_from_task_id(self, task_id: str) -> str:
        """Extract lemma name from task ID format: prefix--lemma_name--tamarin_version"""
        # Task ID format: {output_file_prefix}--{lemma_name}--{tamarin_version}
        parts = task_id.split("--")
        if len(parts) >= 3:
            # The lemma name is the second-to-last part before the tamarin version
            return parts[-2]
        return task_id  # Fallback to full task_id if parsing fails

    def _create_task_failed_result(self, task_result: TaskResult) -> TaskFailedResult:
        """Create TaskFailedResult from TaskResult."""
        # Determine error type based on task result
        if task_result.status == TaskStatus.TIMEOUT:
            error_type = ErrorType.TIMEOUT
        elif task_result.status == TaskStatus.MEMORY_LIMIT_EXCEEDED:
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

    def _get_error_description(self, task_result: TaskResult) -> str:
        """Get error description from task result."""
        if task_result.status == TaskStatus.TIMEOUT:
            return "Task timed out during execution"
        elif task_result.status == TaskStatus.MEMORY_LIMIT_EXCEEDED:
            return "Task exceeded memory limit"
        else:
            return f"Task failed with return code {task_result.return_code}"
