"""
Tests for OutputManager class.

This module tests the OutputManager functionality including output parsing,
JSON generation, directory management, and error handling. All file system
operations are mocked for CI compatibility.
"""

# pyright: basic

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from batch_tamarin.model.executable_task import MemoryStats, TaskResult, TaskStatus
from batch_tamarin.modules.output_manager import (
    FailedTaskResult,
    OutputManager,
    SuccessfulTaskResult,
    output_manager,
)


@pytest.fixture
def sample_successful_tamarin_output() -> str:
    """Sample successful tamarin output for testing."""
    return """
analyzed: examples/protocol.spthy

  lemma1 (all-traces): verified (2 steps)
  lemma2 (all-traces): verified (5 steps)
  lemma3 (all-traces): falsified (3 steps)

==============================================================================
summary of summaries:

analyzed: examples/protocol.spthy

  lemma1 (all-traces): verified (2 steps)
  lemma2 (all-traces): verified (5 steps)
  lemma3 (all-traces): falsified (3 steps)

==============================================================================

processing time: 15.123s
"""


@pytest.fixture
def sample_failed_tamarin_output() -> str:
    """Sample failed tamarin output for testing."""
    return """
tamarin-prover: error while parsing file 'examples/protocol.spthy' at line 15, column 3:
  unexpected "end"
  expecting "equations", "functions", "let", "restriction", "rule", or "lemma"

Error: Protocol parsing failed
"""


@pytest.fixture
def sample_task_result_success() -> TaskResult:
    """Sample successful task result for testing."""
    return TaskResult(
        task_id="test_task_success",
        status=TaskStatus.COMPLETED,
        return_code=0,
        stdout="analyzed: examples/protocol.spthy\n\n  lemma1 (all-traces): verified (2 steps)",
        stderr="",
        start_time=1000.0,
        end_time=1015.123,
        duration=15.123,
        memory_stats=MemoryStats(peak_memory_mb=512.0, avg_memory_mb=256.0),
    )


@pytest.fixture
def sample_task_result_failed() -> TaskResult:
    """Sample failed task result for testing."""
    return TaskResult(
        task_id="test_task_failed",
        status=TaskStatus.FAILED,
        return_code=1,
        stdout="",
        stderr="tamarin-prover: error while parsing file 'examples/protocol.spthy'",
        start_time=1000.0,
        end_time=1005.0,
        duration=5.0,
        memory_stats=None,
    )


class TestOutputManagerInitialization:
    """Test OutputManager initialization and singleton behavior."""

    def test_output_manager_singleton(self):
        """Test OutputManager singleton pattern."""
        manager1 = OutputManager()
        manager2 = OutputManager()

        assert manager1 is manager2
        assert manager1 is output_manager

    def test_output_manager_initialization_state(self):
        """Test OutputManager initial state."""
        manager = OutputManager()

        assert not manager.is_initialized()
        assert manager.output_dir == Path(".")
        assert manager.success_dir == Path(".")
        assert manager.failed_dir == Path(".")
        assert manager.models_dir == Path(".")
        assert manager.traces_dir == Path(".")

    @patch("batch_tamarin.modules.output_manager.notification_manager")
    def test_initialize_with_bypass(self, mock_notification: Mock, tmp_dir: Path):
        """Test OutputManager initialization with bypass flag."""
        manager = OutputManager()

        # Reset initialization state for testing
        manager._is_setup = False  # type: ignore

        output_dir = tmp_dir / "test_output"
        manager.initialize(output_dir, bypass=True)

        assert manager.is_initialized()
        assert manager.output_dir == output_dir
        assert manager.success_dir == output_dir / "success"
        assert manager.failed_dir == output_dir / "failed"
        assert manager.models_dir == output_dir / "proofs"
        assert manager.traces_dir == output_dir / "traces"

        # Should not have called debug notification when bypass=True
        mock_notification.debug.assert_not_called()

    def test_initialize_already_setup(self, tmp_dir: Path):
        """Test OutputManager initialization when already setup."""
        manager = OutputManager()

        # Set as already initialized
        manager._is_setup = True  # type: ignore
        original_output_dir = manager.output_dir

        # Should not change state
        manager.initialize(tmp_dir / "new_output")

        assert manager.output_dir == original_output_dir


class TestOutputManagerDirectoryManagement:
    """Test OutputManager directory creation and management."""

    @patch("batch_tamarin.modules.output_manager.notification_manager")
    def test_create_directories(self, mock_notification: Mock, tmp_dir: Path):
        """Test directory creation."""
        manager = OutputManager()
        manager._is_setup = False  # type: ignore

        output_dir = tmp_dir / "test_output"

        with patch.object(manager, "_handle_existing_directory") as mock_handle:
            with patch.object(manager, "_create_directories") as mock_create:
                manager.initialize(output_dir)

                mock_handle.assert_called_once()
                mock_create.assert_called_once()

    @patch("batch_tamarin.modules.output_manager.notification_manager")
    def test_handle_existing_directory_empty(
        self, mock_notification: Mock, tmp_dir: Path
    ):
        """Test handling of non-existent directory."""
        manager = OutputManager()
        manager._is_setup = False  # type: ignore

        output_dir = tmp_dir / "nonexistent"
        manager.output_dir = output_dir
        manager._is_setup = True  # type: ignore

        # Should not raise exception for non-existent directory
        manager._handle_existing_directory()  # type: ignore

    @patch("batch_tamarin.modules.output_manager.notification_manager")
    def test_handle_existing_directory_file(
        self, mock_notification: Mock, tmp_dir: Path
    ):
        """Test handling when output path is a file."""
        manager = OutputManager()
        manager._is_setup = False  # type: ignore

        # Create a file instead of directory
        output_file = tmp_dir / "output_file.txt"
        output_file.write_text("test content")

        manager.output_dir = output_file
        manager._is_setup = True  # type: ignore

        with pytest.raises(RuntimeError, match="Output path is not a directory"):
            manager._handle_existing_directory()  # type: ignore

    @patch("batch_tamarin.modules.output_manager.notification_manager")
    def test_handle_existing_directory_not_empty_wipe(
        self, mock_notification: Mock, tmp_dir: Path
    ):
        """Test handling of non-empty directory with wipe confirmation."""
        manager = OutputManager()
        manager._is_setup = False  # type: ignore

        # Create non-empty directory
        output_dir = tmp_dir / "test_output"
        output_dir.mkdir()
        (output_dir / "existing_file.txt").write_text("content")

        manager.output_dir = output_dir
        manager._is_setup = True  # type: ignore

        # Mock user confirmation to wipe
        mock_notification.prompt_user.return_value = True

        with patch("batch_tamarin.modules.output_manager.shutil.rmtree"):
            manager._handle_existing_directory()  # type: ignore

            mock_notification.prompt_user.assert_called_once()
            mock_notification.info.assert_called_once()

    @patch("batch_tamarin.modules.output_manager.notification_manager")
    @patch("batch_tamarin.modules.output_manager.datetime")
    def test_handle_existing_directory_not_empty_no_wipe(
        self, mock_datetime: Mock, mock_notification: Mock, tmp_dir: Path
    ):
        """Test handling of non-empty directory without wipe confirmation."""
        manager = OutputManager()
        manager._is_setup = False  # type: ignore

        # Create non-empty directory
        output_dir = tmp_dir / "test_output"
        output_dir.mkdir()
        (output_dir / "existing_file.txt").write_text("content")

        manager.output_dir = output_dir
        manager.success_dir = output_dir / "success"
        manager.failed_dir = output_dir / "failed"
        manager.models_dir = output_dir / "proofs"
        manager.traces_dir = output_dir / "traces"
        manager._is_setup = True  # type: ignore

        # Mock user confirmation to not wipe
        mock_notification.prompt_user.return_value = False

        # Mock datetime for timestamp
        mock_datetime.now.return_value.strftime.return_value = "01-01-23_12-00-00"

        manager._handle_existing_directory()  # type: ignore

        mock_notification.prompt_user.assert_called_once()
        mock_notification.info.assert_called_once()

        # Check that directory path was updated with timestamp
        assert manager.output_dir.name == "test_output_01-01-23_12-00-00"

    @patch("batch_tamarin.modules.output_manager.notification_manager")
    def test_handle_existing_directory_wipe_error(
        self, mock_notification: Mock, tmp_dir: Path
    ):
        """Test error handling during directory wipe."""
        manager = OutputManager()
        manager._is_setup = False  # type: ignore

        # Create non-empty directory
        output_dir = tmp_dir / "test_output"
        output_dir.mkdir()
        (output_dir / "existing_file.txt").write_text("content")

        manager.output_dir = output_dir
        manager._is_setup = True  # type: ignore

        # Mock user confirmation to wipe
        mock_notification.prompt_user.return_value = True

        # Mock an actual error during removal
        def mock_unlink_side_effect():
            raise Exception("Permission denied")

        with patch.object(Path, "unlink", side_effect=mock_unlink_side_effect):
            with pytest.raises(RuntimeError, match="Failed to wipe output directory"):
                manager._handle_existing_directory()  # type: ignore

    def test_handle_existing_directory_not_initialized(self):
        """Test error when trying to handle directory before initialization."""
        manager = OutputManager()
        manager._is_setup = False  # type: ignore

        with pytest.raises(RuntimeError, match="OutputManager not initialized"):
            manager._handle_existing_directory()  # type: ignore

    def test_get_output_paths(self, tmp_dir: Path):
        """Test getting output paths."""
        manager = OutputManager()
        manager._is_setup = False  # type: ignore

        output_dir = tmp_dir / "test_output"
        manager.output_dir = output_dir
        manager.success_dir = output_dir / "success"
        manager.failed_dir = output_dir / "failed"
        manager.models_dir = output_dir / "proofs"
        manager.traces_dir = output_dir / "traces"
        manager._is_setup = True  # type: ignore

        paths = manager.get_output_paths()

        assert paths["success"] == manager.success_dir
        assert paths["failed"] == manager.failed_dir
        assert paths["models"] == manager.models_dir
        assert paths["traces"] == manager.traces_dir


class TestOutputManagerProcessing:
    """Test OutputManager task result processing."""

    @patch("batch_tamarin.modules.output_manager.notification_manager")
    def test_process_task_result_success(
        self,
        mock_notification: Mock,
        tmp_dir: Path,
        sample_task_result_success: TaskResult,
    ):
        """Test processing successful task result."""
        manager = OutputManager()
        manager._is_setup = False  # type: ignore

        # Setup manager
        output_dir = tmp_dir / "test_output"
        manager.output_dir = output_dir
        manager.success_dir = output_dir / "success"
        manager.failed_dir = output_dir / "failed"
        manager.models_dir = output_dir / "proofs"
        manager.traces_dir = output_dir / "traces"
        manager._is_setup = True  # type: ignore

        with patch.object(manager, "_process_successful_task") as mock_process:
            manager.process_task_result(sample_task_result_success, "test_output.spthy")

            mock_process.assert_called_once_with(
                sample_task_result_success, "test_output.json", "test_output.spthy"
            )

    @patch("batch_tamarin.modules.output_manager.notification_manager")
    def test_process_task_result_failed(
        self,
        mock_notification: Mock,
        tmp_dir: Path,
        sample_task_result_failed: TaskResult,
    ):
        """Test processing failed task result."""
        manager = OutputManager()
        manager._is_setup = False  # type: ignore

        # Setup manager
        output_dir = tmp_dir / "test_output"
        manager.output_dir = output_dir
        manager.success_dir = output_dir / "success"
        manager.failed_dir = output_dir / "failed"
        manager.models_dir = output_dir / "proofs"
        manager.traces_dir = output_dir / "traces"
        manager._is_setup = True  # type: ignore

        with patch.object(manager, "_process_failed_task") as mock_process:
            manager.process_task_result(sample_task_result_failed, "test_output.spthy")

            mock_process.assert_called_once_with(
                sample_task_result_failed, "test_output.json"
            )

    @patch("batch_tamarin.modules.output_manager.notification_manager")
    def test_process_task_result_not_initialized(
        self, mock_notification: Mock, sample_task_result_success: TaskResult
    ):
        """Test processing task result when not initialized."""
        manager = OutputManager()
        manager._is_setup = False  # type: ignore

        with pytest.raises(RuntimeError, match="OutputManager not initialized"):
            manager.process_task_result(sample_task_result_success, "test_output.spthy")

    @patch("batch_tamarin.modules.output_manager.notification_manager")
    def test_process_successful_task(
        self,
        mock_notification: Mock,
        tmp_dir: Path,
        sample_task_result_success: TaskResult,
    ):
        """Test processing successful task with file creation."""
        manager = OutputManager()
        manager._is_setup = False  # type: ignore

        # Setup manager
        output_dir = tmp_dir / "test_output"
        manager.output_dir = output_dir
        manager.success_dir = output_dir / "success"
        manager.failed_dir = output_dir / "failed"
        manager.models_dir = output_dir / "proofs"
        manager.traces_dir = output_dir / "traces"
        manager._is_setup = True  # type: ignore

        # Create directories
        manager.success_dir.mkdir(parents=True)

        # Mock the successful result
        mock_result = Mock()
        mock_result.model_dump_json.return_value = '{"task_id": "test_task"}'

        with patch.object(manager, "_parse_successful_output") as mock_parse:
            mock_parse.return_value = mock_result

            with patch("builtins.open", create=True) as mock_open:
                mock_file = Mock()
                mock_open.return_value.__enter__.return_value = mock_file

                manager._process_successful_task(  # type: ignore
                    sample_task_result_success, "test_output.json", "test_output.spthy"
                )

                mock_parse.assert_called_once_with(
                    "test_task_success",
                    sample_task_result_success.stdout,
                    sample_task_result_success.stderr,
                    sample_task_result_success.duration,
                    sample_task_result_success.memory_stats,
                    "test_output.spthy",
                )
                mock_open.assert_called_once()
                mock_file.write.assert_called_once_with('{"task_id": "test_task"}')

    @patch("batch_tamarin.modules.output_manager.notification_manager")
    def test_process_failed_task(
        self,
        mock_notification: Mock,
        tmp_dir: Path,
        sample_task_result_failed: TaskResult,
    ):
        """Test processing failed task with file creation."""
        manager = OutputManager()
        manager._is_setup = False  # type: ignore

        # Setup manager
        output_dir = tmp_dir / "test_output"
        manager.output_dir = output_dir
        manager.success_dir = output_dir / "success"
        manager.failed_dir = output_dir / "failed"
        manager.models_dir = output_dir / "proofs"
        manager.traces_dir = output_dir / "traces"
        manager._is_setup = True  # type: ignore

        # Create directories
        manager.failed_dir.mkdir(parents=True)

        # Mock the failed result
        mock_result = Mock()
        mock_result.model_dump_json.return_value = '{"task_id": "test_task"}'

        with patch.object(manager, "_parse_failed_output") as mock_parse:
            mock_parse.return_value = mock_result

            with patch("builtins.open", create=True) as mock_open:
                mock_file = Mock()
                mock_open.return_value.__enter__.return_value = mock_file

                manager._process_failed_task(  # type: ignore
                    sample_task_result_failed, "test_output.json"
                )

                mock_parse.assert_called_once_with(
                    "test_task_failed",
                    sample_task_result_failed.stdout,
                    sample_task_result_failed.stderr,
                    sample_task_result_failed.duration,
                    sample_task_result_failed.memory_stats,
                    sample_task_result_failed.return_code,
                    sample_task_result_failed.status,
                )
                mock_open.assert_called_once()
                mock_file.write.assert_called_once_with('{"task_id": "test_task"}')


class TestOutputManagerParsing:
    """Test OutputManager parsing functionality."""

    def test_parse_successful_output(self, sample_successful_tamarin_output: str):
        """Test parsing successful tamarin output."""
        manager = OutputManager()
        manager._is_setup = True  # type: ignore
        manager.models_dir = Path("/mock/models")

        memory_stats = MemoryStats(peak_memory_mb=512.0, avg_memory_mb=256.0)

        result = manager._parse_successful_output(  # type: ignore
            "test_task",
            sample_successful_tamarin_output,
            "",
            15.123,
            memory_stats,
            "test_output.spthy",
        )

        assert isinstance(result, SuccessfulTaskResult)
        assert result.task_id == "test_task"
        assert result.tamarin_timing == 15.123
        assert result.wrapper_measures.time == 15.123
        assert result.wrapper_measures.peak_memory == 512.0
        assert result.wrapper_measures.avg_memory == 256.0
        assert "lemma1" in result.verified_lemma
        assert "lemma3" in result.falsified_lemma

    def test_parse_failed_output(self, sample_failed_tamarin_output: str):
        """Test parsing failed tamarin output."""
        manager = OutputManager()

        memory_stats = MemoryStats(peak_memory_mb=256.0, avg_memory_mb=128.0)

        result = manager._parse_failed_output(  # type: ignore
            "test_task",
            "",
            sample_failed_tamarin_output,
            5.0,
            memory_stats,
            1,
            TaskStatus.FAILED,
        )

        assert isinstance(result, FailedTaskResult)
        assert result.task_id == "test_task"
        assert result.return_code == 1
        assert result.wrapper_measures.time == 5.0
        assert result.wrapper_measures.peak_memory == 256.0
        assert result.wrapper_measures.avg_memory == 128.0
        assert (
            "error" in result.error_description
            or "unexpected" in result.error_description
        )

    def test_extract_tamarin_timing(self):
        """Test extracting timing information from tamarin output."""
        manager = OutputManager()

        output_with_timing = """
some output

processing time: 15.123s
"""

        timing = manager._extract_tamarin_timing(  # type: ignore
            output_with_timing
        )  # type: ignore

        assert timing == 15.123

    def test_extract_tamarin_timing_no_timing(self):
        """Test extracting timing when no timing info present."""
        manager = OutputManager()

        output_without_timing = "some output without timing"

        timing = manager._extract_tamarin_timing(  # type: ignore
            output_without_timing
        )  # type: ignore

        assert timing == 0.0

    def test_parse_lemma_results(self):
        """Test parsing lemma results from tamarin output."""
        manager = OutputManager()

        output_with_lemmas = """
analyzed: examples/protocol.spthy

  lemma1 (all-traces): verified (2 steps)
  lemma2 (all-traces): verified (5 steps)
  lemma3 (all-traces): falsified (3 steps)
  lemma4 (all-traces): analysis incomplete (1 steps)
"""

        verified, falsified, unterminated = manager._parse_lemma_results(  # type: ignore
            output_with_lemmas
        )

        assert len(verified) == 2
        assert "lemma1" in verified
        assert verified["lemma1"].steps == 2
        assert verified["lemma1"].analysis_type == "all-traces"
        assert "lemma2" in verified
        assert verified["lemma2"].steps == 5

        assert len(falsified) == 1
        assert "lemma3" in falsified
        assert falsified["lemma3"].steps == 3

        assert len(unterminated) == 1
        assert "lemma4" in unterminated

    def test_parse_lemma_results_no_lemmas(self):
        """Test parsing lemma results when no lemmas present."""
        manager = OutputManager()

        output_without_lemmas = "some output without lemmas"

        verified, falsified, unterminated = manager._parse_lemma_results(  # type: ignore
            output_without_lemmas
        )

        assert verified == {}
        assert falsified == {}
        assert unterminated == []

    def test_extract_warnings(self):
        """Test extracting warnings from tamarin output."""
        manager = OutputManager()

        output_with_warnings = """
WARNING: Some warning message
Another line
WARNING: Another warning
Normal output
"""

        warnings = manager._extract_warnings(output_with_warnings)  # type: ignore

        assert len(warnings) == 2
        assert "Some warning message" in warnings
        assert "Another warning" in warnings

    def test_extract_warnings_no_warnings(self):
        """Test extracting warnings when no warnings present."""
        manager = OutputManager()

        output_without_warnings = "normal output without warnings"

        warnings = manager._extract_warnings(output_without_warnings)  # type: ignore

        assert warnings == []

    def test_handle_error_description(self):
        """Test handling error description from stderr."""
        manager = OutputManager()

        stderr_with_error = """
tamarin-prover: error while parsing file 'examples/protocol.spthy' at line 15, column 3:
  unexpected "end"
  expecting "equations", "functions", "let", "restriction", "rule", or "lemma"

Error: Protocol parsing failed
"""

        error_desc = manager._handle_error_description(  # type: ignore
            stderr_with_error, "", 1, TaskStatus.FAILED
        )

        assert "unexpected error" in error_desc

    def test_handle_error_description_timeout(self):
        """Test handling timeout error description."""
        manager = OutputManager()

        error_desc = manager._handle_error_description(  # type: ignore
            "", "", -1, TaskStatus.TIMEOUT
        )

        assert "timed out" in error_desc

    def test_handle_error_description_memory_limit(self):
        """Test handling memory limit error description."""
        manager = OutputManager()

        error_desc = manager._handle_error_description(  # type: ignore
            "", "", -1, TaskStatus.MEMORY_LIMIT_EXCEEDED
        )

        assert "memory limit" in error_desc

    def test_parse_task_result_success(self, sample_task_result_success: TaskResult):
        """Test parsing successful task result."""
        manager = OutputManager()
        manager._is_setup = True  # type: ignore
        manager.models_dir = Path("/mock/models")

        result = manager.parse_task_result(
            sample_task_result_success, "test_output.spthy"
        )

        assert isinstance(result, SuccessfulTaskResult)
        assert result.task_id == "test_task_success"

    def test_parse_task_result_failed(self, sample_task_result_failed: TaskResult):
        """Test parsing failed task result."""
        manager = OutputManager()
        manager._is_setup = True  # type: ignore

        result = manager.parse_task_result(
            sample_task_result_failed, "test_output.spthy"
        )

        assert isinstance(result, FailedTaskResult)
        assert result.task_id == "test_task_failed"


class TestOutputManagerErrorHandling:
    """Test OutputManager error handling scenarios."""

    @patch("batch_tamarin.modules.output_manager.notification_manager")
    def test_process_task_result_file_error(
        self,
        mock_notification: Mock,
        tmp_dir: Path,
        sample_task_result_success: TaskResult,
    ):
        """Test error handling during file writing."""
        manager = OutputManager()
        manager._is_setup = False  # type: ignore

        # Setup manager
        output_dir = tmp_dir / "test_output"
        manager.output_dir = output_dir
        manager.success_dir = output_dir / "success"
        manager.failed_dir = output_dir / "failed"
        manager.models_dir = output_dir / "proofs"
        manager.traces_dir = output_dir / "traces"
        manager._is_setup = True  # type: ignore

        # Mock successful result
        mock_result = Mock()
        mock_result.model_dump_json.return_value = '{"task_id": "test_task"}'

        with patch.object(manager, "_parse_successful_output") as mock_parse:
            mock_parse.return_value = mock_result

            with patch("builtins.open", side_effect=IOError("Permission denied")):
                # Should not raise exception, but log error
                manager._process_successful_task(  # type: ignore
                    sample_task_result_success, "test_output.json", "test_output.spthy"
                )

                mock_notification.error.assert_called_once()

    @patch("batch_tamarin.modules.output_manager.notification_manager")
    def test_process_task_result_parse_error(
        self,
        mock_notification: Mock,
        tmp_dir: Path,
        sample_task_result_success: TaskResult,
    ):
        """Test error handling during output parsing."""
        manager = OutputManager()
        manager._is_setup = False  # type: ignore

        # Setup manager
        output_dir = tmp_dir / "test_output"
        manager.output_dir = output_dir
        manager.success_dir = output_dir / "success"
        manager.failed_dir = output_dir / "failed"
        manager.models_dir = output_dir / "proofs"
        manager.traces_dir = output_dir / "traces"
        manager._is_setup = True  # type: ignore

        with patch.object(
            manager, "_parse_successful_output", side_effect=Exception("Parse error")
        ):
            # Should not raise exception, but log error
            manager._process_successful_task(  # type: ignore
                sample_task_result_success, "test_output.json", "test_output.spthy"
            )

            mock_notification.error.assert_called_once()

    def test_extract_tamarin_timing_malformed(self):
        """Test timing extraction with malformed timing data."""
        manager = OutputManager()

        output_malformed = """
processing time: invalidXs
some other output
"""

        timing = manager._extract_tamarin_timing(output_malformed)  # type: ignore

        # Should handle malformed data gracefully
        assert timing == 0.0

    def test_parse_lemma_results_malformed(self):
        """Test lemma parsing with malformed lemma data."""
        manager = OutputManager()

        output_malformed = """
analyzed: examples/protocol.spthy

  lemma1 (all-traces): verified (invalid steps)
  malformed lemma line
  lemma2 (all-traces): verified (5 steps)
"""

        verified, _falsified, _unterminated = manager._parse_lemma_results(  # type: ignore
            output_malformed
        )

        # Should handle malformed data gracefully, parsing what it can
        assert "lemma2" in verified
        assert verified["lemma2"].steps == 5

    def test_get_output_paths_not_initialized(self):
        """Test get_output_paths when not initialized."""
        manager = OutputManager()
        manager._is_setup = False  # type: ignore

        with pytest.raises(RuntimeError, match="OutputManager not initialized"):
            manager.get_output_paths()
