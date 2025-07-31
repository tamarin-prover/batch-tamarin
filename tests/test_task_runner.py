"""
Tests for TaskRunner class.

This module tests the TaskRunner functionality including task orchestration,
resource coordination, progress reporting, and shutdown handling.
All external dependencies are mocked for CI compatibility.
"""

# pyright: basic

import asyncio
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from batch_tamarin.model.executable_task import (
    ExecutableTask,
    MemoryStats,
    TaskResult,
    TaskStatus,
)
from batch_tamarin.model.tamarin_recipe import (
    SchedulingStrategy,
    TamarinRecipe,
)
from batch_tamarin.runner import TaskRunner


@pytest.fixture
def mock_recipe_data() -> Dict[str, Any]:
    """Create mock recipe data for testing."""
    return {
        "config": {
            "global_max_cores": 8,
            "global_max_memory": 16,
            "default_timeout": 3600,
            "output_directory": "./test-results",
        },
        "tamarin_versions": {
            "stable": {"path": "/mock/tamarin-prover", "version": "1.10.0"}
        },
        "tasks": {
            "test_task": {
                "theory_file": "/mock/theory.spthy",
                "tamarin_versions": ["stable"],
                "output_file_prefix": "test_task",
            }
        },
    }


@pytest.fixture
def mock_recipe(mock_recipe_data: Dict[str, Any]) -> TamarinRecipe:
    """Create mock TamarinRecipe for testing."""
    return TamarinRecipe.model_validate(mock_recipe_data)


@pytest.fixture
def mock_executable_tasks() -> List[ExecutableTask]:
    """Create mock ExecutableTask list for testing."""
    return [
        ExecutableTask(
            task_name="task1",
            original_task_name="task1",
            tamarin_version_name="stable",
            tamarin_executable=Path("/mock/tamarin-prover"),
            theory_file=Path("/mock/theory.spthy"),
            output_file=Path("/mock/output1.txt"),
            lemma="lemma1",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=2,
            max_memory=4,
            task_timeout=1800,
            traces_dir=Path("/mock/traces"),
        ),
        ExecutableTask(
            task_name="task2",
            original_task_name="task2",
            tamarin_version_name="stable",
            tamarin_executable=Path("/mock/tamarin-prover"),
            theory_file=Path("/mock/theory.spthy"),
            output_file=Path("/mock/output2.txt"),
            lemma="lemma2",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=2,
            max_memory=4,
            task_timeout=1800,
            traces_dir=Path("/mock/traces"),
        ),
    ]


@pytest.fixture
def mock_task_results() -> List[TaskResult]:
    """Create mock TaskResult list for testing."""
    return [
        TaskResult(
            task_id="task1",
            status=TaskStatus.COMPLETED,
            return_code=0,
            stdout="success output 1",
            stderr="",
            start_time=1000.0,
            end_time=1010.0,
            duration=10.0,
            memory_stats=MemoryStats(peak_memory_mb=512.0, avg_memory_mb=256.0),
        ),
        TaskResult(
            task_id="task2",
            status=TaskStatus.FAILED,
            return_code=1,
            stdout="",
            stderr="error output 2",
            start_time=1005.0,
            end_time=1015.0,
            duration=10.0,
            memory_stats=None,
        ),
    ]


class TestTaskRunnerInitialization:
    """Test TaskRunner initialization and setup."""

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    def test_task_runner_initialization(
        self,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
    ):
        """Test TaskRunner initializes correctly with recipe."""
        # Mock the managers
        mock_resource_manager.return_value = Mock()
        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)

        assert runner.recipe == mock_recipe
        assert runner.resource_manager is not None
        assert runner.task_manager is not None
        assert runner._pending_tasks == []  # type: ignore
        assert runner._running_tasks == {}  # type: ignore
        assert runner._completed_tasks == set()  # type: ignore
        assert runner._failed_tasks == set()  # type: ignore
        assert runner._task_results == {}  # type: ignore
        assert runner.completed_tasks == set()
        assert runner.failed_tasks == set()
        assert runner.task_results == {}
        assert not runner._shutdown_requested  # type: ignore
        assert not runner._force_shutdown_requested  # type: ignore
        assert runner._signal_count == 0  # type: ignore

        # Verify managers were initialized
        mock_resource_manager.assert_called_once_with(
            mock_recipe, SchedulingStrategy.FIFO
        )
        mock_task_manager.assert_called_once()
        mock_output_manager.initialize.assert_called_once()

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    def test_task_runner_output_manager_initialization(
        self,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
    ):
        """Test TaskRunner initializes OutputManager with correct directory."""
        mock_resource_manager.return_value = Mock()
        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()

        # Mock get_output_paths to return the expected structure
        mock_output_paths = {"base": Path(mock_recipe.config.output_directory)}
        mock_output_manager.get_output_paths.return_value = mock_output_paths

        _ = TaskRunner(mock_recipe)

        expected_output_dir = Path(mock_recipe.config.output_directory)
        mock_output_manager.initialize.assert_called_once_with(expected_output_dir)
        mock_output_manager.get_output_paths.assert_called_once()


class TestTaskRunnerExecution:
    """Test TaskRunner main execution functionality."""

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    @patch("batch_tamarin.runner.notification_manager")
    async def test_execute_all_tasks_empty_list(
        self,
        mock_notification: Mock,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
    ):
        """Test execute_all_tasks with empty task list."""
        mock_resource_mgr_instance = Mock()
        # Make sure get_next_schedulable_tasks returns an empty list instead of a Mock
        mock_resource_mgr_instance.get_next_schedulable_tasks.return_value = []
        mock_resource_manager.return_value = mock_resource_mgr_instance
        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)

        await runner.execute_all_tasks([])

        mock_notification.phase_separator.assert_called_once_with("Task Execution")
        mock_notification.error.assert_called_once_with(
            "[TaskRunner] No tasks provided for execution"
        )

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    @patch("batch_tamarin.runner.notification_manager")
    async def test_execute_all_tasks_with_tasks(
        self,
        mock_notification: Mock,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
        mock_executable_tasks: List[ExecutableTask],
    ):
        """Test execute_all_tasks with actual tasks."""
        # Mock managers
        mock_resource_manager.return_value = Mock()
        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)

        # Mock the execution pool method
        with patch.object(runner, "_execute_task_pool") as mock_execute_pool:
            mock_execute_pool.return_value = None

            await runner.execute_all_tasks(mock_executable_tasks)

            # Verify initialization
            assert runner._pending_tasks == mock_executable_tasks  # type: ignore
            assert runner._running_tasks == {}  # type: ignore
            assert runner._completed_tasks == set()  # type: ignore
            assert runner._failed_tasks == set()  # type: ignore
            assert runner._task_results == {}  # type: ignore
            assert runner.completed_tasks == set()

            # Verify notifications
            mock_notification.phase_separator.assert_called_once_with("Task Execution")
            mock_execute_pool.assert_called_once_with(mock_executable_tasks)

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    @patch("batch_tamarin.runner.notification_manager")
    async def test_execute_task_pool_completion(
        self,
        mock_notification: Mock,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
        mock_executable_tasks: List[ExecutableTask],
    ):
        """Test _execute_task_pool with task completion."""
        # Mock managers
        mock_resource_manager.return_value = Mock()
        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)
        runner._pending_tasks = mock_executable_tasks.copy()  # type: ignore

        # Mock the helper methods
        with patch.object(runner, "_should_continue_execution") as mock_should_continue:
            with patch.object(runner, "_start_schedulable_tasks") as mock_start:
                with patch.object(runner, "_handle_completed_tasks") as mock_handle:
                    with patch.object(
                        runner, "_display_progress_update"
                    ) as mock_display:
                        with patch.object(runner, "_handle_shutdown") as mock_shutdown:
                            with patch("asyncio.sleep") as mock_sleep:
                                with patch("asyncio.get_event_loop") as mock_loop:
                                    mock_loop.return_value.time.return_value = 1000.0

                                    # Set up the execution loop to run once then stop
                                    mock_should_continue.side_effect = [True, False]
                                    mock_start.return_value = None
                                    mock_handle.return_value = None
                                    mock_display.return_value = None
                                    mock_shutdown.return_value = None

                                    # Mock resource manager
                                    mock_resource_mgr = Mock()
                                    mock_resource_mgr.get_next_schedulable_tasks.return_value = (
                                        []
                                    )
                                    runner.resource_manager = mock_resource_mgr

                                    await runner._execute_task_pool(  # type: ignore
                                        mock_executable_tasks
                                    )

                                    # Verify methods were called
                                    assert mock_should_continue.call_count == 2
                                    # _start_schedulable_tasks is now called multiple times due to event-driven scheduling
                                    assert mock_start.call_count >= 1
                                    mock_handle.assert_called_once()
                                    mock_display.assert_called()
                                    mock_shutdown.assert_called_once()
                                    # asyncio.sleep is no longer called with fixed intervals in the new implementation

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    def test_should_continue_execution_pending_tasks(
        self,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
    ):
        """Test _should_continue_execution with pending tasks."""
        mock_resource_manager.return_value = Mock()
        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)
        runner._pending_tasks = ["task1", "task2"]  # type: ignore
        runner._running_tasks = {}  # type: ignore

        assert runner._should_continue_execution() is True  # type: ignore

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    def test_should_continue_execution_running_tasks(
        self,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
    ):
        """Test _should_continue_execution with running tasks."""
        mock_resource_manager.return_value = Mock()
        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)
        runner._pending_tasks = []  # type: ignore
        runner._running_tasks = {"task1": Mock()}  # type: ignore

        assert runner._should_continue_execution() is True  # type: ignore

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    def test_should_continue_execution_no_tasks(
        self,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
    ):
        """Test _should_continue_execution with no tasks."""
        mock_resource_manager.return_value = Mock()
        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)
        runner._pending_tasks = []  # type: ignore
        runner._running_tasks = {}  # type: ignore

        assert runner._should_continue_execution() is False  # type: ignore

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    @patch("batch_tamarin.runner.notification_manager")
    @pytest.mark.asyncio
    async def test_start_schedulable_tasks(
        self,
        mock_notification: Mock,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
        mock_executable_tasks: List[ExecutableTask],
    ):
        """Test _start_schedulable_tasks with available resources."""
        # Mock resource manager
        mock_resource_mgr = Mock()
        mock_resource_mgr.allocate_resources.return_value = True
        mock_resource_manager.return_value = mock_resource_mgr

        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)
        runner._pending_tasks = mock_executable_tasks.copy()  # type: ignore

        # Mock _execute_single_task and asyncio.create_task
        with patch.object(
            runner, "_execute_single_task", new_callable=AsyncMock
        ) as mock_execute:
            with patch("asyncio.create_task") as mock_create_task:
                # Mock execute returns a simple Mock - asyncio.create_task handles the async behavior
                mock_execute.return_value = Mock()
                mock_task_obj = Mock()
                mock_create_task.return_value = mock_task_obj

                runner._start_schedulable_tasks(mock_executable_tasks)  # type: ignore

                # Should start all schedulable tasks
                assert mock_resource_mgr.allocate_resources.call_count == 2
                assert mock_create_task.call_count == 2
                assert len(runner._pending_tasks) == 0  # type: ignore
                assert len(runner._running_tasks) == 2  # type: ignore

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    @patch("batch_tamarin.runner.notification_manager")
    def test_start_schedulable_tasks_no_resources(
        self,
        mock_notification: Mock,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
        mock_executable_tasks: List[ExecutableTask],
    ):
        """Test _start_schedulable_tasks with no available resources."""
        # Mock resource manager to deny allocation
        mock_resource_mgr = Mock()
        mock_resource_mgr.allocate_resources.return_value = False
        mock_resource_manager.return_value = mock_resource_mgr

        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)
        runner._pending_tasks = mock_executable_tasks.copy()  # type: ignore

        runner._start_schedulable_tasks(mock_executable_tasks)  # type: ignore

        # Should not start any tasks
        assert len(runner._pending_tasks) == 2  # type: ignore
        assert len(runner._running_tasks) == 0  # type: ignore

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    async def test_handle_completed_tasks(
        self,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
        mock_executable_tasks: List[ExecutableTask],
        mock_task_results: List[TaskResult],
    ):
        """Test _handle_completed_tasks with completed tasks."""
        mock_resource_manager.return_value = Mock()
        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)

        # Create mock completed tasks with proper asyncio task behavior
        async def completed_task():
            return mock_task_results[0]

        mock_task1 = asyncio.create_task(completed_task())
        # Let the task complete
        await asyncio.sleep(0)

        mock_task2 = Mock()
        mock_task2.done.return_value = False

        runner._running_tasks = {  # type: ignore
            "task1": mock_task1,
            "task2": mock_task2,
        }

        # Mock _handle_task_completion
        with patch.object(runner, "_handle_task_completion") as mock_handle:
            await runner._handle_completed_tasks(mock_executable_tasks)  # type: ignore

            # Should handle only completed task
            mock_handle.assert_called_once_with(
                mock_executable_tasks[0], mock_task_results[0]
            )
            assert "task1" not in runner._running_tasks  # type: ignore
            assert "task2" in runner._running_tasks  # type: ignore

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    @pytest.mark.asyncio
    async def test_execute_single_task(
        self,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
        mock_executable_tasks: List[ExecutableTask],
        mock_task_results: List[TaskResult],
    ):
        """Test _execute_single_task execution."""
        mock_resource_manager.return_value = Mock()

        # Mock task manager with proper async handling
        mock_task_mgr = Mock()
        mock_task_mgr.run_executable_task = AsyncMock(return_value=mock_task_results[0])
        mock_task_manager.return_value = mock_task_mgr

        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)

        task = mock_executable_tasks[0]
        result = await runner._execute_single_task(task)  # type: ignore

        assert result == mock_task_results[0]
        mock_task_mgr.run_executable_task.assert_called_once_with(task)

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    @patch("batch_tamarin.runner.notification_manager")
    def test_handle_task_completion_success(
        self,
        mock_notification: Mock,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
        mock_executable_tasks: List[ExecutableTask],
        mock_task_results: List[TaskResult],
    ):
        """Test _handle_task_completion with successful task."""
        # Mock resource manager
        mock_resource_mgr = Mock()
        mock_resource_mgr.release_resources.return_value = None
        mock_resource_manager.return_value = mock_resource_mgr

        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)

        task = mock_executable_tasks[0]
        task_result = mock_task_results[0]  # Successful result
        runner._handle_task_completion(task, task_result)  # type: ignore

        assert "task1" in runner._completed_tasks  # type: ignore
        assert "task1" not in runner._failed_tasks  # type: ignore
        assert runner._task_results["task1"] == task_result  # type: ignore
        assert runner.task_results["task1"] == task_result

        mock_resource_mgr.release_resources.assert_called_once_with(task)

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    @patch("batch_tamarin.runner.notification_manager")
    def test_handle_task_completion_failure(
        self,
        mock_notification: Mock,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
        mock_executable_tasks: List[ExecutableTask],
        mock_task_results: List[TaskResult],
    ):
        """Test _handle_task_completion with failed task."""
        # Mock resource manager
        mock_resource_mgr = Mock()
        mock_resource_mgr.release_resources.return_value = None
        mock_resource_manager.return_value = mock_resource_mgr

        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)

        task = mock_executable_tasks[1]
        task_result = mock_task_results[1]  # Failed result
        runner._handle_task_completion(task, task_result)  # type: ignore

        assert "task2" in runner._failed_tasks  # type: ignore
        assert "task2" not in runner._completed_tasks  # type: ignore
        assert runner._task_results["task2"] == task_result  # type: ignore
        assert runner.task_results["task2"] == task_result

        mock_resource_mgr.release_resources.assert_called_once_with(task)

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    @patch("batch_tamarin.runner.notification_manager")
    def test_display_progress_update(
        self,
        mock_notification: Mock,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
    ):
        """Test _display_progress_update with progress reporting."""
        # Mock resource manager
        mock_resource_mgr = Mock()
        mock_resource_mgr.get_allocated_cores.return_value = 4
        mock_resource_mgr.global_max_cores = 8
        mock_resource_mgr.get_allocated_memory.return_value = 8
        mock_resource_mgr.global_max_memory = 16
        mock_resource_manager.return_value = mock_resource_mgr

        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)

        # Set up some task state
        runner._pending_tasks = ["task1"]  # type: ignore
        runner._running_tasks = {"task2": Mock()}  # type: ignore
        runner._completed_tasks = {"task3"}  # type: ignore
        runner._failed_tasks = {"task4"}  # type: ignore
        runner._display_progress_update()  # type: ignore

        # Should have called info notifications
        assert mock_notification.info.call_count >= 2


class TestTaskRunnerShutdown:
    """Test TaskRunner shutdown and signal handling."""

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    @patch("batch_tamarin.runner.notification_manager")
    async def test_handle_shutdown_graceful(
        self,
        mock_notification: Mock,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
    ):
        """Test _handle_shutdown with graceful shutdown."""
        mock_resource_manager.return_value = Mock()
        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)
        runner._shutdown_requested = True  # type: ignore

        # Mock running tasks
        mock_task1 = AsyncMock()
        mock_task2 = AsyncMock()
        runner._running_tasks = {  # type: ignore
            "task1": mock_task1,
            "task2": mock_task2,
        }

        with patch.object(runner, "_cleanup_running_tasks") as mock_cleanup:
            await runner._handle_shutdown()  # type: ignore

            mock_cleanup.assert_called_once()

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    @patch("batch_tamarin.runner.notification_manager")
    async def test_handle_shutdown_force(
        self,
        mock_notification: Mock,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
    ):
        """Test _handle_shutdown with force shutdown."""
        mock_resource_manager.return_value = Mock()
        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)
        runner._force_shutdown_requested = True  # type: ignore

        # Mock running tasks
        mock_task1 = AsyncMock()
        mock_task2 = AsyncMock()
        runner._running_tasks = {  # type: ignore
            "task1": mock_task1,
            "task2": mock_task2,
        }

        with patch.object(runner, "_force_kill_all_tasks") as mock_force_kill:
            await runner._handle_shutdown()  # type: ignore

            mock_force_kill.assert_called_once()

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    @patch("batch_tamarin.runner.notification_manager")
    async def test_cleanup_running_tasks(
        self,
        mock_notification: Mock,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
    ):
        """Test _cleanup_running_tasks with successful completion."""
        mock_resource_manager.return_value = Mock()
        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)

        # Mock running tasks with proper async behavior
        async def task1():
            return Mock()

        async def task2():
            return Mock()

        mock_task1 = asyncio.create_task(task1())
        mock_task2 = asyncio.create_task(task2())

        runner._running_tasks = {  # type: ignore
            "task1": mock_task1,
            "task2": mock_task2,
        }

        # Let the tasks complete
        await asyncio.sleep(0)

        await runner._cleanup_running_tasks()  # type: ignore

        assert len(runner._running_tasks) == 0  # type: ignore
        assert len(runner._pending_tasks) == 0  # type: ignore

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    @patch("batch_tamarin.runner.notification_manager")
    @patch("batch_tamarin.runner.process_manager")
    async def test_force_kill_all_tasks(
        self,
        mock_process_manager: Mock,
        mock_notification: Mock,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
    ):
        """Test _force_kill_all_tasks cancellation."""
        mock_resource_manager.return_value = Mock()
        mock_task_manager.return_value = Mock()
        mock_output_manager.initialize = Mock()
        mock_process_manager.kill_all_processes = AsyncMock()

        runner = TaskRunner(mock_recipe)

        # Mock running tasks
        mock_task1 = Mock()
        mock_task1.done.return_value = False
        mock_task1.cancel = Mock()

        mock_task2 = Mock()
        mock_task2.done.return_value = False
        mock_task2.cancel = Mock()

        runner._running_tasks = {  # type: ignore
            "task1": mock_task1,
            "task2": mock_task2,
        }

        with patch("asyncio.wait") as mock_wait:
            # Simulate that tasks don't complete during grace period (all pending)
            mock_wait.return_value = (
                set(),
                {mock_task1, mock_task2},
            )  # completed, pending

            await runner._force_kill_all_tasks()  # type: ignore

            # Tasks should be cancelled since they were in pending set
            mock_task1.cancel.assert_called_once()
            mock_task2.cancel.assert_called_once()
            mock_process_manager.kill_all_processes.assert_called_once()
            assert len(runner._running_tasks) == 0  # type: ignore
            assert len(runner._pending_tasks) == 0  # type: ignore


class TestTaskRunnerErrorHandling:
    """Test TaskRunner error handling scenarios."""

    @patch("batch_tamarin.runner.output_manager")
    @patch("batch_tamarin.runner.TaskManager")
    @patch("batch_tamarin.runner.ResourceManager")
    @patch("batch_tamarin.runner.notification_manager")
    async def test_execute_single_task_exception(
        self,
        mock_notification: Mock,
        mock_resource_manager: Mock,
        mock_task_manager: Mock,
        mock_output_manager: Mock,
        mock_recipe: TamarinRecipe,
        mock_executable_tasks: List[ExecutableTask],
    ):
        """Test _execute_single_task with exception during execution."""
        mock_resource_manager.return_value = Mock()

        # Mock task manager to raise exception
        mock_task_mgr = Mock()
        mock_task_mgr.run_executable_task = AsyncMock(
            side_effect=Exception("Task execution failed")
        )
        mock_task_manager.return_value = mock_task_mgr

        mock_output_manager.initialize = Mock()

        runner = TaskRunner(mock_recipe)

        task = mock_executable_tasks[0]

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.time.return_value = 1000.0

            # Should not raise exception, but return error result
            result = await runner._execute_single_task(task)  # type: ignore

            assert result.status == TaskStatus.FAILED
            assert result.return_code == -1
            assert result.stderr == "Task execution failed"
            mock_task_mgr.run_executable_task.assert_called_once_with(task)
