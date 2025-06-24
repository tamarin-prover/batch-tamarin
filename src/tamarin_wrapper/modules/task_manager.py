"""
Task manager for the Tamarin Wrapper.

This module provides task execution with progress reporting capabilities,
built on top of the ProcessManager for actual process execution.
"""

import asyncio
from typing import Dict

from ..model.executable_task import (
    ExecutableTask,
    ExecutionSummary,
    ProgressReport,
    TaskResult,
    TaskStatus,
)
from ..utils.notifications import notification_manager
from .output_manager import output_manager
from .process_manager import process_manager


class TaskManager:
    """
    Task manager with progress reporting capabilities.

    Manages execution of ExecutableTasks with status tracking, timing,
    and progress reporting while using ProcessManager for actual execution.
    """

    def __init__(self):
        # Task tracking for progress reporting
        self._task_status: Dict[str, TaskStatus] = {}
        self._task_results: Dict[str, TaskResult] = {}
        self._task_start_times: Dict[str, float] = {}

    async def run_executable_task(self, task: ExecutableTask) -> TaskResult:
        """
        Execute an ExecutableTask using task.to_command().

        Track status changes and timing, return TaskResult with complete execution information.
        Uses existing run_command method internally.

        Args:
            task: ExecutableTask to execute

        Returns:
            TaskResult with complete execution information
        """
        # Generate task identifier
        task_id = task.task_name

        # Initialize task tracking
        start_time = asyncio.get_event_loop().time()
        self._task_start_times[task_id] = start_time
        self.update_task_status(task_id, TaskStatus.PENDING)

        # Convert task to command
        command = task.to_command()
        executable = task.tamarin_executable
        args = command[1:]  # Remove the executable from the command list

        # Update status to running
        self.update_task_status(task_id, TaskStatus.RUNNING)

        # Notify start of execution
        notification_manager.debug(f"[TaskManager] Starting task: {task_id}")

        try:
            # Execute the command using existing run_command method (now returns memory stats)
            # Convert memory limit from GB to MB
            memory_limit_mb = float(task.max_memory) * 1024
            return_code, stdout, stderr, memory_stats = (
                await process_manager.run_command(
                    executable,
                    args,
                    timeout=float(task.task_timeout),
                    memory_limit_mb=memory_limit_mb,
                )
            )

            # Determine final status based on return code
            end_time = asyncio.get_event_loop().time()
            duration = end_time - start_time

            if return_code == 0:
                status = TaskStatus.COMPLETED
            elif return_code == -1 and stderr == "Process timed out":
                status = TaskStatus.TIMEOUT
            elif return_code == -2 and stderr == "Process exceeded memory limit":
                status = TaskStatus.MEMORY_LIMIT_EXCEEDED
            else:
                status = TaskStatus.FAILED

            # Create task result with memory statistics
            task_result = TaskResult(
                task_id=task_id,
                status=status,
                return_code=return_code,
                stdout=stdout,
                stderr=stderr,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                memory_stats=memory_stats,
            )

            # Update tracking
            self._task_status[task_id] = status
            self._task_results[task_id] = task_result

            # Process result with output manager if initialized
            if output_manager.is_initialized():
                try:
                    output_file_name = task.output_file.name
                    output_manager.process_task_result(task_result, output_file_name)
                except Exception as e:
                    notification_manager.error(
                        f"[TaskManager] Failed to process task result with output manager: {e}"
                    )

            return task_result

        except Exception as e:
            # Handle unexpected errors
            end_time = asyncio.get_event_loop().time()
            duration = end_time - start_time

            notification_manager.error(
                f"[TaskManager] Unexpected error in task {task_id}: {e}"
            )

            task_result = TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                return_code=-1,
                stdout="",
                stderr=str(e),
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                memory_stats=None,
            )

            # Update tracking
            self._task_status[task_id] = TaskStatus.FAILED
            self._task_results[task_id] = task_result

            # Process result with output manager if initialized
            if output_manager.is_initialized():
                try:
                    output_file_name = task.output_file.name
                    output_manager.process_task_result(task_result, output_file_name)
                except Exception as e:
                    notification_manager.error(
                        f"[TaskManager] Failed to process task result with output manager: {e}"
                    )

            return task_result

    def get_execution_progress(self) -> ProgressReport:
        """
        Return current progress status.

        Count tasks in each status category.

        Returns:
            ProgressReport with current progress status
        """
        current_time = asyncio.get_event_loop().time()

        # Count tasks by status
        pending_tasks = sum(
            1 for status in self._task_status.values() if status == TaskStatus.PENDING
        )
        running_tasks = sum(
            1 for status in self._task_status.values() if status == TaskStatus.RUNNING
        )
        completed_tasks = sum(
            1 for status in self._task_status.values() if status == TaskStatus.COMPLETED
        )
        failed_tasks = sum(
            1
            for status in self._task_status.values()
            if status
            in [TaskStatus.FAILED, TaskStatus.TIMEOUT, TaskStatus.MEMORY_LIMIT_EXCEEDED]
        )

        total_tasks = len(self._task_status)

        return ProgressReport(
            total_tasks=total_tasks,
            pending_tasks=pending_tasks,
            running_tasks=running_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            current_time=current_time,
        )

    def update_task_status(self, task_id: str, status: TaskStatus) -> None:
        """
        Update task status manually.

        Update timestamps appropriately.

        Args:
            task_id: Identifier of the task
            status: New status to set
        """
        self._task_status[task_id] = status

        # Update start time if transitioning to RUNNING
        if status == TaskStatus.RUNNING and task_id not in self._task_start_times:
            self._task_start_times[task_id] = asyncio.get_event_loop().time()

        # Notify status change
        notification_manager.debug(
            f"[TaskManager] Task {task_id} status updated to {status.value}"
        )

    def generate_execution_summary(self) -> ExecutionSummary:
        """
        Generate final execution summary.

        Calculate total duration and success rates.

        Returns:
            ExecutionSummary with complete execution statistics
        """
        task_results = list(self._task_results.values())
        total_tasks = len(task_results)

        if total_tasks == 0:
            return ExecutionSummary(
                total_tasks=0,
                successful_tasks=0,
                failed_tasks=0,
                total_duration=0.0,
                task_results=[],
            )

        # Count successful and failed tasks
        successful_tasks = sum(
            1 for result in task_results if result.status == TaskStatus.COMPLETED
        )
        failed_tasks = sum(
            1
            for result in task_results
            if result.status
            in [TaskStatus.FAILED, TaskStatus.TIMEOUT, TaskStatus.MEMORY_LIMIT_EXCEEDED]
        )

        # Calculate total duration (earliest start to latest end)
        if task_results:
            earliest_start = min(result.start_time for result in task_results)
            latest_end = max(result.end_time for result in task_results)
            total_duration = latest_end - earliest_start
        else:
            total_duration = 0.0

        return ExecutionSummary(
            total_tasks=total_tasks,
            successful_tasks=successful_tasks,
            failed_tasks=failed_tasks,
            total_duration=total_duration,
            task_results=task_results,
        )

    def get_task_results(self) -> Dict[str, TaskResult]:
        """
        Get all task results.

        Returns:
            Dictionary mapping task_id to TaskResult
        """
        return self._task_results.copy()

    def get_task_status(self, task_id: str) -> TaskStatus:
        """
        Get status of a specific task.

        Args:
            task_id: Identifier of the task

        Returns:
            TaskStatus of the specified task

        Raises:
            KeyError: If task_id is not found
        """
        return self._task_status[task_id]

    def clear_completed_tasks(self) -> None:
        """
        Clear completed and failed tasks from tracking.

        Keeps only pending and running tasks.
        """
        completed_statuses = {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.TIMEOUT,
            TaskStatus.MEMORY_LIMIT_EXCEEDED,
        }

        # Get task IDs to remove
        tasks_to_remove = [
            task_id
            for task_id, status in self._task_status.items()
            if status in completed_statuses
        ]

        # Remove from all tracking dictionaries
        for task_id in tasks_to_remove:
            self._task_status.pop(task_id, None)
            self._task_results.pop(task_id, None)
            self._task_start_times.pop(task_id, None)

        if tasks_to_remove:
            notification_manager.info(
                f"[TaskManager] Cleared {len(tasks_to_remove)} completed tasks from tracking : {tasks_to_remove}"
            )


# Global instance of the task manager
task_manager = TaskManager()
