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

from .model.executable_task import (
    ExecutableTask,
    TaskResult,
    TaskStatus,
)
from .model.tamarin_recipe import SchedulingStrategy, TamarinRecipe
from .modules.output_manager import output_manager
from .modules.process_manager import process_manager
from .modules.resource_manager import ResourceManager
from .modules.task_manager import TaskManager
from .utils.dot_utils import cleanup_empty_trace_files
from .utils.notifications import notification_manager


class TaskRunner:
    """
    Coordinates the entire execution pipeline for Tamarin proof tasks.

    This class manages task lifecycle from pending to completion, handles
    resource allocation and scheduling coordination, and provides real-time
    progress updates throughout the execution process.
    """

    def __init__(
        self,
        recipe: TamarinRecipe,
        scheduler: SchedulingStrategy = SchedulingStrategy.FIFO,
    ) -> None:
        """
        Initialize the TaskRunner with a recipe containing global configuration.

        Args:
            recipe: TamarinRecipe object containing global configuration and tasks
            scheduler: Task scheduling strategy to use
        """
        self.recipe = recipe

        # Initialize ResourceManager with recipe and scheduler (will validate and potentially correct resource limits)
        self.resource_manager = ResourceManager(recipe, scheduler)

        # Initialize TaskManager for execution
        self.task_manager = TaskManager()

        # Initialize OutputManager for reporting
        output_directory = Path(recipe.config.output_directory)
        output_manager.initialize(output_directory)

        # Update recipe config with actual output directory (may have changed due to timestamping)
        actual_output_paths = output_manager.get_output_paths()
        self.recipe.config.output_directory = str(actual_output_paths["base"])

        # Internal state for task management
        self._pending_tasks: List[ExecutableTask] = []
        self._running_tasks: Dict[str, asyncio.Task[TaskResult]] = {}
        self._completed_tasks: Set[str] = set()
        self._failed_tasks: Set[str] = set()
        self._task_results: Dict[str, TaskResult] = {}
        self.completed_tasks: Set[str] = set()
        self.failed_tasks: Set[str] = set()
        self.task_results: Dict[str, TaskResult] = {}

        # Track shutdown state
        self._shutdown_requested = False
        self._force_shutdown_requested = False
        self._signal_count = 0
        self._signal_interrupted_tasks: Set[str] = set()

        # Task completion event for immediate scheduling (will be set during execution)
        self._task_completed_event: Optional[asyncio.Event] = None

        # Store scheduler mode for logging
        self.scheduler = scheduler

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
        self.completed_tasks.clear()
        self.failed_tasks.clear()
        self.task_results.clear()
        self._shutdown_requested = False

        # Initialize task completion event for this execution
        self._task_completed_event = asyncio.Event()

        # Set up shutdown handler
        def signal_handler(signum: int, frame: Any) -> None:
            _ = signum, frame  # Suppress unused parameter warnings
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
                f"[TaskRunner] Starting execution of {len(tasks)} tasks using {self.scheduler.value} scheduling strategy. \n"
                f"Available resources: {self.resource_manager.get_available_cores()} cores, "
                f"{self.resource_manager.get_available_memory()}GB memory"
            )

            # Start main scheduling loop
            await self._execute_task_pool(tasks)

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
        Internal method to manage task pool execution with event-driven scheduling.

        Implements improved scheduling loop:
        - Event-driven scheduling (immediate on task completion)
        - Adaptive sleep intervals based on activity
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

        # Try initial scheduling
        await self._schedule_available_tasks()

        while self._should_continue_execution():
            # Wait for task completion event or timeout
            # Use shorter timeout when tasks are running (more responsive)
            # Use longer timeout when no tasks running (less CPU usage)
            timeout = 0.1 if self._running_tasks else 1.0

            try:
                if self._task_completed_event:
                    await asyncio.wait_for(
                        self._task_completed_event.wait(), timeout=timeout
                    )
                    self._task_completed_event.clear()
                else:
                    await asyncio.sleep(timeout)
            except asyncio.TimeoutError:
                pass  # Normal timeout, continue with periodic checks

            # Handle completed tasks (this may free up resources)
            await self._handle_completed_tasks(all_tasks)

            # Try to schedule new tasks if resources are available
            await self._schedule_available_tasks()

            # Display progress update periodically
            current_time = asyncio.get_event_loop().time()
            if current_time - last_progress_update >= progress_update_interval:
                self._display_progress_update()
                last_progress_update = current_time

            # Check for force shutdown more frequently
            if self._force_shutdown_requested:
                break

        # Handle shutdown scenarios
        await self._handle_shutdown()

        # Final progress update
        self._display_progress_update()

    async def _schedule_available_tasks(self) -> None:
        """Schedule available tasks if resources permit."""
        if self._shutdown_requested or self._force_shutdown_requested:
            return

        # Get next schedulable tasks
        schedulable_tasks = self.resource_manager.get_next_schedulable_tasks(
            self._pending_tasks
        )

        # Start new tasks as background coroutines
        self._start_schedulable_tasks(schedulable_tasks)

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

                notification_manager.info(f"[TaskRunner] Started subtask: {task_id}")

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
                    # Check if task was signal interrupted and update status
                    if task_id in self._signal_interrupted_tasks:
                        task_result.status = TaskStatus.SIGNAL_INTERRUPTED
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
            # Mark running tasks as signal interrupted before killing
            for task_id in self._running_tasks.keys():
                self._signal_interrupted_tasks.add(task_id)
            await self._force_kill_all_tasks()
        elif self._shutdown_requested:
            notification_manager.debug(
                "[TaskRunner] Graceful shutdown requested. Waiting for running tasks to complete..."
            )
            # Mark running tasks as signal interrupted for graceful shutdown too
            for task_id in self._running_tasks.keys():
                self._signal_interrupted_tasks.add(task_id)
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

        # Clean up empty trace files
        try:
            cleanup_empty_trace_files(task.traces_dir)
        except Exception as e:
            notification_manager.debug(
                f"[TaskRunner] Failed to clean up trace files for task {task_id}: {e}"
            )

        # Update internal tracking
        self._task_results[task_id] = result
        self.task_results[task_id] = result

        # Signal that a task has completed (for event-driven scheduling)
        if self._task_completed_event:
            self._task_completed_event.set()

        if result.status == TaskStatus.COMPLETED:
            self._completed_tasks.add(task_id)
            self.completed_tasks.add(task_id)
            notification_manager.success(
                f"[TaskRunner] Task completed successfully: {task_id} (duration: {result.duration:.2f}s)"
            )
        elif result.status == TaskStatus.TIMEOUT:
            self._failed_tasks.add(task_id)
            self.failed_tasks.add(task_id)
            notification_manager.warning(
                f"[TaskRunner] Task timed out: {task_id} (duration: {result.duration:.2f}s)"
            )
        elif result.status == TaskStatus.MEMORY_LIMIT_EXCEEDED:
            self._failed_tasks.add(task_id)
            self.failed_tasks.add(task_id)
            notification_manager.warning(
                f"[TaskRunner] Task exceeded memory limit: {task_id} (duration: {result.duration:.2f}s)"
            )
        elif result.status == TaskStatus.SIGNAL_INTERRUPTED:
            self._failed_tasks.add(task_id)
            self.failed_tasks.add(task_id)
            notification_manager.warning(
                f"[TaskRunner] Task interrupted by signal: {task_id} (duration: {result.duration:.2f}s)"
            )
        else:
            self._failed_tasks.add(task_id)
            self.failed_tasks.add(task_id)
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
        Force kill all running tasks with brief grace period.

        Gives tasks a 2-second grace period to complete naturally before
        canceling asyncio tasks and killing underlying processes.
        """
        if not self._running_tasks:
            return

        running_tasks: List[asyncio.Task[TaskResult]] = list(
            self._running_tasks.values()
        )

        # Give tasks a brief grace period to complete naturally
        notification_manager.info(
            f"[TaskRunner] Giving {len(running_tasks)} running tasks 2 seconds to complete before force termination..."
        )

        if running_tasks:
            done, pending = await asyncio.wait(running_tasks, timeout=2.0)

            # Process any tasks that completed during grace period
            for task in done:
                if not task.cancelled():
                    try:
                        # Task completed naturally - let normal completion handling work
                        await task
                    except Exception:
                        # Task failed during grace period, still better than cancellation
                        pass

            # Cancel remaining tasks that didn't complete
            for task in pending:
                if not task.done():
                    task.cancel()

            # Force kill all remaining processes via ProcessManager
            await process_manager.kill_all_processes()

            # Wait briefly for cancellations to complete
            if pending:
                _, still_pending = await asyncio.wait(pending, timeout=3.0)
                if still_pending:
                    notification_manager.warning(
                        f"[TaskRunner] {len(still_pending)} tasks did not respond to cancellation within timeout"
                    )

        # Clear all tracking - both running and pending tasks
        self._running_tasks.clear()
        self._pending_tasks.clear()

        notification_manager.info("[TaskRunner] Force shutdown cleanup completed")
