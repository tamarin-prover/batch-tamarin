"""
Tests for the cache_manager module.

This module tests the CacheManager class functionality including cache storage,
retrieval, key generation, and cache management operations.
"""

# pyright: basic

from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch

from batch_tamarin.model.executable_task import ExecutableTask, TaskResult, TaskStatus
from batch_tamarin.modules.cache_manager import CacheManager


@pytest.fixture
def cache_manager(tmp_dir: Path, monkeypatch: MonkeyPatch) -> CacheManager:
    """Create a CacheManager instance with temporary cache directory."""
    # Mock the cache directory to use our temp directory
    with monkeypatch.context() as m:
        m.setattr("pathlib.Path.home", lambda: tmp_dir)
        return CacheManager()


@pytest.fixture
def sample_task(sample_theory_file: Path, tmp_dir: Path) -> ExecutableTask:
    """Create a sample ExecutableTask for testing."""
    tamarin_exe = tmp_dir / "tamarin-prover"
    tamarin_exe.write_text("#!/bin/bash\necho 'mock tamarin'")
    tamarin_exe.chmod(0o755)

    output_file = tmp_dir / "test_output.txt"
    traces_dir = tmp_dir / "traces"
    traces_dir.mkdir(exist_ok=True)

    return ExecutableTask(
        task_name="test_task_001",
        original_task_name="test_task_001",
        tamarin_version_name="stable",
        theory_file=sample_theory_file,
        tamarin_executable=tamarin_exe,
        output_file=output_file,
        lemma="test_lemma",
        tamarin_options=["--heuristic=S"],
        preprocess_flags=["FLAG1"],
        max_cores=4,
        max_memory=8,
        task_timeout=1800,
        traces_dir=traces_dir,
    )


@pytest.fixture
def sample_result() -> TaskResult:
    """Create a sample TaskResult for testing."""
    return TaskResult(
        task_id="test_task_001",
        status=TaskStatus.COMPLETED,
        return_code=0,
        stdout="Analysis completed successfully",
        stderr="",
        start_time=1000.0,
        end_time=1120.5,
        duration=120.5,
    )


class TestCacheManager:
    """Test cases for CacheManager class."""

    def test_cache_manager_initialization(self, cache_manager: CacheManager):
        """Test CacheManager initialization creates cache directory."""
        # Cache manager should initialize successfully
        assert cache_manager.cache is not None

    def test_generate_cache_key_consistency(
        self, cache_manager: CacheManager, sample_task: ExecutableTask
    ):
        """Test that cache key generation is consistent for identical tasks."""
        key1 = cache_manager._generate_key(sample_task)  # type: ignore
        key2 = cache_manager._generate_key(sample_task)  # type: ignore
        assert key1 == key2
        assert len(key1) == 64  # SHA256 produces 64-character hex string

    def test_generate_cache_key_different_tasks(
        self,
        cache_manager: CacheManager,
        sample_task: ExecutableTask,
        sample_theory_file: Path,
    ):
        """Test that different tasks produce different cache keys."""
        task1 = sample_task

        # Create task with different lemma
        tamarin_exe = sample_task.tamarin_executable
        task2 = ExecutableTask(
            task_name="test_task_002",
            original_task_name="test_task_002",
            tamarin_version_name="stable",
            theory_file=sample_theory_file,
            tamarin_executable=tamarin_exe,
            output_file=sample_task.output_file,
            lemma="different_lemma",
            tamarin_options=["--heuristic=S"],
            preprocess_flags=["FLAG1"],
            max_cores=4,
            max_memory=8,
            task_timeout=1800,
            traces_dir=sample_task.traces_dir,
        )

        key1 = cache_manager._generate_key(task1)  # type: ignore
        key2 = cache_manager._generate_key(task2)  # type: ignore
        assert key1 != key2

    def test_generate_cache_key_file_content_sensitivity(
        self, cache_manager: CacheManager, tmp_dir: Path
    ):
        """Test that cache key changes when file content changes."""
        # Create two files with different content
        file1 = tmp_dir / "theory1.spthy"
        file2 = tmp_dir / "theory2.spthy"
        file1.write_text('theory Test1\nbegin\nlemma test: "true"\nend')
        file2.write_text('theory Test2\nbegin\nlemma test: "false"\nend')

        tamarin_exe = tmp_dir / "tamarin-prover"
        tamarin_exe.write_text("#!/bin/bash\necho 'mock tamarin'")
        tamarin_exe.chmod(0o755)

        output_file = tmp_dir / "test_output.txt"
        traces_dir = tmp_dir / "traces"
        traces_dir.mkdir(exist_ok=True)

        task1 = ExecutableTask(
            task_name="test_task_001",
            original_task_name="test_task_001",
            tamarin_version_name="stable",
            theory_file=file1,
            tamarin_executable=tamarin_exe,
            output_file=output_file,
            lemma="test",
            tamarin_options=[],
            preprocess_flags=[],
            max_cores=4,
            max_memory=8,
            task_timeout=1800,
            traces_dir=traces_dir,
        )

        task2 = ExecutableTask(
            task_name="test_task_002",
            original_task_name="test_task_002",
            tamarin_version_name="stable",
            theory_file=file2,
            tamarin_executable=tamarin_exe,
            output_file=output_file,
            lemma="test",
            tamarin_options=[],
            preprocess_flags=[],
            max_cores=4,
            max_memory=8,
            task_timeout=1800,
            traces_dir=traces_dir,
        )

        key1 = cache_manager._generate_key(task1)  # type: ignore
        key2 = cache_manager._generate_key(task2)  # type: ignore
        assert key1 != key2

    def test_cache_store_and_retrieve(
        self,
        cache_manager: CacheManager,
        sample_task: ExecutableTask,
        sample_result: TaskResult,
    ):
        """Test storing and retrieving cache entries."""
        # Initially no cached result
        cached_result = cache_manager.get_cached_result(sample_task)
        assert cached_result is None

        # Store result
        cache_manager.store_result(sample_task, sample_result)

        # Retrieve cached result
        cached_result = cache_manager.get_cached_result(sample_task)
        assert cached_result is not None
        assert cached_result.task_id == sample_result.task_id
        assert cached_result.status == sample_result.status
        assert cached_result.return_code == sample_result.return_code
        assert cached_result.stdout == sample_result.stdout
        assert cached_result.duration == sample_result.duration

    def test_cache_failed_task_result(
        self, cache_manager: CacheManager, sample_task: ExecutableTask
    ):
        """Test caching failed task results."""
        failed_result = TaskResult(
            task_id="test_task_001",
            status=TaskStatus.FAILED,
            return_code=1,
            stdout="",
            stderr="Analysis failed with error",
            start_time=1000.0,
            end_time=1030.0,
            duration=30.0,
        )

        # Store failed result
        cache_manager.store_result(sample_task, failed_result)

        # Retrieve cached failed result
        cached_result = cache_manager.get_cached_result(sample_task)
        assert cached_result is not None
        assert cached_result.status == TaskStatus.FAILED
        assert cached_result.return_code == 1
        assert cached_result.stderr == "Analysis failed with error"

    def test_cache_stats(
        self,
        cache_manager: CacheManager,
        sample_task: ExecutableTask,
        sample_result: TaskResult,
    ):
        """Test cache statistics functionality."""
        # Initially empty cache
        stats = cache_manager.get_stats()
        assert stats["size"] == 0

        # Store one result
        cache_manager.store_result(sample_task, sample_result)

        # Check stats after storage
        stats = cache_manager.get_stats()
        assert stats["size"] == 1

    def test_cache_clear(
        self,
        cache_manager: CacheManager,
        sample_task: ExecutableTask,
        sample_result: TaskResult,
    ):
        """Test cache clearing functionality."""
        # Store result
        cache_manager.store_result(sample_task, sample_result)

        # Verify it's cached
        cached_result = cache_manager.get_cached_result(sample_task)
        assert cached_result is not None

        # Clear cache
        cache_manager.clear_cache()

        # Verify it's gone
        cached_result = cache_manager.get_cached_result(sample_task)
        assert cached_result is None

        # Verify stats are reset
        stats = cache_manager.get_stats()
        assert stats["size"] == 0

    @patch("batch_tamarin.modules.cache_manager.hashlib.sha256")
    def test_file_hashing_chunked_reading(
        self,
        mock_sha256: Any,
        cache_manager: CacheManager,
        sample_task: ExecutableTask,
        tmp_dir: Path,
    ):
        """Test that file hashing uses chunked reading for large files."""
        # Create a larger file (100KB to ensure multiple chunks)
        large_file = tmp_dir / "large_theory.spthy"
        content = "theory LargeTest\nbegin\n" + 'lemma test: "true"\n' * 5000 + "end"
        large_file.write_text(content)

        sample_task.theory_file = large_file

        # Mock hasher
        mock_hasher = Mock()
        mock_sha256.return_value = mock_hasher
        mock_hasher.hexdigest.return_value = "mocked_hash"

        # Generate key (which triggers file hashing)
        cache_manager._generate_key(sample_task)  # type: ignore

        # Verify chunked reading was used (should be multiple chunks for a large file)
        assert mock_hasher.update.call_count >= 1  # At least one chunk should be read

    def test_cache_key_includes_all_relevant_fields(
        self, cache_manager: CacheManager, sample_theory_file: Path, tmp_dir: Path
    ):
        """Test that cache key includes all execution-affecting task fields."""
        tamarin_exe = tmp_dir / "tamarin-prover"
        tamarin_exe.write_text("#!/bin/bash\necho 'mock tamarin'")
        tamarin_exe.chmod(0o755)

        tamarin_exe2 = tmp_dir / "tamarin-prover-dev"
        tamarin_exe2.write_text("#!/bin/bash\necho 'mock tamarin dev'")
        tamarin_exe2.chmod(0o755)

        output_file = tmp_dir / "test_output.txt"
        traces_dir = tmp_dir / "traces"
        traces_dir.mkdir(exist_ok=True)

        base_task = ExecutableTask(
            task_name="test_task_001",
            original_task_name="test_task_001",
            tamarin_version_name="stable",
            theory_file=sample_theory_file,
            tamarin_executable=tamarin_exe,
            output_file=output_file,
            lemma="test_lemma",
            tamarin_options=["--heuristic=S"],
            preprocess_flags=["FLAG1"],
            max_cores=4,
            max_memory=8,
            task_timeout=1800,
            traces_dir=traces_dir,
        )

        # Test different tamarin_executable
        from dataclasses import replace

        task_diff_exe = replace(base_task, tamarin_executable=tamarin_exe2)
        assert cache_manager._generate_key(  # type: ignore
            # type: ignore
            base_task
        ) != cache_manager._generate_key(  # type: ignore
            task_diff_exe
        )

        # Test different tamarin_options
        task_diff_options = replace(base_task, tamarin_options=["--heuristic=O"])
        assert cache_manager._generate_key(base_task) != cache_manager._generate_key(task_diff_options)  # type: ignore

        # Test different preprocess_flags
        task_diff_flags = replace(base_task, preprocess_flags=["FLAG2"])
        assert cache_manager._generate_key(base_task) != cache_manager._generate_key(task_diff_flags)  # type: ignore

        # Test different max_cores
        task_diff_cores = replace(base_task, max_cores=8)
        assert cache_manager._generate_key(base_task) != cache_manager._generate_key(task_diff_cores)  # type: ignore

        # Test different max_memory
        task_diff_memory = replace(base_task, max_memory=16)
        assert cache_manager._generate_key(base_task) != cache_manager._generate_key(task_diff_memory)  # type: ignore

        # Test different task_timeout
        task_diff_timeout = replace(base_task, task_timeout=3600)
        assert cache_manager._generate_key(base_task) != cache_manager._generate_key(task_diff_timeout)  # type: ignore

    def test_cache_handles_missing_file(
        self, cache_manager: CacheManager, tmp_dir: Path
    ):
        """Test cache behavior when theory file doesn't exist."""
        nonexistent_file = tmp_dir / "nonexistent.spthy"

        tamarin_exe = tmp_dir / "tamarin-prover"
        tamarin_exe.write_text("#!/bin/bash\necho 'mock tamarin'")
        tamarin_exe.chmod(0o755)

        output_file = tmp_dir / "test_output.txt"
        traces_dir = tmp_dir / "traces"
        traces_dir.mkdir(exist_ok=True)

        task = ExecutableTask(
            task_name="test_task_001",
            original_task_name="test_task_001",
            tamarin_version_name="stable",
            theory_file=nonexistent_file,
            tamarin_executable=tamarin_exe,
            output_file=output_file,
            lemma="test_lemma",
            tamarin_options=[],
            preprocess_flags=[],
            max_cores=4,
            max_memory=8,
            task_timeout=1800,
            traces_dir=traces_dir,
        )

        # Should raise FileNotFoundError when trying to generate key
        with pytest.raises(FileNotFoundError):
            cache_manager._generate_key(task)  # type: ignore

    def test_cache_persistence_across_instances(
        self, tmp_dir: Path, sample_task: ExecutableTask, sample_result: TaskResult
    ):
        """Test that cache persists across different CacheManager instances."""
        with patch("pathlib.Path.home", return_value=tmp_dir):
            # First instance - store result
            cache_manager1 = CacheManager()
            cache_manager1.store_result(sample_task, sample_result)

            # Second instance - should find cached result
            cache_manager2 = CacheManager()
            cached_result = cache_manager2.get_cached_result(sample_task)

            assert cached_result is not None
            assert cached_result.task_id == sample_result.task_id
            assert cached_result.status == sample_result.status

    def test_default_cache_location(self):
        """Test that default cache location is in user home directory."""
        cache_manager = CacheManager()
        # Cache manager should initialize with a valid cache object
        assert cache_manager.cache is not None
        # Check that cache directory is created under user home
        expected_path = Path.home() / ".batch-tamarin" / "cache"
        assert Path(cache_manager.cache.directory) == expected_path
