"""
Task runner system for coordinating the entire execution pipeline.

This module provides the TaskRunner class that manages task lifecycle,
resource allocation, scheduling coordination, and real-time progress updates
for parallel Tamarin proof execution.
"""

import asyncio
import signal
from typing import Any, Dict, List, Optional, Set

from model.executable_task import (
    ExecutableTask,
    ExecutionSummary,
    TaskResult,
    TaskStatus,
)
from model.tamarin_recipe import GlobalConfig
from modules.resource_manager import ResourceManager
from modules.task_manager import TaskManager
from utils.notifications import notification_manager


class TaskRunner:
    """
    Coordinates the entire execution pipeline for Tamarin proof tasks.

    This class manages task lifecycle from pending to completion, handles
    resource allocation and scheduling coordination, and provides real-time
    progress updates throughout the execution process.
    """

    def __init__(self, global_config: GlobalConfig) -> None:
        """
        Initialize the TaskRunner with global configuration.

        Args:
            global_config: Global configuration settings containing resource limits
        """
        self.global_config = global_config

        # Initialize ResourceManager with global limits
        self.resource_manager = ResourceManager(
            global_max_cores=global_config.global_max_cores,
            global_max_memory=global_config.global_max_memory,
        )

        # Initialize TaskManager for execution
        self.task_manager = TaskManager()

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
        def signal_handler(signum: int, frame: Any) -> None:
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
                f"[TaskRunner] Starting execution of {len(tasks)} tasks. "
                f"Available resources: {self.resource_manager.get_available_cores()} cores, "
                f"{self.resource_manager.get_available_memory()}GB memory"
            )

            # Start main scheduling loop
            await self._execute_task_pool(tasks)

            # Summary Phase
            notification_manager.phase_separator("Summary")

            # Generate final execution summary
            summary = self.task_manager.generate_execution_summary()

            # Display enhanced final statistics
            self._display_enhanced_summary(summary)

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

        while (
            (self._pending_tasks or self._running_tasks)
            and not self._shutdown_requested
            and not self._force_shutdown_requested
        ):
            # Get next schedulable tasks
            schedulable_tasks = self.resource_manager.get_next_schedulable_tasks(
                self._pending_tasks
            )

            # Start new tasks as background coroutines (only if not shutting down)
            if not self._shutdown_requested and not self._force_shutdown_requested:
                for task in schedulable_tasks:
                    if self.resource_manager.allocate_resources(task):
                        task_id = self._get_task_id(task)

                        # Create and start background coroutine
                        coroutine = self._execute_single_task(task)
                        asyncio_task = asyncio.create_task(coroutine)
                        self._running_tasks[task_id] = asyncio_task

                        # Remove from pending tasks
                        self._pending_tasks.remove(task)

                        notification_manager.info(
                            f"[TaskRunner] Started task: {task_id}"
                        )

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
                        if self._get_task_id(task) == task_id:
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

        # Final progress update
        self._display_progress_update()

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
            task_id = self._get_task_id(task)
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
        task_id = self._get_task_id(task)

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
            notification_manager.warning(
                f"[TaskRunner] Task timed out: {task_id} (duration: {result.duration:.2f}s)"
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
            try:
                # Wait for tasks with a reasonable timeout
                await asyncio.wait_for(
                    asyncio.gather(*running_tasks, return_exceptions=True), timeout=30.0
                )
            except asyncio.TimeoutError:
                notification_manager.warning(
                    "[TaskRunner] Some tasks did not complete within timeout during graceful shutdown"
                )

        # Clear tracking
        self._running_tasks.clear()

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
        from modules.process_manager import process_manager

        await process_manager.kill_all_processes()

        # Wait briefly for cancellations to complete
        if running_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*running_tasks, return_exceptions=True), timeout=5.0
                )
            except asyncio.TimeoutError:
                notification_manager.warning(
                    "[TaskRunner] Some tasks did not respond to cancellation within timeout"
                )

        # Clear all tracking - both running and pending tasks
        self._running_tasks.clear()
        self._pending_tasks.clear()

        notification_manager.info("[TaskRunner] Force shutdown cleanup completed")

    def _display_enhanced_summary(self, summary: ExecutionSummary) -> None:
        """
        Display an enhanced execution summary with detailed statistics.

        Args:
            summary: ExecutionSummary object with execution statistics
        """
        # Count different types of failures
        timeout_tasks = sum(
            1 for result in summary.task_results if result.status == TaskStatus.TIMEOUT
        )
        oom_tasks = sum(
            1
            for result in summary.task_results
            if "out of memory" in result.stderr.lower()
            or "memory" in result.stderr.lower()
        )
        failed_tasks_other = summary.failed_tasks - timeout_tasks - oom_tasks

        # Calculate percentages
        total = summary.total_tasks
        success_percent = (summary.successful_tasks / total * 100) if total > 0 else 0
        failed_percent = (failed_tasks_other / total * 100) if total > 0 else 0
        timeout_percent = (timeout_tasks / total * 100) if total > 0 else 0
        oom_percent = (oom_tasks / total * 100) if total > 0 else 0

        # Display main statistics
        notification_manager.success(
            f"Successful Tasks: {summary.successful_tasks}/{total} ({success_percent:.1f}%)"
        )

        if failed_tasks_other > 0:
            notification_manager.error(
                f"Failed Tasks: {failed_tasks_other}/{total} ({failed_percent:.1f}%)"
            )

        if timeout_tasks > 0:
            notification_manager.warning(
                f"Timed Out Tasks: {timeout_tasks}/{total} ({timeout_percent:.1f}%)"
            )

        if oom_tasks > 0:
            notification_manager.error(
                f"Out of Memory Tasks: {oom_tasks}/{total} ({oom_percent:.1f}%)"
            )

        notification_manager.info(
            f"Total Duration: {summary.total_duration:.2f} seconds"
        )

        # Display failed task details if any
        failed_results = [
            r
            for r in summary.task_results
            if r.status in [TaskStatus.FAILED, TaskStatus.TIMEOUT]
        ]
        if failed_results:
            notification_manager.warning("Failed Task Details:")
            for result in failed_results[:5]:  # Show max 5 failed tasks
                error_type = (
                    "Timeout" if result.status == TaskStatus.TIMEOUT else "Error"
                )
                brief_error = (
                    result.stderr[:100] + "..."
                    if len(result.stderr) > 100
                    else result.stderr
                )
                notification_manager.error(
                    f"  • {result.task_id}: {error_type} - {brief_error}"
                )

            if len(failed_results) > 5:
                notification_manager.info(
                    f"  ... and {len(failed_results) - 5} more failed tasks"
                )

    def _get_task_id(self, task: ExecutableTask) -> str:
        """
        Generate a unique identifier for a task.

        Args:
            task: The ExecutableTask to generate an ID for

        Returns:
            Unique string identifier combining task name and tamarin version
        """
        return f"{task.tamarin_version_name}_{task.task_name}"
