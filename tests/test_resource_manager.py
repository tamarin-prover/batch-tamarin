"""
Tests for ResourceManager class.

This module tests the ResourceManager functionality including resource allocation,
task scheduling, and resource tracking. All system dependencies are mocked for
CI compatibility.
"""

# pyright: basic

from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock, patch

from batch_tamarin.model.executable_task import ExecutableTask
from batch_tamarin.model.tamarin_recipe import SchedulingStrategy, TamarinRecipe
from batch_tamarin.modules.resource_manager import ResourceManager


class TestResourceManagerInitialization:
    """Test ResourceManager initialization and system resource validation."""

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_resource_manager_init_within_limits(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
    ) -> None:
        """Test ResourceManager initialization with resources within system limits."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)  # 64GB in bytes
        # Return input unchanged
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        assert resource_manager.global_max_cores == 8
        assert resource_manager.global_max_memory == 16
        assert resource_manager.allocated_cores == 0
        assert resource_manager.allocated_memory == 0
        assert resource_manager.task_allocations == {}

        # Should not prompt for fallback since limits are within system capabilities
        mock_notification.warning.assert_not_called()
        mock_notification.prompt_user.assert_not_called()

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_resource_manager_init_cores_exceed_system_accept_fallback(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
    ):
        """Test ResourceManager initialization when cores exceed system limits and user accepts fallback."""
        # Mock system resources - fewer cores than requested
        mock_cpu_count.return_value = 4
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)  # 64GB in bytes
        mock_resolve.side_effect = lambda x, _: x  # type: ignore
        mock_notification.prompt_user.return_value = True  # User accepts fallback

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        assert resource_manager.global_max_cores == 4  # Fell back to system limit
        assert resource_manager.global_max_memory == 16
        assert recipe.config.global_max_cores == 4  # Recipe updated too

        mock_notification.warning.assert_called_once()
        mock_notification.prompt_user.assert_called_once()

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_resource_manager_init_cores_exceed_system_reject_fallback(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
    ):
        """Test ResourceManager initialization when cores exceed system limits and user rejects fallback."""
        # Mock system resources - fewer cores than requested
        mock_cpu_count.return_value = 4
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)  # 64GB in bytes
        mock_resolve.side_effect = lambda x, _: x  # type: ignore
        mock_notification.prompt_user.return_value = False  # User rejects fallback

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        assert resource_manager.global_max_cores == 8  # Keeps original value
        assert resource_manager.global_max_memory == 16
        assert recipe.config.global_max_cores == 8  # Recipe unchanged

        mock_notification.warning.assert_called_once()
        mock_notification.prompt_user.assert_called_once()

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_resource_manager_init_memory_exceed_system_accept_fallback(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
    ):
        """Test ResourceManager initialization when memory exceeds system limits and user accepts fallback."""
        # Mock system resources - less memory than requested
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=8 * 1024**3)  # 8GB in bytes
        mock_resolve.side_effect = lambda x, _: x  # type: ignore
        mock_notification.prompt_user.return_value = True  # User accepts fallback

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        assert resource_manager.global_max_cores == 8
        assert resource_manager.global_max_memory == 8  # Fell back to system limit
        assert recipe.config.global_max_memory == 8  # Recipe updated too

        mock_notification.warning.assert_called_once()
        mock_notification.prompt_user.assert_called_once()

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_resource_manager_init_both_exceed_system_multiple_prompts(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
    ):
        """Test ResourceManager initialization when both cores and memory exceed system limits."""
        # Mock system resources - both below requested
        mock_cpu_count.return_value = 4
        mock_virtual_memory.return_value = Mock(total=8 * 1024**3)  # 8GB in bytes
        mock_resolve.side_effect = lambda x, _: x  # type: ignore
        mock_notification.prompt_user.side_effect = [
            True,
            False,
        ]  # Accept cores fallback, reject memory fallback

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        assert resource_manager.global_max_cores == 4  # Fell back
        assert resource_manager.global_max_memory == 16  # Kept original
        assert recipe.config.global_max_cores == 4
        assert recipe.config.global_max_memory == 16

        assert mock_notification.warning.call_count == 2
        assert mock_notification.prompt_user.call_count == 2

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_resource_manager_init_with_resource_resolution(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
    ):
        """Test ResourceManager initialization with resource value resolution."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)  # 64GB in bytes

        # Mock resource resolution to return different values (e.g., "max" resolved to actual values)
        def mock_resolve_fn(value: int, resource_type: str) -> Any:
            if resource_type == "cores":
                return 12  # Resolved cores
            elif resource_type == "memory":
                return 24  # Resolved memory
            return value

        mock_resolve.side_effect = mock_resolve_fn

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        assert resource_manager.global_max_cores == 12
        assert resource_manager.global_max_memory == 24

        # Verify resolve_resource_value was called correctly
        assert mock_resolve.call_count == 2
        mock_resolve.assert_any_call(8, "cores")
        mock_resolve.assert_any_call(16, "memory")


class TestResourceAllocation:
    """Test resource allocation and deallocation."""

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_allocate_resources_success(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
        tmp_dir: Path,
    ):
        """Test successful resource allocation."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        # Create test task
        task = ExecutableTask(
            task_name="test_task",
            original_task_name="test_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="test_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=4,
            max_memory=8,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        # Allocate resources
        success = resource_manager.allocate_resources(task)

        assert success is True
        assert resource_manager.allocated_cores == 4
        assert resource_manager.allocated_memory == 8
        assert resource_manager.task_allocations["test_task"] == (4, 8)
        assert resource_manager.get_available_cores() == 4  # 8 - 4
        assert resource_manager.get_available_memory() == 8  # 16 - 8

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_allocate_resources_insufficient_cores(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
        tmp_dir: Path,
    ):
        """Test resource allocation failure due to insufficient cores."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        # Create task that requires more cores than available
        task = ExecutableTask(
            task_name="test_task",
            original_task_name="test_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="test_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=16,  # More than global max of 8
            max_memory=8,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        # Allocate resources
        success = resource_manager.allocate_resources(task)

        assert success is False
        assert resource_manager.allocated_cores == 0
        assert resource_manager.allocated_memory == 0
        assert resource_manager.task_allocations == {}

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_allocate_resources_insufficient_memory(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
        tmp_dir: Path,
    ):
        """Test resource allocation failure due to insufficient memory."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        # Create task that requires more memory than available
        task = ExecutableTask(
            task_name="test_task",
            original_task_name="test_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="test_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=4,
            max_memory=32,  # More than global max of 16
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        # Allocate resources
        success = resource_manager.allocate_resources(task)

        assert success is False
        assert resource_manager.allocated_cores == 0
        assert resource_manager.allocated_memory == 0
        assert resource_manager.task_allocations == {}

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_allocate_resources_double_allocation(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
        tmp_dir: Path,
    ):
        """Test resource allocation failure when task already has resources allocated."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        # Create test task
        task = ExecutableTask(
            task_name="test_task",
            original_task_name="test_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="test_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=4,
            max_memory=8,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        # First allocation should succeed
        success1 = resource_manager.allocate_resources(task)
        assert success1 is True

        # Second allocation should fail
        success2 = resource_manager.allocate_resources(task)
        assert success2 is False

        # Resources should still be allocated once
        assert resource_manager.allocated_cores == 4
        assert resource_manager.allocated_memory == 8
        assert resource_manager.task_allocations["test_task"] == (4, 8)

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_release_resources_success(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
        tmp_dir: Path,
    ):
        """Test successful resource release."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        # Create test task
        task = ExecutableTask(
            task_name="test_task",
            original_task_name="test_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="test_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=4,
            max_memory=8,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        # Allocate resources first
        resource_manager.allocate_resources(task)
        assert resource_manager.allocated_cores == 4
        assert resource_manager.allocated_memory == 8

        # Release resources
        resource_manager.release_resources(task)

        assert resource_manager.allocated_cores == 0
        assert resource_manager.allocated_memory == 0
        assert resource_manager.task_allocations == {}
        assert resource_manager.get_available_cores() == 8
        assert resource_manager.get_available_memory() == 16

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_release_resources_not_allocated(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
        tmp_dir: Path,
    ):
        """Test resource release when task was not allocated."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        # Create test task
        task = ExecutableTask(
            task_name="test_task",
            original_task_name="test_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="test_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=4,
            max_memory=8,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        # Release resources without allocating first
        resource_manager.release_resources(task)

        # Should log error and not change state
        mock_notification.error.assert_called_once()
        assert resource_manager.allocated_cores == 0
        assert resource_manager.allocated_memory == 0
        assert resource_manager.task_allocations == {}

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_release_resources_prevents_negative_allocation(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
        tmp_dir: Path,
    ):
        """Test that resource release prevents negative allocation values."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        # Create test task
        task = ExecutableTask(
            task_name="test_task",
            original_task_name="test_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="test_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=4,
            max_memory=8,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        # Manually add task allocation and set negative values to test edge case
        resource_manager.task_allocations["test_task"] = (4, 8)
        resource_manager.allocated_cores = 2  # Less than what will be released
        resource_manager.allocated_memory = 4  # Less than what will be released

        # Release resources
        resource_manager.release_resources(task)

        # Should not go negative
        assert resource_manager.allocated_cores == 0
        assert resource_manager.allocated_memory == 0
        assert resource_manager.task_allocations == {}


class TestTaskScheduling:
    """Test task scheduling algorithms."""

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_can_schedule_task_success(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
        tmp_dir: Path,
    ):
        """Test successful task scheduling check."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        # Create test task within limits
        task = ExecutableTask(
            task_name="test_task",
            original_task_name="test_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="test_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=4,
            max_memory=8,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        assert resource_manager.can_schedule_task(task) is True

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_can_schedule_task_insufficient_resources(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
        tmp_dir: Path,
    ):
        """Test task scheduling check with insufficient resources."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        # Create test task that exceeds limits
        task = ExecutableTask(
            task_name="test_task",
            original_task_name="test_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="test_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=16,  # More than global max of 8
            max_memory=8,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        assert resource_manager.can_schedule_task(task) is False

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_get_next_schedulable_tasks_empty_list(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
    ):
        """Test scheduling with empty pending tasks list."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        schedulable_tasks = resource_manager.get_next_schedulable_tasks([])

        assert schedulable_tasks == []

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_get_next_schedulable_tasks_fifo_scheduling(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
        tmp_dir: Path,
    ):
        """Test FIFO (First-In-First-Out) task scheduling algorithm."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe, SchedulingStrategy.FIFO)

        # Create tasks with different resource requirements
        task_small = ExecutableTask(
            task_name="small_task",
            original_task_name="small_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="small_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=2,
            max_memory=4,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        task_large = ExecutableTask(
            task_name="large_task",
            original_task_name="large_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="large_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=8,
            max_memory=16,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        # Test FIFO scheduling: tasks selected in original order
        pending_tasks = [task_large, task_small]  # Order: large, small
        schedulable_tasks = resource_manager.get_next_schedulable_tasks(pending_tasks)

        # With FIFO, should select task_large first (it exactly fits: 8+16 = 24 <= 8+16 available)
        assert len(schedulable_tasks) == 1
        assert schedulable_tasks[0].task_name == "large_task"

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_get_next_schedulable_tasks_sjf_scheduling(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
        tmp_dir: Path,
    ):
        """Test SJF (Shortest Job First) task scheduling algorithm."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe, SchedulingStrategy.SJF)

        # Create tasks with different resource requirements
        task_small = ExecutableTask(
            task_name="small_task",
            original_task_name="small_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="small_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=2,
            max_memory=4,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        task_medium = ExecutableTask(
            task_name="medium_task",
            original_task_name="medium_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="medium_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=4,
            max_memory=8,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        task_large = ExecutableTask(
            task_name="large_task",
            original_task_name="large_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="large_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=8,
            max_memory=16,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        # Test SJF scheduling: tasks selected by smallest resource requirements first
        pending_tasks = [
            task_large,
            task_medium,
            task_small,
        ]  # Order: large, medium, small
        schedulable_tasks = resource_manager.get_next_schedulable_tasks(pending_tasks)

        # With SJF, should select small and medium tasks (small: 2+4=6, medium: 4+8=12, total=18 <= 24)
        assert len(schedulable_tasks) == 2
        assert schedulable_tasks[0].task_name == "small_task"  # Smallest first
        assert schedulable_tasks[1].task_name == "medium_task"  # Next smallest

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_get_next_schedulable_tasks_ljf_scheduling(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
        tmp_dir: Path,
    ):
        """Test LJF (Longest Job First) task scheduling algorithm."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe, SchedulingStrategy.LJF)

        # Create tasks with different resource requirements
        task_small = ExecutableTask(
            task_name="small_task",
            original_task_name="small_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="small_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=2,
            max_memory=4,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        task_large = ExecutableTask(
            task_name="large_task",
            original_task_name="large_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="large_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=8,
            max_memory=16,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        # Test LJF scheduling: tasks selected by largest resource requirements first
        pending_tasks = [task_small, task_large]  # Order: small, large
        schedulable_tasks = resource_manager.get_next_schedulable_tasks(pending_tasks)

        # With LJF, should select large task first (it exactly fits: 8+16 = 24 <= 8+16 available)
        assert len(schedulable_tasks) == 1
        assert schedulable_tasks[0].task_name == "large_task"  # Largest first

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_get_next_schedulable_tasks_partial_selection(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
        tmp_dir: Path,
    ):
        """Test partial task selection when not all tasks fit."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        # Pre-allocate some resources to limit available resources
        dummy_task = ExecutableTask(
            task_name="dummy_task",
            original_task_name="dummy_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="dummy_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=4,
            max_memory=8,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )
        resource_manager.allocate_resources(dummy_task)

        # Now we have 4 cores and 8GB available

        # Create tasks
        task_small = ExecutableTask(
            task_name="small_task",
            original_task_name="small_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="small_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=2,
            max_memory=4,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        task_large = ExecutableTask(
            task_name="large_task",
            original_task_name="large_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="large_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=8,
            max_memory=16,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        # Test scheduling
        pending_tasks = [task_large, task_small]
        schedulable_tasks = resource_manager.get_next_schedulable_tasks(pending_tasks)

        # Should only select small task (large task won't fit)
        assert len(schedulable_tasks) == 1
        assert schedulable_tasks[0].task_name == "small_task"

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_get_next_schedulable_tasks_no_schedulable_tasks(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
        tmp_dir: Path,
    ):
        """Test scheduling when no tasks can be scheduled."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        # Allocate all resources
        dummy_task = ExecutableTask(
            task_name="dummy_task",
            original_task_name="dummy_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="dummy_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=8,
            max_memory=16,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )
        resource_manager.allocate_resources(dummy_task)

        # Create task that won't fit
        task_large = ExecutableTask(
            task_name="large_task",
            original_task_name="large_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="large_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=4,
            max_memory=8,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        # Test scheduling
        pending_tasks = [task_large]
        schedulable_tasks = resource_manager.get_next_schedulable_tasks(pending_tasks)

        assert len(schedulable_tasks) == 0


class TestResourceQueries:
    """Test resource availability and allocation queries."""

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_resource_queries_initial_state(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
    ):
        """Test resource queries in initial state."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        assert resource_manager.get_available_cores() == 8
        assert resource_manager.get_available_memory() == 16
        assert resource_manager.get_allocated_cores() == 0
        assert resource_manager.get_allocated_memory() == 0

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_resource_queries_after_allocation(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
        tmp_dir: Path,
    ):
        """Test resource queries after allocation."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        # Allocate resources
        task = ExecutableTask(
            task_name="test_task",
            original_task_name="test_task",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="test_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=4,
            max_memory=8,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )
        resource_manager.allocate_resources(task)

        assert resource_manager.get_available_cores() == 4  # 8 - 4
        assert resource_manager.get_available_memory() == 8  # 16 - 8
        assert resource_manager.get_allocated_cores() == 4
        assert resource_manager.get_allocated_memory() == 8

    @patch("batch_tamarin.modules.resource_manager.resolve_resource_value")
    @patch("batch_tamarin.modules.resource_manager.os.cpu_count")
    @patch("batch_tamarin.modules.resource_manager.psutil.virtual_memory")
    @patch("batch_tamarin.modules.resource_manager.notification_manager")
    def test_resource_queries_multiple_allocations(
        self,
        mock_notification: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_count: Mock,
        mock_resolve: Mock,
        minimal_recipe_data: Dict[str, Any],
        tmp_dir: Path,
    ):
        """Test resource queries with multiple allocations."""
        # Mock system resources
        mock_cpu_count.return_value = 16
        mock_virtual_memory.return_value = Mock(total=64 * 1024**3)
        mock_resolve.side_effect = lambda x, _: x  # type: ignore

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        resource_manager = ResourceManager(recipe)

        # Allocate resources for multiple tasks
        task1 = ExecutableTask(
            task_name="task1",
            original_task_name="task1",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="lemma1",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=2,
            max_memory=4,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        task2 = ExecutableTask(
            task_name="task2",
            original_task_name="task2",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="lemma2",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=3,
            max_memory=6,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        resource_manager.allocate_resources(task1)
        resource_manager.allocate_resources(task2)

        assert resource_manager.get_available_cores() == 3  # 8 - 2 - 3
        assert resource_manager.get_available_memory() == 6  # 16 - 4 - 6
        assert resource_manager.get_allocated_cores() == 5  # 2 + 3
        assert resource_manager.get_allocated_memory() == 10  # 4 + 6
