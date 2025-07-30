"""
Tests for TaskManager class.

This module tests the TaskManager functionality including task execution,
progress reporting, cache management, and execution summary generation.
All external dependencies are mocked for CI compatibility.
"""

# pyright: basic

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from batch_tamarin.model.executable_task import (
    ExecutableTask,
    MemoryStats,
    TaskResult,
    TaskStatus,
)
from batch_tamarin.modules.task_manager import TaskManager


@pytest.fixture
def mock_executable_task() -> ExecutableTask:
    """Create a mock ExecutableTask for testing."""
    return ExecutableTask(
        task_name="test_task",
        original_task_name="test_task",
        tamarin_version_name="stable",
        tamarin_executable=Path("/mock/tamarin-prover"),
        theory_file=Path("/mock/theory.spthy"),
        output_file=Path("/mock/output.txt"),
        lemma="test_lemma",
        tamarin_options=["--diff"],
        preprocess_flags=["FLAG1"],
        max_cores=4,
        max_memory=8,
        task_timeout=1800,
        traces_dir=Path("/mock/traces"),
    )


@pytest.fixture
def mock_task_result() -> TaskResult:
    """Create a mock TaskResult for testing."""
    return TaskResult(
        task_id="test_task",
        status=TaskStatus.COMPLETED,
        return_code=0,
        stdout="mock stdout",
        stderr="",
        start_time=1000.0,
        end_time=1010.0,
        duration=10.0,
        memory_stats=MemoryStats(peak_memory_mb=512.0, avg_memory_mb=256.0),
    )


class TestTaskManagerInitialization:
    """Test TaskManager initialization and basic setup."""

    def test_task_manager_initialization(self):
        """Test TaskManager initializes with correct default state."""
        task_manager = TaskManager()

        assert task_manager._task_status == {}  # type:ignore
        assert task_manager._task_results == {}  # type:ignore
        assert task_manager._task_start_times == {}  # type:ignore
        assert task_manager._cached_tasks == set()  # type:ignore
        assert task_manager._cache_manager is not None  # type:ignore

    def test_task_manager_is_singleton_like(self):
        """Test that TaskManager instances can be created independently."""
        task_manager1 = TaskManager()
        task_manager2 = TaskManager()

        # They should be separate instances
        assert task_manager1 is not task_manager2

        # But each should have its own state
        task_manager1._task_status["test"] = TaskStatus.RUNNING  # type:ignore
        assert "test" not in task_manager2._task_status  # type:ignore


class TestTaskExecution:
    """Test task execution with various scenarios."""

    @patch("batch_tamarin.modules.task_manager.output_manager")
    @patch("batch_tamarin.modules.task_manager.process_manager")
    @patch("batch_tamarin.modules.task_manager.notification_manager")
    @patch("batch_tamarin.modules.task_manager.time.time")
    async def test_run_executable_task_success(
        self,
        mock_time: Mock,
        mock_notification: Mock,
        mock_process_manager: Mock,
        mock_output_manager: Mock,
        mock_executable_task: ExecutableTask,
    ):
        """Test successful task execution."""
        # Mock time.time() with incrementing values to ensure proper duration calculation
        time_counter = [1000.0]

        def time_mock():
            current = time_counter[0]
            time_counter[0] += 0.1  # Small increment each call
            return current

        mock_time.side_effect = time_mock

        # Mock process manager
        mock_process_manager.run_command = AsyncMock(
            return_value=(0, "success output", "", None)
        )

        # Mock output manager
        mock_output_manager.is_initialized.return_value = True
        mock_output_manager.process_task_result = Mock()

        # Mock task.to_command()
        mock_executable_task.to_command = AsyncMock(
            return_value=["tamarin-prover", "theory.spthy", "--prove=test_lemma"]
        )

        task_manager = TaskManager()

        # Mock cache manager to return None (no cache hit)
        with patch.object(
            task_manager._cache_manager,  # type:ignore
            "get_cached_result",
            return_value=None,
        ):
            with patch.object(
                task_manager._cache_manager, "store_result"  # type:ignore
            ) as mock_store:
                result = await task_manager.run_executable_task(mock_executable_task)

        # Verify result
        assert result.task_id == "test_task"
        assert result.status == TaskStatus.COMPLETED
        assert result.return_code == 0
        assert result.stdout == "success output"
        assert result.stderr == ""
        assert (
            result.duration > 0.0
        )  # Duration should be positive due to incrementing time

        # Verify tracking

        assert (
            task_manager._task_status["test_task"]  # type:ignore
            == TaskStatus.COMPLETED
        )
        assert task_manager._task_results["test_task"] == result  # type:ignore

        # Verify cache was used
        mock_store.assert_called_once()

        # Verify output manager was called
        mock_output_manager.process_task_result.assert_called_once()

    @patch("batch_tamarin.modules.task_manager.output_manager")
    @patch("batch_tamarin.modules.task_manager.process_manager")
    @patch("batch_tamarin.modules.task_manager.notification_manager")
    @patch("batch_tamarin.modules.task_manager.time.time")
    async def test_run_executable_task_failure(
        self,
        mock_time: Mock,
        mock_notification: Mock,
        mock_process_manager: Mock,
        mock_output_manager: Mock,
        mock_executable_task: ExecutableTask,
    ):
        """Test task execution with failure."""
        # Mock time.time() with incrementing values to ensure proper duration calculation
        time_counter = [1000.0]

        def time_mock():
            current = time_counter[0]
            time_counter[0] += 0.1  # Small increment each call
            return current

        mock_time.side_effect = time_mock

        # Mock process manager to return failure
        mock_process_manager.run_command = AsyncMock(
            return_value=(1, "", "error output", None)
        )

        # Mock output manager
        mock_output_manager.is_initialized.return_value = True
        mock_output_manager.process_task_result = Mock()

        # Mock task.to_command()
        mock_executable_task.to_command = AsyncMock(
            return_value=["tamarin-prover", "theory.spthy", "--prove=test_lemma"]
        )

        task_manager = TaskManager()

        # Mock cache manager to return None (no cache hit)
        with patch.object(
            task_manager._cache_manager,  # type:ignore
            "get_cached_result",
            return_value=None,
        ):
            with patch.object(
                task_manager._cache_manager, "store_result"  # type:ignore
            ):
                result = await task_manager.run_executable_task(mock_executable_task)

        # Verify result
        assert result.task_id == "test_task"
        assert result.status == TaskStatus.FAILED
        assert result.return_code == 1
        assert result.stdout == ""
        assert result.stderr == "error output"

        # Verify tracking
        assert (
            task_manager._task_status["test_task"]  # type:ignore
            == TaskStatus.FAILED
        )
        assert task_manager._task_results["test_task"] == result  # type:ignore

    @patch("batch_tamarin.modules.task_manager.output_manager")
    @patch("batch_tamarin.modules.task_manager.process_manager")
    @patch("batch_tamarin.modules.task_manager.notification_manager")
    @patch("batch_tamarin.modules.task_manager.time.time")
    async def test_run_executable_task_timeout(
        self,
        mock_time: Mock,
        mock_notification: Mock,
        mock_process_manager: Mock,
        mock_output_manager: Mock,
        mock_executable_task: ExecutableTask,
    ):
        """Test task execution with timeout."""
        # Mock time.time() with incrementing values to ensure proper duration calculation
        time_counter = [1000.0]

        def time_mock():
            current = time_counter[0]
            time_counter[0] += 0.1  # Small increment each call
            return current

        mock_time.side_effect = time_mock

        # Mock process manager to return timeout
        mock_process_manager.run_command = AsyncMock(
            return_value=(-1, "", "Process timed out", None)
        )

        # Mock output manager
        mock_output_manager.is_initialized.return_value = False

        # Mock task.to_command()
        mock_executable_task.to_command = AsyncMock(
            return_value=["tamarin-prover", "theory.spthy", "--prove=test_lemma"]
        )

        task_manager = TaskManager()

        # Mock cache manager to return None (no cache hit)
        with patch.object(
            task_manager._cache_manager,  # type:ignore
            "get_cached_result",
            return_value=None,
        ):
            result = await task_manager.run_executable_task(mock_executable_task)

        # Verify result
        assert result.status == TaskStatus.TIMEOUT
        assert result.return_code == -1
        assert result.stderr == "Process timed out"

    @patch("batch_tamarin.modules.task_manager.output_manager")
    @patch("batch_tamarin.modules.task_manager.process_manager")
    @patch("batch_tamarin.modules.task_manager.notification_manager")
    @patch("batch_tamarin.modules.task_manager.time.time")
    async def test_run_executable_task_memory_limit(
        self,
        mock_time: Mock,
        mock_notification: Mock,
        mock_process_manager: Mock,
        mock_output_manager: Mock,
        mock_executable_task: ExecutableTask,
    ):
        """Test task execution with memory limit exceeded."""
        # Mock time.time() with incrementing values to ensure proper duration calculation
        time_counter = [1000.0]

        def time_mock():
            current = time_counter[0]
            time_counter[0] += 0.1  # Small increment each call
            return current

        mock_time.side_effect = time_mock

        # Mock process manager to return memory limit exceeded
        mock_process_manager.run_command = AsyncMock(
            return_value=(-2, "", "Process exceeded memory limit", None)
        )

        # Mock output manager
        mock_output_manager.is_initialized.return_value = False

        # Mock task.to_command()
        mock_executable_task.to_command = AsyncMock(
            return_value=["tamarin-prover", "theory.spthy", "--prove=test_lemma"]
        )

        task_manager = TaskManager()

        # Mock cache manager to return None (no cache hit)
        with patch.object(
            task_manager._cache_manager,  # type:ignore
            "get_cached_result",
            return_value=None,
        ):
            result = await task_manager.run_executable_task(mock_executable_task)

        # Verify result
        assert result.status == TaskStatus.MEMORY_LIMIT_EXCEEDED
        assert result.return_code == -2
        assert result.stderr == "Process exceeded memory limit"

    @patch("batch_tamarin.modules.task_manager.output_manager")
    @patch("batch_tamarin.modules.task_manager.process_manager")
    @patch("batch_tamarin.modules.task_manager.notification_manager")
    @patch("batch_tamarin.modules.task_manager.time.time")
    async def test_run_executable_task_exception(
        self,
        mock_time: Mock,
        mock_notification: Mock,
        mock_process_manager: Mock,
        mock_output_manager: Mock,
        mock_executable_task: ExecutableTask,
    ):
        """Test task execution with unexpected exception."""
        # Mock time.time() with incrementing values to ensure proper duration calculation
        time_counter = [1000.0]

        def time_mock():
            current = time_counter[0]
            time_counter[0] += 0.1  # Small increment each call
            return current

        mock_time.side_effect = time_mock

        # Mock process manager to raise exception
        mock_process_manager.run_command = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        # Mock output manager
        mock_output_manager.is_initialized.return_value = False

        # Mock task.to_command()
        mock_executable_task.to_command = AsyncMock(
            return_value=["tamarin-prover", "theory.spthy", "--prove=test_lemma"]
        )

        task_manager = TaskManager()

        # Mock cache manager to return None (no cache hit)
        with patch.object(
            task_manager._cache_manager,  # type:ignore
            "get_cached_result",
            return_value=None,
        ):
            result = await task_manager.run_executable_task(mock_executable_task)

        # Verify result
        assert result.status == TaskStatus.FAILED
        assert result.return_code == -1
        assert result.stderr == "Unexpected error"


class TestCacheManagement:
    """Test cache-related functionality."""

    @patch("batch_tamarin.modules.task_manager.output_manager")
    @patch("batch_tamarin.modules.task_manager.notification_manager")
    async def test_cache_hit(
        self,
        mock_notification: Mock,
        mock_output_manager: Mock,
        mock_executable_task: ExecutableTask,
        mock_task_result: TaskResult,
    ):
        """Test task execution with cache hit."""
        task_manager = TaskManager()

        # Mock cache manager to return cached result
        with patch.object(
            task_manager._cache_manager,  # type:ignore
            "get_cached_result",
            return_value=mock_task_result,
        ):
            result = await task_manager.run_executable_task(mock_executable_task)

        # Verify we got the cached result
        assert result == mock_task_result
        assert (
            task_manager._task_status["test_task"]  # type:ignore
            == TaskStatus.COMPLETED
        )
        assert (
            task_manager._task_results["test_task"]  # type:ignore
            == mock_task_result
        )
        assert "test_task" in task_manager._cached_tasks  # type:ignore

    @patch("batch_tamarin.modules.task_manager.output_manager")
    @patch("batch_tamarin.modules.task_manager.process_manager")
    @patch("batch_tamarin.modules.task_manager.notification_manager")
    @patch("batch_tamarin.modules.task_manager.time.time")
    async def test_cache_miss_and_store(
        self,
        mock_time: Mock,
        mock_notification: Mock,
        mock_process_manager: Mock,
        mock_output_manager: Mock,
        mock_executable_task: ExecutableTask,
    ):
        """Test task execution with cache miss and subsequent storage."""
        # Mock time.time() with incrementing values to ensure proper duration calculation
        time_counter = [1000.0]

        def time_mock():
            current = time_counter[0]
            time_counter[0] += 0.1  # Small increment each call
            return current

        mock_time.side_effect = time_mock

        # Mock process manager
        mock_process_manager.run_command = AsyncMock(
            return_value=(0, "success output", "", None)
        )

        # Mock output manager
        mock_output_manager.is_initialized.return_value = False

        # Mock task.to_command()
        mock_executable_task.to_command = AsyncMock(
            return_value=["tamarin-prover", "theory.spthy", "--prove=test_lemma"]
        )

        task_manager = TaskManager()

        # Mock cache manager
        with patch.object(
            task_manager._cache_manager,  # type:ignore
            "get_cached_result",
            return_value=None,
        ):
            with patch.object(
                task_manager._cache_manager, "store_result"  # type:ignore
            ) as mock_store:
                result = await task_manager.run_executable_task(mock_executable_task)

        # Verify cache was checked and result was stored
        mock_store.assert_called_once()
        assert result.status == TaskStatus.COMPLETED
        assert (
            "test_task" not in task_manager._cached_tasks  # type:ignore
        )  # No cache hit

    @patch("batch_tamarin.modules.task_manager.output_manager")
    @patch("batch_tamarin.modules.task_manager.notification_manager")
    async def test_cache_error_handling(
        self,
        mock_notification: Mock,
        mock_output_manager: Mock,
        mock_executable_task: ExecutableTask,
    ):
        """Test handling of cache errors."""
        task_manager = TaskManager()

        # Mock cache manager to raise exception
        with patch.object(
            task_manager._cache_manager,  # type:ignore
            "get_cached_result",
            side_effect=Exception("Cache error"),
        ):
            # Should not raise exception, should continue with normal execution
            with patch(
                "batch_tamarin.modules.task_manager.process_manager"
            ) as mock_process_manager:
                mock_process_manager.run_command = AsyncMock(
                    return_value=(0, "success", "", None)
                )
                mock_executable_task.to_command = AsyncMock(
                    return_value=["tamarin-prover", "theory.spthy"]
                )
                mock_output_manager.is_initialized.return_value = False

                with patch("batch_tamarin.modules.task_manager.time.time") as mock_time:
                    mock_time.side_effect = [
                        1000.0,
                        1000.0,
                        1000.0,
                        1000.0,
                        1010.0,
                        1010.0,
                        1010.0,
                    ]

                    result = await task_manager.run_executable_task(
                        mock_executable_task
                    )

                    assert result.status == TaskStatus.COMPLETED


class TestProgressReporting:
    """Test progress reporting functionality."""

    @patch("batch_tamarin.modules.task_manager.time.time")
    def test_get_execution_progress_empty(self, mock_time: Mock):
        """Test progress reporting with no tasks."""
        mock_time.return_value = 2000.0

        task_manager = TaskManager()
        progress = task_manager.get_execution_progress()

        assert progress.total_tasks == 0
        assert progress.pending_tasks == 0
        assert progress.running_tasks == 0
        assert progress.completed_tasks == 0
        assert progress.failed_tasks == 0
        assert progress.current_time == 2000.0

    @patch("batch_tamarin.modules.task_manager.time.time")
    def test_get_execution_progress_with_tasks(self, mock_time: Mock):
        """Test progress reporting with various task statuses."""
        mock_time.return_value = 2000.0

        task_manager = TaskManager()

        # Add tasks in various states
        task_manager._task_status["task1"] = TaskStatus.PENDING  # type:ignore
        task_manager._task_status["task2"] = TaskStatus.RUNNING  # type:ignore
        task_manager._task_status["task3"] = TaskStatus.COMPLETED  # type:ignore
        task_manager._task_status["task4"] = TaskStatus.FAILED  # type:ignore
        task_manager._task_status["task5"] = TaskStatus.TIMEOUT  # type:ignore
        task_manager._task_status["task6"] = (  # type:ignore
            TaskStatus.MEMORY_LIMIT_EXCEEDED
        )

        progress = task_manager.get_execution_progress()

        assert progress.total_tasks == 6
        assert progress.pending_tasks == 1
        assert progress.running_tasks == 1
        assert progress.completed_tasks == 1
        assert progress.failed_tasks == 3  # FAILED, TIMEOUT, MEMORY_LIMIT_EXCEEDED
        assert progress.current_time == 2000.0

    @patch("batch_tamarin.modules.task_manager.time.time")
    def test_update_task_status(self, mock_time: Mock):
        """Test manual task status updates."""
        # Use return_value for simple cases where timing doesn't matter
        mock_time.return_value = 2000.0

        task_manager = TaskManager()

        # Update task status
        task_manager.update_task_status("task1", TaskStatus.RUNNING)

        assert task_manager._task_status["task1"] == TaskStatus.RUNNING  # type:ignore
        assert task_manager._task_start_times["task1"] == 2000.0  # type:ignore

        # Update to completed
        task_manager.update_task_status("task1", TaskStatus.COMPLETED)

        assert task_manager._task_status["task1"] == TaskStatus.COMPLETED  # type:ignore
        # Start time should remain unchanged
        assert task_manager._task_start_times["task1"] == 2000.0  # type:ignore

    @patch("batch_tamarin.modules.task_manager.time.time")
    def test_update_task_status_no_duplicate_start_time(self, mock_time: Mock):
        """Test that start time is not overwritten if already set."""
        # Mock time.time() with incrementing values
        time_counter = [2000.0]

        def time_mock():
            current = time_counter[0]
            time_counter[0] += 0.1
            return current

        mock_time.side_effect = time_mock

        task_manager = TaskManager()

        # Set initial start time
        task_manager._task_start_times["task1"] = 1900.0  # type:ignore

        # Update to running should not overwrite start time
        task_manager.update_task_status("task1", TaskStatus.RUNNING)

        assert task_manager._task_start_times["task1"] == 1900.0  # type:ignore


class TestExecutionSummary:
    """Test execution summary generation."""

    def test_generate_execution_summary_empty(self):
        """Test execution summary with no tasks."""
        task_manager = TaskManager()
        summary = task_manager.generate_execution_summary()

        assert summary.total_tasks == 0
        assert summary.successful_tasks == 0
        assert summary.failed_tasks == 0
        assert summary.total_duration == 0.0
        assert summary.task_results == []

    def test_generate_execution_summary_with_tasks(self):
        """Test execution summary with various task results."""
        task_manager = TaskManager()

        # Create mock task results
        task_results = [
            TaskResult(
                task_id="task1",
                status=TaskStatus.COMPLETED,
                return_code=0,
                stdout="output1",
                stderr="",
                start_time=1000.0,
                end_time=1010.0,
                duration=10.0,
            ),
            TaskResult(
                task_id="task2",
                status=TaskStatus.FAILED,
                return_code=1,
                stdout="",
                stderr="error",
                start_time=1005.0,
                end_time=1020.0,
                duration=15.0,
            ),
            TaskResult(
                task_id="task3",
                status=TaskStatus.TIMEOUT,
                return_code=-1,
                stdout="",
                stderr="timeout",
                start_time=1010.0,
                end_time=1030.0,
                duration=20.0,
            ),
        ]

        # Add results to task manager
        for result in task_results:
            task_manager._task_results[result.task_id] = result  # type:ignore
            task_manager._task_status[result.task_id] = result.status  # type:ignore

        # Add some cached tasks
        task_manager._cached_tasks.add("task1")  # type:ignore

        # Mock cache manager stats
        with patch.object(
            task_manager._cache_manager,  # type:ignore
            "get_stats",
            return_value={"size": 5, "volume": 1024},
        ):
            summary = task_manager.generate_execution_summary()

        assert summary.total_tasks == 3
        assert summary.successful_tasks == 1
        assert summary.failed_tasks == 2  # FAILED + TIMEOUT
        assert summary.total_duration == 30.0  # 1030.0 - 1000.0
        assert len(summary.task_results) == 3
        assert summary.cache_entries == 5
        assert summary.cached_tasks == 1
        assert summary.cache_volume == 1024
        assert summary.cached_task_ids == {"task1"}

    def test_generate_execution_summary_cache_error(self):
        """Test execution summary when cache stats fail."""
        task_manager = TaskManager()

        # Add a task result
        task_result = TaskResult(
            task_id="task1",
            status=TaskStatus.COMPLETED,
            return_code=0,
            stdout="output1",
            stderr="",
            start_time=1000.0,
            end_time=1010.0,
            duration=10.0,
        )
        task_manager._task_results["task1"] = task_result  # type:ignore

        # Mock cache manager to raise exception
        with patch.object(
            task_manager._cache_manager,  # type:ignore
            "get_stats",
            side_effect=Exception("Cache error"),
        ):
            summary = task_manager.generate_execution_summary()

        assert summary.total_tasks == 1
        assert summary.successful_tasks == 1
        assert summary.failed_tasks == 0
        assert summary.cache_entries == 0
        assert summary.cached_tasks == 0
        assert summary.cache_volume == 0


class TestTaskStatusManagement:
    """Test task status and result management."""

    def test_get_task_results(self):
        """Test getting all task results."""
        task_manager = TaskManager()

        # Add some results
        result1 = TaskResult(
            task_id="task1",
            status=TaskStatus.COMPLETED,
            return_code=0,
            stdout="output1",
            stderr="",
            start_time=1000.0,
            end_time=1010.0,
            duration=10.0,
        )
        result2 = TaskResult(
            task_id="task2",
            status=TaskStatus.FAILED,
            return_code=1,
            stdout="",
            stderr="error",
            start_time=1005.0,
            end_time=1020.0,
            duration=15.0,
        )

        task_manager._task_results["task1"] = result1  # type:ignore
        task_manager._task_results["task2"] = result2  # type:ignore

        results = task_manager.get_task_results()

        assert len(results) == 2
        assert results["task1"] == result1
        assert results["task2"] == result2

        # Should be a copy, not the original
        assert results is not task_manager._task_results  # type:ignore

    def test_get_task_status(self):
        """Test getting status of specific task."""
        task_manager = TaskManager()

        # Add task status
        task_manager._task_status["task1"] = TaskStatus.RUNNING  # type:ignore

        status = task_manager.get_task_status("task1")
        assert status == TaskStatus.RUNNING

    def test_get_task_status_not_found(self):
        """Test getting status of non-existent task."""
        task_manager = TaskManager()

        with pytest.raises(KeyError):
            task_manager.get_task_status("nonexistent")

    def test_clear_completed_tasks(self):
        """Test clearing completed tasks from tracking."""
        task_manager = TaskManager()

        # Add various task statuses
        task_manager._task_status["pending"] = TaskStatus.PENDING  # type:ignore
        task_manager._task_status["running"] = TaskStatus.RUNNING  # type:ignore
        task_manager._task_status["completed"] = TaskStatus.COMPLETED  # type:ignore
        task_manager._task_status["failed"] = TaskStatus.FAILED  # type:ignore
        task_manager._task_status["timeout"] = TaskStatus.TIMEOUT  # type:ignore
        task_manager._task_status["memory"] = (  # type:ignore
            TaskStatus.MEMORY_LIMIT_EXCEEDED
        )

        # Add corresponding results and start times
        for task_id in task_manager._task_status:  # type:ignore
            task_manager._task_results[task_id] = TaskResult(  # type:ignore
                task_id=task_id,
                status=task_manager._task_status[task_id],  # type:ignore
                return_code=0,
                stdout="",
                stderr="",
                start_time=1000.0,
                end_time=1010.0,
                duration=10.0,
            )
            task_manager._task_start_times[task_id] = 1000.0  # type:ignore

        # Clear completed tasks
        task_manager.clear_completed_tasks()

        # Should only have pending and running tasks left
        assert len(task_manager._task_status) == 2  # type:ignore
        assert "pending" in task_manager._task_status  # type:ignore
        assert "running" in task_manager._task_status  # type:ignore
        assert "completed" not in task_manager._task_status  # type:ignore
        assert "failed" not in task_manager._task_status  # type:ignore
        assert "timeout" not in task_manager._task_status  # type:ignore
        assert "memory" not in task_manager._task_status  # type:ignore

        # Check that results and start times were also cleared
        assert len(task_manager._task_results) == 2  # type:ignore
        assert len(task_manager._task_start_times) == 2  # type:ignore

    def test_clear_completed_tasks_empty(self):
        """Test clearing completed tasks when none exist."""
        task_manager = TaskManager()

        # Should not raise exception
        task_manager.clear_completed_tasks()

        assert len(task_manager._task_status) == 0  # type:ignore
        assert len(task_manager._task_results) == 0  # type:ignore
        assert len(task_manager._task_start_times) == 0  # type:ignore
