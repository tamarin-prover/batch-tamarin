"""
Tests for the batch model classes.

This module provides comprehensive tests for all batch model classes including:
- Resources model
- TaskConfig model
- TaskExecMetadata model
- TaskResult models (success/failed)
- RichExecutableTask model
- RichTask model
- Batch model
- Enum classes (TaskStatus, LemmaResult, ErrorType)
"""

# pyright: basic

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from batch_tamarin.model.batch import (
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
from batch_tamarin.model.tamarin_recipe import GlobalConfig, TamarinVersion


class TestResources:
    """Test cases for Resources model."""

    def test_resources_valid_creation(self):
        """Test creating valid Resources instance."""
        resources = Resources(cores=4, memory=8, timeout=3600)
        assert resources.cores == 4
        assert resources.memory == 8
        assert resources.timeout == 3600

    def test_resources_validation_errors(self):
        """Test Resources validation errors."""
        # Note: Resources model doesn't have validation constraints for negative values
        # This test documents the current behavior - negative values are accepted
        resources = Resources(cores=-1, memory=8, timeout=3600)
        assert resources.cores == -1

        resources = Resources(cores=4, memory=-1, timeout=3600)
        assert resources.memory == -1

        resources = Resources(cores=4, memory=8, timeout=-1)
        assert resources.timeout == -1

    def test_resources_json_serialization(self):
        """Test Resources JSON serialization."""
        resources = Resources(cores=8, memory=16, timeout=1800)
        json_data = resources.model_dump_json()
        parsed = json.loads(json_data)

        assert parsed["cores"] == 8
        assert parsed["memory"] == 16
        assert parsed["timeout"] == 1800


class TestTaskConfig:
    """Test cases for TaskConfig model."""

    def test_task_config_valid_creation(self, tmp_dir: Path):
        """Test creating valid TaskConfig instance."""
        theory_file = tmp_dir / "theory.spthy"
        theory_file.write_text("theory Test begin end")

        trace_file = tmp_dir / "trace.json"
        resources = Resources(cores=4, memory=8, timeout=3600)

        config = TaskConfig(
            tamarin_alias="stable",
            lemma="test_lemma",
            output_theory_file=theory_file,
            output_trace_file=trace_file,
            options=["--heuristic=S"],
            preprocessor_flags=["FLAG1"],
            resources=resources,
        )

        assert config.tamarin_alias == "stable"
        assert config.lemma == "test_lemma"
        assert config.output_theory_file == theory_file
        assert config.output_trace_file == trace_file
        assert config.options == ["--heuristic=S"]
        assert config.preprocessor_flags == ["FLAG1"]
        assert config.resources == resources

    def test_task_config_optional_fields(self, tmp_dir: Path):
        """Test TaskConfig with optional fields as None."""
        theory_file = tmp_dir / "theory.spthy"
        trace_file = tmp_dir / "trace.json"
        resources = Resources(cores=4, memory=8, timeout=3600)

        config = TaskConfig(
            tamarin_alias="stable",
            lemma="test_lemma",
            output_theory_file=theory_file,
            output_trace_file=trace_file,
            options=None,
            preprocessor_flags=None,
            resources=resources,
        )

        assert config.options is None
        assert config.preprocessor_flags is None


class TestTaskExecMetadata:
    """Test cases for TaskExecMetadata model."""

    def test_task_exec_metadata_valid_creation(self):
        """Test creating valid TaskExecMetadata instance."""
        metadata = TaskExecMetadata(
            command=["tamarin-prover", "theory.spthy"],
            status=TaskStatus.COMPLETED,
            cache_hit=False,
            exec_start="2024-01-01T12:00:00",
            exec_end="2024-01-01T12:05:00",
            exec_duration_monotonic=300.0,
            avg_memory=512.0,
            peak_memory=1024.0,
        )

        assert metadata.command == ["tamarin-prover", "theory.spthy"]
        assert metadata.status == TaskStatus.COMPLETED
        assert metadata.cache_hit is False
        assert metadata.exec_start == "2024-01-01T12:00:00"
        assert metadata.exec_end == "2024-01-01T12:05:00"
        assert metadata.exec_duration_monotonic == 300.0
        assert metadata.avg_memory == 512.0
        assert metadata.peak_memory == 1024.0

    def test_task_exec_metadata_with_cache_hit(self):
        """Test TaskExecMetadata with cache hit."""
        metadata = TaskExecMetadata(
            command=["tamarin-prover", "theory.spthy"],
            status=TaskStatus.COMPLETED,
            cache_hit=True,
            exec_start="2024-01-01T12:00:00",
            exec_end="2024-01-01T12:00:01",
            exec_duration_monotonic=0.1,
            avg_memory=0.0,
            peak_memory=0.0,
        )

        assert metadata.cache_hit is True
        assert metadata.exec_duration_monotonic == 0.1


class TestTaskSucceedResult:
    """Test cases for TaskSucceedResult model."""

    def test_task_succeed_result_valid_creation(self):
        """Test creating valid TaskSucceedResult instance."""
        result = TaskSucceedResult(
            warnings=["Warning: deprecated feature"],
            real_time_tamarin_measure=285.5,
            lemma_result=LemmaResult.VERIFIED,
            steps=1250,
            analysis_type="all-traces",
        )

        assert result.warnings == ["Warning: deprecated feature"]
        assert result.real_time_tamarin_measure == 285.5
        assert result.lemma_result == LemmaResult.VERIFIED
        assert result.steps == 1250
        assert result.analysis_type == "all-traces"

    def test_task_succeed_result_empty_warnings(self):
        """Test TaskSucceedResult with empty warnings."""
        result = TaskSucceedResult(
            warnings=[],
            real_time_tamarin_measure=100.0,
            lemma_result=LemmaResult.FALSIFIED,
            steps=500,
            analysis_type="exists-trace",
        )

        assert result.warnings == []
        assert result.lemma_result == LemmaResult.FALSIFIED

    def test_task_succeed_result_unterminated(self):
        """Test TaskSucceedResult with unterminated lemma."""
        result = TaskSucceedResult(
            warnings=["Analysis terminated early"],
            real_time_tamarin_measure=3600.0,
            lemma_result=LemmaResult.UNTERMINATED,
            steps=0,
            analysis_type="all-traces",
        )

        assert result.lemma_result == LemmaResult.UNTERMINATED
        assert result.steps == 0


class TestTaskFailedResult:
    """Test cases for TaskFailedResult model."""

    def test_task_failed_result_valid_creation(self):
        """Test creating valid TaskFailedResult instance."""
        result = TaskFailedResult(
            return_code="1",
            error_type=ErrorType.TAMARIN_ERROR,
            error_description="Syntax error in theory file",
            last_stderr_lines=[
                "Error: Parse error at line 25",
                "Expected 'end' keyword",
            ],
        )

        assert result.return_code == "1"
        assert result.error_type == ErrorType.TAMARIN_ERROR
        assert result.error_description == "Syntax error in theory file"
        assert result.last_stderr_lines == [
            "Error: Parse error at line 25",
            "Expected 'end' keyword",
        ]

    def test_task_failed_result_timeout(self):
        """Test TaskFailedResult with timeout error."""
        result = TaskFailedResult(
            return_code="124",
            error_type=ErrorType.TIMEOUT,
            error_description="Task timed out after 3600 seconds",
            last_stderr_lines=[],
        )

        assert result.error_type == ErrorType.TIMEOUT
        assert result.error_description == "Task timed out after 3600 seconds"
        assert result.last_stderr_lines == []

    def test_task_failed_result_memory_limit(self):
        """Test TaskFailedResult with memory limit error."""
        result = TaskFailedResult(
            return_code="137",
            error_type=ErrorType.MEMORY_LIMIT,
            error_description="Process killed due to memory limit",
            last_stderr_lines=["Out of memory"],
        )

        assert result.error_type == ErrorType.MEMORY_LIMIT
        assert result.last_stderr_lines == ["Out of memory"]


class TestExecMetadata:
    """Test cases for ExecMetadata model."""

    def test_exec_metadata_valid_creation(self):
        """Test creating valid ExecMetadata instance."""
        metadata = ExecMetadata(
            total_tasks=10,
            total_successes=8,
            total_failures=2,
            total_cache_hit=3,
            total_runtime=1800.0,
            total_memory=8192.0,
            max_runtime=450.0,
            max_memory=2048.0,
        )

        assert metadata.total_tasks == 10
        assert metadata.total_successes == 8
        assert metadata.total_failures == 2
        assert metadata.total_cache_hit == 3
        assert metadata.total_runtime == 1800.0
        assert metadata.total_memory == 8192.0
        assert metadata.max_runtime == 450.0
        assert metadata.max_memory == 2048.0

    def test_exec_metadata_zero_values(self):
        """Test ExecMetadata with zero values."""
        metadata = ExecMetadata(
            total_tasks=0,
            total_successes=0,
            total_failures=0,
            total_cache_hit=0,
            total_runtime=0.0,
            total_memory=0.0,
            max_runtime=0.0,
            max_memory=0.0,
        )

        assert metadata.total_tasks == 0
        assert metadata.total_successes == 0
        assert metadata.total_failures == 0


class TestRichExecutableTask:
    """Test cases for RichExecutableTask model."""

    def test_rich_executable_task_valid_creation(self, tmp_dir: Path):
        """Test creating valid RichExecutableTask instance."""
        theory_file = tmp_dir / "theory.spthy"
        trace_file = tmp_dir / "trace.json"
        resources = Resources(cores=4, memory=8, timeout=3600)

        task_config = TaskConfig(
            tamarin_alias="stable",
            lemma="test_lemma",
            output_theory_file=theory_file,
            output_trace_file=trace_file,
            options=["--heuristic=S"],
            preprocessor_flags=["FLAG1"],
            resources=resources,
        )

        task_metadata = TaskExecMetadata(
            command=["tamarin-prover", "theory.spthy"],
            status=TaskStatus.COMPLETED,
            cache_hit=False,
            exec_start="2024-01-01T12:00:00",
            exec_end="2024-01-01T12:05:00",
            exec_duration_monotonic=300.0,
            avg_memory=512.0,
            peak_memory=1024.0,
        )

        task_result = TaskSucceedResult(
            warnings=[],
            real_time_tamarin_measure=285.5,
            lemma_result=LemmaResult.VERIFIED,
            steps=1250,
            analysis_type="all-traces",
        )

        rich_task = RichExecutableTask(
            task_config=task_config,
            task_execution_metadata=task_metadata,
            task_result=task_result,
        )

        assert rich_task.task_config == task_config
        assert rich_task.task_execution_metadata == task_metadata
        assert rich_task.task_result == task_result

    def test_rich_executable_task_no_result(self, tmp_dir: Path):
        """Test RichExecutableTask with no result."""
        theory_file = tmp_dir / "theory.spthy"
        trace_file = tmp_dir / "trace.json"
        resources = Resources(cores=4, memory=8, timeout=3600)

        task_config = TaskConfig(
            tamarin_alias="stable",
            lemma="test_lemma",
            output_theory_file=theory_file,
            output_trace_file=trace_file,
            options=None,
            preprocessor_flags=None,
            resources=resources,
        )

        task_metadata = TaskExecMetadata(
            command=["tamarin-prover", "theory.spthy"],
            status=TaskStatus.PENDING,
            cache_hit=False,
            exec_start="",
            exec_end="",
            exec_duration_monotonic=0.0,
            avg_memory=0.0,
            peak_memory=0.0,
        )

        rich_task = RichExecutableTask(
            task_config=task_config,
            task_execution_metadata=task_metadata,
            task_result=None,
        )

        assert rich_task.task_result is None

    def test_rich_executable_task_failed_result(self, tmp_dir: Path):
        """Test RichExecutableTask with failed result."""
        theory_file = tmp_dir / "theory.spthy"
        trace_file = tmp_dir / "trace.json"
        resources = Resources(cores=4, memory=8, timeout=3600)

        task_config = TaskConfig(
            tamarin_alias="stable",
            lemma="test_lemma",
            output_theory_file=theory_file,
            output_trace_file=trace_file,
            options=None,
            preprocessor_flags=None,
            resources=resources,
        )

        task_metadata = TaskExecMetadata(
            command=["tamarin-prover", "theory.spthy"],
            status=TaskStatus.FAILED,
            cache_hit=False,
            exec_start="2024-01-01T12:00:00",
            exec_end="2024-01-01T12:00:30",
            exec_duration_monotonic=30.0,
            avg_memory=256.0,
            peak_memory=512.0,
        )

        task_result = TaskFailedResult(
            return_code="1",
            error_type=ErrorType.TAMARIN_ERROR,
            error_description="Syntax error in theory file",
            last_stderr_lines=["Error: Parse error at line 25"],
        )

        rich_task = RichExecutableTask(
            task_config=task_config,
            task_execution_metadata=task_metadata,
            task_result=task_result,
        )

        assert isinstance(rich_task.task_result, TaskFailedResult)
        assert rich_task.task_result.error_type == ErrorType.TAMARIN_ERROR


class TestRichTask:
    """Test cases for RichTask model."""

    def test_rich_task_valid_creation(self, tmp_dir: Path):
        """Test creating valid RichTask instance."""
        theory_file = tmp_dir / "theory.spthy"
        trace_file = tmp_dir / "trace.json"
        resources = Resources(cores=4, memory=8, timeout=3600)

        task_config = TaskConfig(
            tamarin_alias="stable",
            lemma="test_lemma",
            output_theory_file=theory_file,
            output_trace_file=trace_file,
            options=None,
            preprocessor_flags=None,
            resources=resources,
        )

        task_metadata = TaskExecMetadata(
            command=["tamarin-prover", "theory.spthy"],
            status=TaskStatus.COMPLETED,
            cache_hit=False,
            exec_start="2024-01-01T12:00:00",
            exec_end="2024-01-01T12:05:00",
            exec_duration_monotonic=300.0,
            avg_memory=512.0,
            peak_memory=1024.0,
        )

        rich_executable_task = RichExecutableTask(
            task_config=task_config,
            task_execution_metadata=task_metadata,
            task_result=None,
        )

        subtasks: dict[str, RichExecutableTask] = {
            "task1--lemma1--stable": rich_executable_task
        }

        rich_task = RichTask(
            theory_file="/path/to/theory.spthy",
            subtasks=subtasks,
        )

        assert rich_task.theory_file == "/path/to/theory.spthy"
        assert rich_task.subtasks == subtasks
        assert "task1--lemma1--stable" in rich_task.subtasks

    def test_rich_task_multiple_subtasks(self, tmp_dir: Path):
        """Test RichTask with multiple subtasks."""
        theory_file = tmp_dir / "theory.spthy"
        trace_file = tmp_dir / "trace.json"
        resources = Resources(cores=4, memory=8, timeout=3600)

        # Create multiple subtasks
        subtasks: dict[str, RichExecutableTask] = {}
        for i in range(3):
            task_config = TaskConfig(
                tamarin_alias="stable",
                lemma=f"lemma_{i}",
                output_theory_file=theory_file,
                output_trace_file=trace_file,
                options=None,
                preprocessor_flags=None,
                resources=resources,
            )

            task_metadata = TaskExecMetadata(
                command=["tamarin-prover", "theory.spthy"],
                status=TaskStatus.COMPLETED,
                cache_hit=False,
                exec_start="2024-01-01T12:00:00",
                exec_end="2024-01-01T12:05:00",
                exec_duration_monotonic=300.0,
                avg_memory=512.0,
                peak_memory=1024.0,
            )

            rich_executable_task = RichExecutableTask(
                task_config=task_config,
                task_execution_metadata=task_metadata,
                task_result=None,
            )

            subtasks[f"task--lemma_{i}--stable"] = rich_executable_task

        rich_task = RichTask(
            theory_file="/path/to/theory.spthy",
            subtasks=subtasks,
        )

        assert len(rich_task.subtasks) == 3
        assert all(key.startswith("task--lemma_") for key in rich_task.subtasks.keys())


class TestBatch:
    """Test cases for Batch model."""

    def test_batch_valid_creation(self, tmp_dir: Path):
        """Test creating valid Batch instance."""
        # Create global config
        global_config = GlobalConfig(
            global_max_cores=8,
            global_max_memory=16,
            default_timeout=3600,
            output_directory=str(tmp_dir),
        )

        # Create tamarin versions
        tamarin_versions = {
            "stable": TamarinVersion(
                path="/usr/bin/tamarin-prover",
                version="1.10.0",
                test_success=True,
            )
        }

        # Create execution metadata
        exec_metadata = ExecMetadata(
            total_tasks=5,
            total_successes=4,
            total_failures=1,
            total_cache_hit=2,
            total_runtime=1500.0,
            total_memory=4096.0,
            max_runtime=600.0,
            max_memory=2048.0,
        )

        # Create batch
        batch = Batch(
            recipe="test_recipe.json",
            config=global_config,
            tamarin_versions=tamarin_versions,
            execution_metadata=exec_metadata,
            tasks={},
        )

        assert batch.recipe == "test_recipe.json"
        assert batch.config == global_config
        assert batch.tamarin_versions == tamarin_versions
        assert batch.execution_metadata == exec_metadata
        assert batch.tasks == {}

    def test_batch_with_tasks(self, tmp_dir: Path):
        """Test Batch with tasks."""
        # Create global config
        global_config = GlobalConfig(
            global_max_cores=8,
            global_max_memory=16,
            default_timeout=3600,
            output_directory=str(tmp_dir),
        )

        # Create tamarin versions
        tamarin_versions = {
            "stable": TamarinVersion(
                path="/usr/bin/tamarin-prover",
                version="1.10.0",
                test_success=True,
            )
        }

        # Create execution metadata
        exec_metadata = ExecMetadata(
            total_tasks=1,
            total_successes=1,
            total_failures=0,
            total_cache_hit=0,
            total_runtime=300.0,
            total_memory=1024.0,
            max_runtime=300.0,
            max_memory=1024.0,
        )

        # Create a task
        theory_file = tmp_dir / "theory.spthy"
        trace_file = tmp_dir / "trace.json"
        resources = Resources(cores=4, memory=8, timeout=3600)

        task_config = TaskConfig(
            tamarin_alias="stable",
            lemma="test_lemma",
            output_theory_file=theory_file,
            output_trace_file=trace_file,
            options=None,
            preprocessor_flags=None,
            resources=resources,
        )

        task_metadata = TaskExecMetadata(
            command=["tamarin-prover", "theory.spthy"],
            status=TaskStatus.COMPLETED,
            cache_hit=False,
            exec_start="2024-01-01T12:00:00",
            exec_end="2024-01-01T12:05:00",
            exec_duration_monotonic=300.0,
            avg_memory=512.0,
            peak_memory=1024.0,
        )

        rich_executable_task = RichExecutableTask(
            task_config=task_config,
            task_execution_metadata=task_metadata,
            task_result=None,
        )

        rich_task = RichTask(
            theory_file="/path/to/theory.spthy",
            subtasks={"task1--lemma1--stable": rich_executable_task},
        )

        # Create batch with tasks
        batch = Batch(
            recipe="test_recipe.json",
            config=global_config,
            tamarin_versions=tamarin_versions,
            execution_metadata=exec_metadata,
            tasks={"task1": rich_task},
        )

        assert len(batch.tasks) == 1
        assert "task1" in batch.tasks
        assert batch.tasks["task1"] == rich_task

    def test_batch_json_serialization(self, tmp_dir: Path):
        """Test Batch JSON serialization."""
        # Create minimal batch
        global_config = GlobalConfig(
            global_max_cores=8,
            global_max_memory=16,
            default_timeout=3600,
            output_directory=str(tmp_dir),
        )

        tamarin_versions = {
            "stable": TamarinVersion(
                path="/usr/bin/tamarin-prover",
                version="1.10.0",
                test_success=True,
            )
        }

        exec_metadata = ExecMetadata(
            total_tasks=0,
            total_successes=0,
            total_failures=0,
            total_cache_hit=0,
            total_runtime=0.0,
            total_memory=0.0,
            max_runtime=0.0,
            max_memory=0.0,
        )

        batch = Batch(
            recipe="test_recipe.json",
            config=global_config,
            tamarin_versions=tamarin_versions,
            execution_metadata=exec_metadata,
            tasks={},
        )

        # Test JSON serialization
        json_data = batch.model_dump_json()
        assert json_data is not None

        # Test that it can be parsed back
        parsed = json.loads(json_data)
        assert parsed["recipe"] == "test_recipe.json"
        assert parsed["config"]["global_max_cores"] == 8
        assert parsed["execution_metadata"]["total_tasks"] == 0

    def test_batch_forbids_extra_fields(self, tmp_dir: Path):
        """Test that Batch model forbids extra fields."""
        global_config = GlobalConfig(
            global_max_cores=8,
            global_max_memory=16,
            default_timeout=3600,
            output_directory=str(tmp_dir),
        )

        tamarin_versions = {
            "stable": TamarinVersion(
                path="/usr/bin/tamarin-prover",
                version="1.10.0",
                test_success=True,
            )
        }

        exec_metadata = ExecMetadata(
            total_tasks=0,
            total_successes=0,
            total_failures=0,
            total_cache_hit=0,
            total_runtime=0.0,
            total_memory=0.0,
            max_runtime=0.0,
            max_memory=0.0,
        )

        # This should work
        batch = Batch(
            recipe="test_recipe.json",
            config=global_config,
            tamarin_versions=tamarin_versions,
            execution_metadata=exec_metadata,
            tasks={},
        )

        # Test that extra fields are forbidden by trying to create from dict
        batch_dict = batch.model_dump()
        batch_dict["extra_field"] = "extra_value"

        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            Batch.model_validate(batch_dict)


class TestEnums:
    """Test cases for enum classes."""

    def test_task_status_enum(self):
        """Test TaskStatus enum values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.TIMEOUT.value == "timeout"
        assert TaskStatus.MEMORY_LIMIT_EXCEEDED.value == "memory_limit_exceeded"

    def test_lemma_result_enum(self):
        """Test LemmaResult enum values."""
        assert LemmaResult.VERIFIED.value == "verified"
        assert LemmaResult.FALSIFIED.value == "falsified"
        assert LemmaResult.UNTERMINATED.value == "unterminated"

    def test_error_type_enum(self):
        """Test ErrorType enum values."""
        assert ErrorType.WRAPPER_KILLED.value == "wrapper_killed"
        assert ErrorType.KILLED.value == "killed"
        assert ErrorType.TERMINATED.value == "terminated"
        assert ErrorType.TIMEOUT.value == "timeout"
        assert ErrorType.MEMORY_LIMIT.value == "memory_limit"
        assert ErrorType.TAMARIN_ERROR.value == "tamarin_error"
        assert ErrorType.UNKNOWN.value == "unknown"

    def test_enum_string_representation(self):
        """Test enum string representations."""
        assert str(TaskStatus.COMPLETED) == "TaskStatus.COMPLETED"
        assert str(LemmaResult.VERIFIED) == "LemmaResult.VERIFIED"
        assert str(ErrorType.TIMEOUT) == "ErrorType.TIMEOUT"


class TestBatchComplexScenarios:
    """Test complex scenarios with full batch structures."""

    def test_complete_batch_workflow(self, tmp_dir: Path):
        """Test a complete batch workflow with multiple tasks and results."""
        # Create global config
        global_config = GlobalConfig(
            global_max_cores=8,
            global_max_memory=16,
            default_timeout=3600,
            output_directory=str(tmp_dir),
        )

        # Create tamarin versions
        tamarin_versions = {
            "stable": TamarinVersion(
                path="/usr/bin/tamarin-prover",
                version="1.10.0",
                test_success=True,
            ),
            "dev": TamarinVersion(
                path="/usr/bin/tamarin-prover-dev",
                version="1.11.0",
                test_success=True,
            ),
        }

        # Create execution metadata
        exec_metadata = ExecMetadata(
            total_tasks=4,
            total_successes=3,
            total_failures=1,
            total_cache_hit=1,
            total_runtime=2400.0,
            total_memory=6144.0,
            max_runtime=900.0,
            max_memory=2048.0,
        )

        # Create tasks with different scenarios
        tasks: dict[str, RichTask] = {}

        # Task 1: Successful verification
        theory_file = tmp_dir / "theory1.spthy"
        trace_file = tmp_dir / "trace1.json"
        resources = Resources(cores=4, memory=8, timeout=3600)

        task_config = TaskConfig(
            tamarin_alias="stable",
            lemma="lemma1",
            output_theory_file=theory_file,
            output_trace_file=trace_file,
            options=["--heuristic=S"],
            preprocessor_flags=["FLAG1"],
            resources=resources,
        )

        task_metadata = TaskExecMetadata(
            command=["tamarin-prover", "+RTS", "-N4", "-RTS", "theory1.spthy"],
            status=TaskStatus.COMPLETED,
            cache_hit=False,
            exec_start="2024-01-01T12:00:00",
            exec_end="2024-01-01T12:10:00",
            exec_duration_monotonic=600.0,
            avg_memory=1024.0,
            peak_memory=1536.0,
        )

        task_result = TaskSucceedResult(
            warnings=["Warning: deprecated syntax"],
            real_time_tamarin_measure=585.2,
            lemma_result=LemmaResult.VERIFIED,
            steps=2500,
            analysis_type="all-traces",
        )

        rich_executable_task1 = RichExecutableTask(
            task_config=task_config,
            task_execution_metadata=task_metadata,
            task_result=task_result,
        )

        # Task 2: Failed task
        task_config2 = TaskConfig(
            tamarin_alias="dev",
            lemma="lemma2",
            output_theory_file=theory_file,
            output_trace_file=trace_file,
            options=None,
            preprocessor_flags=None,
            resources=resources,
        )

        task_metadata2 = TaskExecMetadata(
            command=["tamarin-prover-dev", "+RTS", "-N4", "-RTS", "theory1.spthy"],
            status=TaskStatus.FAILED,
            cache_hit=False,
            exec_start="2024-01-01T12:10:00",
            exec_end="2024-01-01T12:10:30",
            exec_duration_monotonic=30.0,
            avg_memory=256.0,
            peak_memory=512.0,
        )

        task_result2 = TaskFailedResult(
            return_code="1",
            error_type=ErrorType.TAMARIN_ERROR,
            error_description="Parse error in theory file",
            last_stderr_lines=["Error: unexpected token at line 42"],
        )

        rich_executable_task2 = RichExecutableTask(
            task_config=task_config2,
            task_execution_metadata=task_metadata2,
            task_result=task_result2,
        )

        # Create RichTask with multiple subtasks
        rich_task = RichTask(
            theory_file=str(theory_file),
            subtasks={
                "task1--lemma1--stable": rich_executable_task1,
                "task1--lemma2--dev": rich_executable_task2,
            },
        )

        tasks["task1"] = rich_task

        # Create complete batch
        batch = Batch(
            recipe="complex_recipe.json",
            config=global_config,
            tamarin_versions=tamarin_versions,
            execution_metadata=exec_metadata,
            tasks=tasks,
        )

        # Verify complete structure
        assert batch.recipe == "complex_recipe.json"
        assert len(batch.tamarin_versions) == 2
        assert batch.execution_metadata.total_tasks == 4
        assert batch.execution_metadata.total_successes == 3
        assert batch.execution_metadata.total_failures == 1
        assert len(batch.tasks) == 1
        assert len(batch.tasks["task1"].subtasks) == 2

        # Verify successful task
        success_task = batch.tasks["task1"].subtasks["task1--lemma1--stable"]
        assert success_task.task_execution_metadata.status == TaskStatus.COMPLETED
        assert isinstance(success_task.task_result, TaskSucceedResult)
        assert success_task.task_result.lemma_result == LemmaResult.VERIFIED

        # Verify failed task
        failed_task = batch.tasks["task1"].subtasks["task1--lemma2--dev"]
        assert failed_task.task_execution_metadata.status == TaskStatus.FAILED
        assert isinstance(failed_task.task_result, TaskFailedResult)
        assert failed_task.task_result.error_type == ErrorType.TAMARIN_ERROR

        # Test JSON serialization of complete batch
        json_data = batch.model_dump_json(indent=2)
        assert json_data is not None
        assert "complex_recipe.json" in json_data
        assert "task1--lemma1--stable" in json_data
        assert "task1--lemma2--dev" in json_data

    def test_batch_with_cached_results(self, tmp_dir: Path):
        """Test batch with cached results."""
        # Create minimal batch with cached task
        global_config = GlobalConfig(
            global_max_cores=8,
            global_max_memory=16,
            default_timeout=3600,
            output_directory=str(tmp_dir),
        )

        tamarin_versions = {
            "stable": TamarinVersion(
                path="/usr/bin/tamarin-prover",
                version="1.10.0",
                test_success=True,
            )
        }

        exec_metadata = ExecMetadata(
            total_tasks=2,
            total_successes=2,
            total_failures=0,
            total_cache_hit=1,
            total_runtime=150.0,
            total_memory=1024.0,
            max_runtime=150.0,
            max_memory=1024.0,
        )

        # Create cached task
        theory_file = tmp_dir / "theory.spthy"
        trace_file = tmp_dir / "trace.json"
        resources = Resources(cores=4, memory=8, timeout=3600)

        task_config = TaskConfig(
            tamarin_alias="stable",
            lemma="cached_lemma",
            output_theory_file=theory_file,
            output_trace_file=trace_file,
            options=None,
            preprocessor_flags=None,
            resources=resources,
        )

        task_metadata = TaskExecMetadata(
            command=["tamarin-prover", "theory.spthy"],
            status=TaskStatus.COMPLETED,
            cache_hit=True,
            exec_start="2024-01-01T12:00:00",
            exec_end="2024-01-01T12:00:01",
            exec_duration_monotonic=0.1,
            avg_memory=0.0,
            peak_memory=0.0,
        )

        task_result = TaskSucceedResult(
            warnings=[],
            real_time_tamarin_measure=0.0,
            lemma_result=LemmaResult.VERIFIED,
            steps=0,
            analysis_type="cached",
        )

        rich_executable_task = RichExecutableTask(
            task_config=task_config,
            task_execution_metadata=task_metadata,
            task_result=task_result,
        )

        rich_task = RichTask(
            theory_file=str(theory_file),
            subtasks={"cached_task--cached_lemma--stable": rich_executable_task},
        )

        batch = Batch(
            recipe="cached_recipe.json",
            config=global_config,
            tamarin_versions=tamarin_versions,
            execution_metadata=exec_metadata,
            tasks={"cached_task": rich_task},
        )

        # Verify cached task properties
        cached_task = batch.tasks["cached_task"].subtasks[
            "cached_task--cached_lemma--stable"
        ]
        assert cached_task.task_execution_metadata.cache_hit is True
        assert cached_task.task_execution_metadata.exec_duration_monotonic == 0.1
        assert cached_task.task_execution_metadata.avg_memory == 0.0
        assert cached_task.task_execution_metadata.peak_memory == 0.0
        assert batch.execution_metadata.total_cache_hit == 1
