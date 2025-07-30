"""
Tests for BatchManager class.

This module tests the BatchManager functionality including batch creation,
execution report generation, and data transformation from TaskRunner results.
All external dependencies are mocked for CI compatibility.
"""

# pyright: basic

from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import Mock, patch

import pytest

from batch_tamarin.model.batch import (
    Batch,
    ErrorType,
    ExecMetadata,
    LemmaResult,
    TaskFailedResult,
    TaskStatus,
    TaskSucceedResult,
)
from batch_tamarin.model.executable_task import (
    ExecutableTask,
    MemoryStats,
    TaskResult,
)
from batch_tamarin.model.executable_task import TaskStatus as ExecutableTaskStatus
from batch_tamarin.model.tamarin_recipe import TamarinRecipe
from batch_tamarin.modules.batch_manager import BatchManager
from batch_tamarin.modules.output_manager import LemmaResult as OutputLemmaResult
from batch_tamarin.modules.output_manager import SuccessfulTaskResult, WrapperMeasures
from batch_tamarin.modules.task_manager import ExecutionSummary


class TestBatchManagerInitialization:
    """Test BatchManager initialization."""

    def test_batch_manager_init(
        self, minimal_recipe_data: Dict[str, Any], sample_tamarin_executable: Path
    ):
        """Test BatchManager initialization with recipe and name."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        assert batch_manager.recipe == recipe
        assert batch_manager.recipe_name == "test_recipe.json"


class TestBatchCreation:
    """Test batch creation and configuration resolution."""

    @pytest.mark.asyncio
    async def test_create_batch_with_resolved_config(
        self, minimal_recipe_data: Dict[str, Any]
    ):
        """Test creating batch with resolved configuration."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        # Mock the dependencies
        with (
            patch(
                "batch_tamarin.modules.batch_manager.resolve_resource_value"
            ) as mock_resolve,
            patch(
                "batch_tamarin.modules.batch_manager.resolve_executable_path"
            ) as mock_resolve_path,
            patch(
                "batch_tamarin.modules.batch_manager.extract_tamarin_version"
            ) as mock_extract_version,
        ):

            # Return input unchanged
            mock_resolve.side_effect = lambda x, _: x  # type:ignore
            mock_resolve_path.return_value = Path("/mock/tamarin-prover")
            mock_extract_version.return_value = "1.10.0"

            batch = (
                await batch_manager._create_batch_with_resolved_config()  # type:ignore
            )

            assert batch.recipe == "test_recipe.json"
            assert batch.config.global_max_cores == 8
            assert batch.config.global_max_memory == 16
            assert "stable" in batch.tamarin_versions
            assert batch.tamarin_versions["stable"].version == "1.10.0"
            assert batch.execution_metadata.total_tasks == 0
            assert batch.tasks == {}

    @pytest.mark.asyncio
    async def test_create_batch_with_tamarin_version_extraction_failure(
        self, minimal_recipe_data: Dict[str, Any]
    ):
        """Test batch creation when tamarin version extraction fails."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        with (
            patch(
                "batch_tamarin.modules.batch_manager.resolve_resource_value"
            ) as mock_resolve,
            patch(
                "batch_tamarin.modules.batch_manager.resolve_executable_path"
            ) as mock_resolve_path,
            patch(
                "batch_tamarin.modules.batch_manager.extract_tamarin_version"
            ) as mock_extract_version,
        ):

            mock_resolve.side_effect = lambda x, _: x  # type:ignore
            mock_resolve_path.return_value = Path("/mock/tamarin-prover")
            mock_extract_version.side_effect = Exception("Version extraction failed")

            batch = (
                await batch_manager._create_batch_with_resolved_config()  # type:ignore
            )

            assert batch.tamarin_versions["stable"].version is None

    @pytest.mark.asyncio
    async def test_create_batch_with_resource_resolution(
        self, minimal_recipe_data: Dict[str, Any]
    ):
        """Test batch creation with resource value resolution."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        with (
            patch(
                "batch_tamarin.modules.batch_manager.resolve_resource_value"
            ) as mock_resolve,
            patch(
                "batch_tamarin.modules.batch_manager.resolve_executable_path"
            ) as mock_resolve_path,
            patch(
                "batch_tamarin.modules.batch_manager.extract_tamarin_version"
            ) as mock_extract_version,
        ):

            # Mock resource resolution to return different values
            def mock_resolve_fn(value: int, resource_type: str) -> int:
                if resource_type == "cores":
                    return 16  # Mock resolved cores
                elif resource_type == "memory":
                    return 32  # Mock resolved memory
                return value

            mock_resolve.side_effect = mock_resolve_fn
            mock_resolve_path.return_value = Path("/mock/tamarin-prover")
            mock_extract_version.return_value = "1.10.0"

            batch = (
                await batch_manager._create_batch_with_resolved_config()  # type:ignore
            )

            assert batch.config.global_max_cores == 16
            assert batch.config.global_max_memory == 32


class TestBatchPopulation:
    """Test batch population with execution results."""

    def test_populate_batch_with_results(
        self, minimal_recipe_data: Dict[str, Any], tmp_dir: Path
    ):
        """Test populating batch with execution results."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        # Create mock batch
        batch = Batch(
            recipe="test_recipe.json",
            config=recipe.config,
            tamarin_versions=recipe.tamarin_versions,
            execution_metadata=ExecMetadata(
                total_tasks=0,
                total_successes=0,
                total_failures=0,
                total_cache_hit=0,
                total_runtime=0,
                total_memory=0,
                max_runtime=0,
                max_memory=0,
            ),
            tasks={},
        )

        # Create mock TaskRunner
        mock_runner = Mock()
        mock_runner.completed_tasks = {"task1", "task2"}
        mock_runner.failed_tasks = {"task3"}
        mock_runner.task_results = {
            "task1": TaskResult(
                task_id="task1",
                status=ExecutableTaskStatus.COMPLETED,
                return_code=0,
                stdout="Success",
                stderr="",
                start_time=1000.0,
                end_time=1100.0,
                duration=100.0,
                memory_stats=MemoryStats(peak_memory_mb=512.0, avg_memory_mb=256.0),
            ),
            "task2": TaskResult(
                task_id="task2",
                status=ExecutableTaskStatus.COMPLETED,
                return_code=0,
                stdout="Success",
                stderr="",
                start_time=1200.0,
                end_time=1350.0,
                duration=150.0,
                memory_stats=MemoryStats(peak_memory_mb=1024.0, avg_memory_mb=512.0),
            ),
        }

        # Mock ExecutionSummary
        mock_execution_summary = ExecutionSummary(
            total_tasks=3,
            successful_tasks=2,
            failed_tasks=1,
            total_duration=250.0,
            task_results=list(mock_runner.task_results.values()),
            cached_tasks=1,
            cached_task_ids={"task1"},
        )
        mock_runner.task_manager.generate_execution_summary.return_value = (
            mock_execution_summary
        )

        # Create mock executable tasks
        executable_tasks = [
            ExecutableTask(
                task_name="task1",
                original_task_name="task1",
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
            ),
            ExecutableTask(
                task_name="task2",
                original_task_name="task2",
                tamarin_version_name="stable",
                tamarin_executable=tmp_dir / "tamarin-prover",
                theory_file=tmp_dir / "theory.spthy",
                output_file=tmp_dir / "output.txt",
                lemma="test_lemma2",
                tamarin_options=None,
                preprocess_flags=None,
                max_cores=4,
                max_memory=8,
                task_timeout=3600,
                traces_dir=tmp_dir / "traces",
            ),
        ]

        # Execute population
        batch_manager._populate_batch_with_results(  # type: ignore
            batch, mock_runner, executable_tasks
        )

        # Verify execution metadata
        assert batch.execution_metadata.total_tasks == 2
        assert batch.execution_metadata.total_successes == 2
        assert batch.execution_metadata.total_failures == 1
        assert batch.execution_metadata.total_cache_hit == 1
        assert batch.execution_metadata.total_runtime == 250.0
        assert batch.execution_metadata.total_memory == 1536.0  # 512 + 1024
        assert batch.execution_metadata.max_runtime == 150.0
        assert batch.execution_metadata.max_memory == 1024.0

    def test_populate_batch_with_no_memory_stats(
        self, minimal_recipe_data: Dict[str, Any], tmp_dir: Path
    ):
        """Test populating batch when task results have no memory stats."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        batch = Batch(
            recipe="test_recipe.json",
            config=recipe.config,
            tamarin_versions=recipe.tamarin_versions,
            execution_metadata=ExecMetadata(
                total_tasks=0,
                total_successes=0,
                total_failures=0,
                total_cache_hit=0,
                total_runtime=0,
                total_memory=0,
                max_runtime=0,
                max_memory=0,
            ),
            tasks={},
        )

        mock_runner = Mock()
        mock_runner.completed_tasks = {"task1"}
        mock_runner.failed_tasks = set()
        mock_runner.task_results = {
            "task1": TaskResult(
                task_id="task1",
                status=ExecutableTaskStatus.COMPLETED,
                return_code=0,
                stdout="Success",
                stderr="",
                start_time=1000.0,
                end_time=1100.0,
                duration=100.0,
                memory_stats=None,  # No memory stats
            )
        }

        mock_execution_summary = ExecutionSummary(
            total_tasks=1,
            successful_tasks=1,
            failed_tasks=0,
            total_duration=100.0,
            task_results=list(mock_runner.task_results.values()),
            cached_tasks=0,
            cached_task_ids=set(),
        )
        mock_runner.task_manager.generate_execution_summary.return_value = (
            mock_execution_summary
        )

        executable_tasks = [
            ExecutableTask(
                task_name="task1",
                original_task_name="task1",
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
        ]

        batch_manager._populate_batch_with_results(  # type:ignore
            batch, mock_runner, executable_tasks
        )

        assert batch.execution_metadata.total_memory == 0.0
        assert batch.execution_metadata.max_memory == 0.0


class TestRichTaskCreation:
    """Test creation of RichTask objects from ExecutableTask instances."""

    def test_create_rich_tasks_from_executable_tasks(
        self, minimal_recipe_data: Dict[str, Any], tmp_dir: Path
    ):
        """Test creating RichTask objects from ExecutableTask instances."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        # Create mock runner with results
        mock_runner = Mock()
        mock_runner.task_results = {
            "task1--lemma1--stable": TaskResult(
                task_id="task1--lemma1--stable",
                status=ExecutableTaskStatus.COMPLETED,
                return_code=0,
                stdout="Success",
                stderr="",
                start_time=1000.0,
                end_time=1100.0,
                duration=100.0,
                memory_stats=MemoryStats(peak_memory_mb=512.0, avg_memory_mb=256.0),
            ),
            "task1--lemma2--stable": TaskResult(
                task_id="task1--lemma2--stable",
                status=ExecutableTaskStatus.FAILED,
                return_code=1,
                stdout="",
                stderr="Error occurred",
                start_time=1200.0,
                end_time=1250.0,
                duration=50.0,
                memory_stats=None,
            ),
        }

        mock_execution_summary = ExecutionSummary(
            total_tasks=2,
            successful_tasks=1,
            failed_tasks=1,
            total_duration=150.0,
            task_results=list(mock_runner.task_results.values()),
            cached_tasks=0,
            cached_task_ids=set(),
        )

        # Create executable tasks
        executable_tasks = [
            ExecutableTask(
                task_name="task1--lemma1--stable",
                original_task_name="task1",
                tamarin_version_name="stable",
                tamarin_executable=tmp_dir / "tamarin-prover",
                theory_file=tmp_dir / "theory.spthy",
                output_file=tmp_dir / "output.txt",
                lemma="lemma1",
                tamarin_options=["--heuristic=S"],
                preprocess_flags=["FLAG1"],
                max_cores=4,
                max_memory=8,
                task_timeout=3600,
                traces_dir=tmp_dir / "traces",
            ),
            ExecutableTask(
                task_name="task1--lemma2--stable",
                original_task_name="task1",
                tamarin_version_name="stable",
                tamarin_executable=tmp_dir / "tamarin-prover",
                theory_file=tmp_dir / "theory.spthy",
                output_file=tmp_dir / "output.txt",
                lemma="lemma2",
                tamarin_options=None,
                preprocess_flags=None,
                max_cores=4,
                max_memory=8,
                task_timeout=3600,
                traces_dir=tmp_dir / "traces",
            ),
        ]

        rich_tasks = (
            batch_manager._create_rich_tasks_from_executable_tasks(  # type:ignore
                executable_tasks, mock_runner, mock_execution_summary
            )
        )

        assert len(rich_tasks) == 1
        assert "task1" in rich_tasks

        rich_task = rich_tasks["task1"]
        assert rich_task.theory_file == str(tmp_dir / "theory.spthy")
        assert len(rich_task.subtasks) == 2
        assert "task1--lemma1--stable" in rich_task.subtasks
        assert "task1--lemma2--stable" in rich_task.subtasks

    def test_create_rich_executable_task_with_result(
        self, minimal_recipe_data: Dict[str, Any], tmp_dir: Path
    ):
        """Test creating RichExecutableTask with task result."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        mock_runner = Mock()
        task_result = TaskResult(
            task_id="task1--lemma1--stable",
            status=ExecutableTaskStatus.COMPLETED,
            return_code=0,
            stdout="Success",
            stderr="",
            start_time=1000.0,
            end_time=1100.0,
            duration=100.0,
            memory_stats=MemoryStats(peak_memory_mb=512.0, avg_memory_mb=256.0),
        )
        mock_runner.task_results = {"task1--lemma1--stable": task_result}

        mock_execution_summary = ExecutionSummary(
            total_tasks=1,
            successful_tasks=1,
            failed_tasks=0,
            total_duration=100.0,
            task_results=[task_result],
            cached_tasks=1,
            cached_task_ids={"task1--lemma1--stable"},
        )

        executable_task = ExecutableTask(
            task_name="task1--lemma1--stable",
            original_task_name="task1",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="lemma1",
            tamarin_options=["--heuristic=S"],
            preprocess_flags=["FLAG1"],
            max_cores=4,
            max_memory=8,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        with patch.object(
            batch_manager, "_create_task_succeed_result"
        ) as mock_create_success:
            mock_create_success.return_value = TaskSucceedResult(
                warnings=[],
                real_time_tamarin_measure=95.0,
                lemma_result=LemmaResult.VERIFIED,
                steps=1000,
                analysis_type="all-traces",
            )

            rich_executable_task = (
                batch_manager._create_rich_executable_task(  # type:ignore
                    executable_task, mock_runner, mock_execution_summary
                )
            )

            assert rich_executable_task.task_config.tamarin_alias == "stable"
            assert rich_executable_task.task_config.lemma == "lemma1"
            assert rich_executable_task.task_config.options == ["--heuristic=S"]
            assert rich_executable_task.task_config.preprocessor_flags == ["FLAG1"]
            assert rich_executable_task.task_config.resources.cores == 4
            assert rich_executable_task.task_config.resources.memory == 8
            assert rich_executable_task.task_config.resources.timeout == 3600

            assert (
                rich_executable_task.task_execution_metadata.status
                == TaskStatus.COMPLETED
            )
            assert rich_executable_task.task_execution_metadata.cache_hit is True
            assert (
                rich_executable_task.task_execution_metadata.exec_duration_monotonic
                == 100.0
            )
            assert rich_executable_task.task_execution_metadata.avg_memory == 256.0
            assert rich_executable_task.task_execution_metadata.peak_memory == 512.0

            assert isinstance(rich_executable_task.task_result, TaskSucceedResult)

    def test_create_rich_executable_task_without_result(
        self, minimal_recipe_data: Dict[str, Any], tmp_dir: Path
    ):
        """Test creating RichExecutableTask without task result."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        mock_runner = Mock()
        mock_runner.task_results = {}  # No results

        mock_execution_summary = ExecutionSummary(
            total_tasks=1,
            successful_tasks=0,
            failed_tasks=0,
            total_duration=0.0,
            task_results=[],
            cached_tasks=0,
            cached_task_ids=set(),
        )

        executable_task = ExecutableTask(
            task_name="task1--lemma1--stable",
            original_task_name="task1",
            tamarin_version_name="stable",
            tamarin_executable=tmp_dir / "tamarin-prover",
            theory_file=tmp_dir / "theory.spthy",
            output_file=tmp_dir / "output.txt",
            lemma="lemma1",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=4,
            max_memory=8,
            task_timeout=3600,
            traces_dir=tmp_dir / "traces",
        )

        rich_executable_task = (
            batch_manager._create_rich_executable_task(  # type:ignore
                executable_task, mock_runner, mock_execution_summary
            )
        )

        assert rich_executable_task.task_execution_metadata.status == TaskStatus.PENDING
        assert rich_executable_task.task_execution_metadata.cache_hit is False
        assert (
            rich_executable_task.task_execution_metadata.exec_duration_monotonic == 0.0
        )
        assert rich_executable_task.task_execution_metadata.avg_memory == 0.0
        assert rich_executable_task.task_execution_metadata.peak_memory == 0.0
        assert rich_executable_task.task_result is None


class TestStatusConversion:
    """Test status conversion between different task status types."""

    def test_convert_task_status_all_values(self):
        """Test converting all ExecutableTaskStatus values to TaskStatus."""
        recipe = TamarinRecipe.model_validate(
            {
                "config": {
                    "global_max_cores": 8,
                    "global_max_memory": 16,
                    "default_timeout": 3600,
                    "output_directory": "./test",
                },
                "tamarin_versions": {"stable": {"path": "/fake/path"}},
                "tasks": {
                    "test": {
                        "theory_file": "/fake/theory.spthy",
                        "tamarin_versions": ["stable"],
                        "output_file_prefix": "test",
                    }
                },
            }
        )
        batch_manager = BatchManager(recipe, "test_recipe.json")

        # Test all status mappings
        assert (
            batch_manager._convert_task_status(  # type:ignore
                ExecutableTaskStatus.PENDING
            )
            == TaskStatus.PENDING
        )
        assert (
            batch_manager._convert_task_status(  # type:ignore
                ExecutableTaskStatus.RUNNING
            )
            == TaskStatus.RUNNING
        )
        assert (
            batch_manager._convert_task_status(  # type:ignore
                ExecutableTaskStatus.COMPLETED
            )
            == TaskStatus.COMPLETED
        )
        assert (
            batch_manager._convert_task_status(  # type:ignore
                ExecutableTaskStatus.FAILED
            )
            == TaskStatus.FAILED
        )
        assert (
            batch_manager._convert_task_status(  # type:ignore
                ExecutableTaskStatus.TIMEOUT
            )
            == TaskStatus.TIMEOUT
        )
        assert (
            batch_manager._convert_task_status(  # type:ignore
                ExecutableTaskStatus.MEMORY_LIMIT_EXCEEDED
            )
            == TaskStatus.MEMORY_LIMIT_EXCEEDED
        )


class TestTaskResultCreation:
    """Test creation of task results from TaskResult instances."""

    def test_create_task_succeed_result(self, minimal_recipe_data: Dict[str, Any]):
        """Test creating TaskSucceedResult from TaskResult."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        task_result = TaskResult(
            task_id="task1--lemma1--stable",
            status=ExecutableTaskStatus.COMPLETED,
            return_code=0,
            stdout="Success",
            stderr="",
            start_time=1000.0,
            end_time=1100.0,
            duration=100.0,
            memory_stats=MemoryStats(peak_memory_mb=512.0, avg_memory_mb=256.0),
        )

        # Mock output_manager parsing
        mock_parsed_result = SuccessfulTaskResult(
            task_id="task1--lemma1--stable",
            warnings=["Warning: deprecated syntax"],
            tamarin_timing=95.0,
            wrapper_measures=WrapperMeasures(
                time=100.0, avg_memory=256.0, peak_memory=512.0
            ),
            output_spthy="output.spthy",
            verified_lemma={
                "lemma1": OutputLemmaResult(steps=1000, analysis_type="all-traces")
            },
            falsified_lemma={},
            unterminated_lemma=[],
        )

        with patch(
            "batch_tamarin.modules.batch_manager.output_manager"
        ) as mock_output_manager:
            mock_output_manager.parse_task_result.return_value = mock_parsed_result

            result = batch_manager._create_task_succeed_result(  # type:ignore
                task_result
            )

            assert isinstance(result, TaskSucceedResult)
            assert result.warnings == ["Warning: deprecated syntax"]
            assert result.real_time_tamarin_measure == 95.0
            assert result.lemma_result == LemmaResult.VERIFIED
            assert result.steps == 1000
            assert result.analysis_type == "all-traces"

    def test_create_task_succeed_result_with_falsified_lemma(
        self, minimal_recipe_data: Dict[str, Any]
    ):
        """Test creating TaskSucceedResult with falsified lemma."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        task_result = TaskResult(
            task_id="task1--lemma1--stable",
            status=ExecutableTaskStatus.COMPLETED,
            return_code=0,
            stdout="Success",
            stderr="",
            start_time=1000.0,
            end_time=1100.0,
            duration=100.0,
            memory_stats=None,
        )

        mock_parsed_result = SuccessfulTaskResult(
            task_id="task1--lemma1--stable",
            warnings=[],
            tamarin_timing=95.0,
            wrapper_measures=WrapperMeasures(
                time=100.0, avg_memory=256.0, peak_memory=512.0
            ),
            output_spthy="output.spthy",
            verified_lemma={},
            falsified_lemma={
                "lemma1": OutputLemmaResult(steps=500, analysis_type="exists-trace")
            },
            unterminated_lemma=[],
        )

        with patch(
            "batch_tamarin.modules.batch_manager.output_manager"
        ) as mock_output_manager:
            mock_output_manager.parse_task_result.return_value = mock_parsed_result

            result = batch_manager._create_task_succeed_result(  # type:ignore
                task_result
            )

            assert result.lemma_result == LemmaResult.FALSIFIED
            assert result.steps == 500
            assert result.analysis_type == "exists-trace"

    def test_create_task_succeed_result_with_unterminated_lemma(
        self, minimal_recipe_data: Dict[str, Any]
    ):
        """Test creating TaskSucceedResult with unterminated lemma."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        task_result = TaskResult(
            task_id="task1--lemma1--stable",
            status=ExecutableTaskStatus.COMPLETED,
            return_code=0,
            stdout="Success",
            stderr="",
            start_time=1000.0,
            end_time=1100.0,
            duration=100.0,
            memory_stats=None,
        )

        mock_parsed_result = SuccessfulTaskResult(
            task_id="task1--lemma1--stable",
            warnings=[],
            tamarin_timing=95.0,
            wrapper_measures=WrapperMeasures(
                time=100.0, avg_memory=256.0, peak_memory=512.0
            ),
            output_spthy="output.spthy",
            verified_lemma={},
            falsified_lemma={},
            unterminated_lemma=["lemma1"],
        )

        with patch(
            "batch_tamarin.modules.batch_manager.output_manager"
        ) as mock_output_manager:
            mock_output_manager.parse_task_result.return_value = mock_parsed_result

            result = batch_manager._create_task_succeed_result(  # type:ignore
                task_result
            )

            assert result.lemma_result == LemmaResult.UNTERMINATED

    def test_create_task_succeed_result_with_unparseable_output(
        self, minimal_recipe_data: Dict[str, Any]
    ):
        """Test creating TaskSucceedResult when output parsing fails."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        task_result = TaskResult(
            task_id="task1--lemma1--stable",
            status=ExecutableTaskStatus.COMPLETED,
            return_code=0,
            stdout="Success",
            stderr="",
            start_time=1000.0,
            end_time=1100.0,
            duration=100.0,
            memory_stats=None,
        )

        with patch(
            "batch_tamarin.modules.batch_manager.output_manager"
        ) as mock_output_manager:
            mock_output_manager.parse_task_result.return_value = None  # Parsing failed

            result = batch_manager._create_task_succeed_result(  # type:ignore
                task_result
            )

            assert isinstance(result, TaskSucceedResult)
            assert result.warnings == []
            assert (
                result.real_time_tamarin_measure == 100.0
            )  # Falls back to task duration
            assert result.lemma_result == LemmaResult.VERIFIED
            assert result.steps == 0
            assert result.analysis_type == "unknown"

    def test_create_task_failed_result_timeout(
        self, minimal_recipe_data: Dict[str, Any]
    ):
        """Test creating TaskFailedResult for timeout."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        task_result = TaskResult(
            task_id="task1--lemma1--stable",
            status=ExecutableTaskStatus.TIMEOUT,
            return_code=124,
            stdout="",
            stderr="Process timed out",
            start_time=1000.0,
            end_time=4600.0,
            duration=3600.0,
            memory_stats=None,
        )

        result = batch_manager._create_task_failed_result(  # type:ignore
            task_result
        )

        assert isinstance(result, TaskFailedResult)
        assert result.return_code == "124"
        assert result.error_type == ErrorType.TIMEOUT
        assert result.error_description == "Task timed out during execution"
        assert result.last_stderr_lines == ["Process timed out"]

    def test_create_task_failed_result_memory_limit(
        self, minimal_recipe_data: Dict[str, Any]
    ):
        """Test creating TaskFailedResult for memory limit exceeded."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        task_result = TaskResult(
            task_id="task1--lemma1--stable",
            status=ExecutableTaskStatus.MEMORY_LIMIT_EXCEEDED,
            return_code=137,
            stdout="",
            stderr="Out of memory",
            start_time=1000.0,
            end_time=1500.0,
            duration=500.0,
            memory_stats=None,
        )

        result = batch_manager._create_task_failed_result(  # type:ignore
            task_result
        )

        assert result.error_type == ErrorType.MEMORY_LIMIT
        assert result.error_description == "Task exceeded memory limit"
        assert result.last_stderr_lines == ["Out of memory"]

    def test_create_task_failed_result_general_failure(
        self, minimal_recipe_data: Dict[str, Any]
    ):
        """Test creating TaskFailedResult for general failure."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        task_result = TaskResult(
            task_id="task1--lemma1--stable",
            status=ExecutableTaskStatus.FAILED,
            return_code=1,
            stdout="",
            stderr="Syntax error\nInvalid theory",
            start_time=1000.0,
            end_time=1050.0,
            duration=50.0,
            memory_stats=None,
        )

        result = batch_manager._create_task_failed_result(  # type:ignore
            task_result
        )

        assert result.error_type == ErrorType.TAMARIN_ERROR
        assert result.error_description == "Task failed with return code 1"
        assert result.last_stderr_lines == ["Syntax error", "Invalid theory"]

    def test_create_task_failed_result_long_stderr(
        self, minimal_recipe_data: Dict[str, Any]
    ):
        """Test creating TaskFailedResult with long stderr (should be truncated)."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        # Create stderr with more than 10 lines
        stderr_lines = [f"Error line {i}" for i in range(15)]
        stderr_text = "\n".join(stderr_lines)

        task_result = TaskResult(
            task_id="task1--lemma1--stable",
            status=ExecutableTaskStatus.FAILED,
            return_code=1,
            stdout="",
            stderr=stderr_text,
            start_time=1000.0,
            end_time=1050.0,
            duration=50.0,
            memory_stats=None,
        )

        result = batch_manager._create_task_failed_result(  # type:ignore
            task_result
        )

        # Should only keep last 10 lines
        assert len(result.last_stderr_lines) == 10
        # First of last 10
        assert result.last_stderr_lines[0] == "Error line 5"
        assert result.last_stderr_lines[-1] == "Error line 14"  # Last line


class TestUtilityMethods:
    """Test utility methods for name extraction and error description."""

    def test_extract_lemma_name_from_task_id(self, minimal_recipe_data: Dict[str, Any]):
        """Test extracting lemma name from task ID."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        # Test standard format
        assert (
            batch_manager._extract_lemma_name_from_task_id(  # type:ignore
                "task1--lemma1--stable"
            )
            == "lemma1"
        )
        assert (
            batch_manager._extract_lemma_name_from_task_id(  # type:ignore
                "complex_task--complex_lemma--dev"
            )
            == "complex_lemma"
        )

        # Test edge cases
        assert (
            batch_manager._extract_lemma_name_from_task_id(  # type:ignore
                "simple"
            )
            == "simple"
        )
        assert (
            batch_manager._extract_lemma_name_from_task_id(  # type:ignore
                "task--lemma"
            )
            == "task--lemma"
        )  # Only 2 parts, returns unchanged

    def test_get_error_description(self, minimal_recipe_data: Dict[str, Any]):
        """Test getting error description from task result."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        # Test timeout
        timeout_result = TaskResult(
            task_id="task1",
            status=ExecutableTaskStatus.TIMEOUT,
            return_code=124,
            stdout="",
            stderr="",
            start_time=1000.0,
            end_time=4600.0,
            duration=3600.0,
        )
        assert (
            batch_manager._get_error_description(  # type:ignore
                timeout_result
            )
            == "Task timed out during execution"
        )

        # Test memory limit
        memory_result = TaskResult(
            task_id="task1",
            status=ExecutableTaskStatus.MEMORY_LIMIT_EXCEEDED,
            return_code=137,
            stdout="",
            stderr="",
            start_time=1000.0,
            end_time=1500.0,
            duration=500.0,
        )
        assert (
            batch_manager._get_error_description(  # type:ignore
                memory_result
            )
            == "Task exceeded memory limit"
        )

        # Test general failure
        failed_result = TaskResult(
            task_id="task1",
            status=ExecutableTaskStatus.FAILED,
            return_code=1,
            stdout="",
            stderr="",
            start_time=1000.0,
            end_time=1050.0,
            duration=50.0,
        )
        assert (
            batch_manager._get_error_description(  # type:ignore
                failed_result
            )
            == "Task failed with return code 1"
        )


class TestExecutionReportGeneration:
    """Test complete execution report generation."""

    @pytest.mark.asyncio
    async def test_generate_execution_report_success(
        self, minimal_recipe_data: Dict[str, Any], tmp_dir: Path
    ):
        """Test successful execution report generation."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        # Mock all dependencies
        with (
            patch.object(
                batch_manager, "_create_batch_with_resolved_config"
            ) as mock_create_batch,
            patch.object(
                batch_manager, "_populate_batch_with_results"
            ) as mock_populate,
            patch.object(batch_manager, "_write_execution_report") as mock_write,
        ):

            mock_batch = Mock()
            mock_create_batch.return_value = mock_batch
            mock_write.return_value = None

            mock_runner = Mock()
            mock_executable_tasks: List[ExecutableTask] = []

            await batch_manager.generate_execution_report(
                mock_runner, mock_executable_tasks
            )

            mock_create_batch.assert_called_once()
            mock_populate.assert_called_once_with(
                mock_batch, mock_runner, mock_executable_tasks
            )
            mock_write.assert_called_once_with(mock_batch)

    @pytest.mark.asyncio
    async def test_generate_execution_report_with_exception(
        self, minimal_recipe_data: Dict[str, Any], tmp_dir: Path
    ):
        """Test execution report generation with exception (should not raise)."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        with (
            patch.object(
                batch_manager, "_create_batch_with_resolved_config"
            ) as mock_create_batch,
            patch(
                "batch_tamarin.modules.batch_manager.notification_manager"
            ) as mock_notification,
        ):

            mock_create_batch.side_effect = Exception("Test exception")

            mock_runner = Mock()
            mock_executable_tasks: List[ExecutableTask] = []

            # Should not raise exception
            await batch_manager.generate_execution_report(
                mock_runner, mock_executable_tasks
            )

            mock_notification.error.assert_called_once()
            assert (
                "Failed to generate execution report"
                in mock_notification.error.call_args[0][0]
            )

    @pytest.mark.asyncio
    async def test_write_execution_report_success(
        self, minimal_recipe_data: Dict[str, Any], tmp_dir: Path
    ):
        """Test writing execution report to file."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        # Create a mock batch
        mock_batch = Mock()
        mock_batch.model_dump_json.return_value = '{"test": "data"}'

        # Mock output_manager
        mock_output_paths = {"base": tmp_dir}

        with (
            patch(
                "batch_tamarin.modules.batch_manager.output_manager"
            ) as mock_output_manager,
            patch(
                "batch_tamarin.modules.batch_manager.notification_manager"
            ) as mock_notification,
        ):

            mock_output_manager.get_output_paths.return_value = mock_output_paths

            await batch_manager._write_execution_report(  # type:ignore
                mock_batch
            )

            # Verify file was written
            report_path = tmp_dir / "execution_report.json"
            assert report_path.exists()
            assert report_path.read_text() == '{"test": "data"}'

            mock_notification.success.assert_called_once()
            assert (
                "Generated execution report"
                in mock_notification.success.call_args[0][0]
            )

    @pytest.mark.asyncio
    async def test_write_execution_report_failure(
        self, minimal_recipe_data: Dict[str, Any], tmp_dir: Path
    ):
        """Test writing execution report with file write failure."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        batch_manager = BatchManager(recipe, "test_recipe.json")

        mock_batch = Mock()
        mock_batch.model_dump_json.return_value = '{"test": "data"}'

        # Mock output_manager to return a non-existent directory
        mock_output_paths = {"base": tmp_dir / "nonexistent"}

        with (
            patch(
                "batch_tamarin.modules.batch_manager.output_manager"
            ) as mock_output_manager,
            patch(
                "batch_tamarin.modules.batch_manager.notification_manager"
            ) as mock_notification,
        ):

            mock_output_manager.get_output_paths.return_value = mock_output_paths

            with pytest.raises(Exception):
                await batch_manager._write_execution_report(  # type:ignore
                    mock_batch
                )

            mock_notification.error.assert_called_once()
            assert (
                "Failed to write execution report"
                in mock_notification.error.call_args[0][0]
            )
