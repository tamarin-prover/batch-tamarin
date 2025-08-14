"""Integration tests for Docker execution support."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def docker_recipe_config(tmp_dir: Path) -> dict:
    """Create a simple Docker recipe configuration."""
    theory_file = tmp_dir / "test.spthy"
    theory_file.write_text(
        """
theory Test
begin
lemma test: "true"
end
"""
    )

    return {
        "config": {
            "global_max_cores": 2,
            "global_max_memory": 4,
            "default_timeout": 60,
            "output_directory": str(tmp_dir / "output"),
        },
        "tamarin_versions": {
            "docker_test": {"docker_image": {"image": "tamarin-prover:test"}}
        },
        "tasks": {
            "simple_test": {
                "theory_file": str(theory_file),
                "tamarin_versions": ["docker_test"],
                "output_file_prefix": "test_output",
            }
        },
    }


@pytest.fixture
def docker_recipe_file(tmp_dir: Path, docker_recipe_config: dict) -> Path:
    """Create a Docker recipe file."""
    recipe_file = tmp_dir / "docker_recipe.json"
    recipe_file.write_text(json.dumps(docker_recipe_config, indent=2))
    return recipe_file


class TestDockerIntegration:
    """Integration tests for Docker execution support."""

    @pytest.mark.asyncio
    async def test_config_manager_loads_docker_recipe(self, docker_recipe_file: Path):
        """Test that ConfigManager can load a Docker recipe."""
        from batch_tamarin.modules.config_manager import load_json_recipe

        recipe = await load_json_recipe(docker_recipe_file)

        # Verify Docker configuration is loaded correctly
        assert "docker_test" in recipe.tamarin_versions
        docker_version = recipe.tamarin_versions["docker_test"]
        assert docker_version.docker_image is not None
        assert docker_version.docker_image.image == "tamarin-prover:test"

    @pytest.mark.asyncio
    async def test_docker_task_command_generation(self, tmp_dir: Path):
        """Test that Docker tasks generate correct commands."""
        # Create a simple Docker task manually for testing
        from batch_tamarin.model.executable_task import ExecutableTask

        theory_file = tmp_dir / "test.spthy"
        theory_file.write_text("theory Test\nbegin\nlemma test: 'true'\nend")

        task = ExecutableTask(
            task_name="test_docker",
            original_task_name="test",
            tamarin_version_name="docker_test",
            tamarin_executable=None,
            docker_image="tamarin-prover:test",
            theory_file=theory_file,
            output_file=tmp_dir / "output.spthy",
            lemma="test_lemma",
            tamarin_options=["--heuristic=O"],
            preprocess_flags=["FLAG1"],
            max_cores=2,
            max_memory=4,
            task_timeout=60,
            traces_dir=tmp_dir / "traces",
        )

        # Generate command
        command = await task.to_command()

        # Verify Docker command structure
        assert command[0] == "tamarin-prover"
        assert "+RTS" in command
        assert f"-N{task.max_cores}" in command
        assert "-RTS" in command

        # Theory file should be relative name only
        assert "test.spthy" in command

        # Output paths should be relative
        assert any("--output-json=traces/" in arg for arg in command)
        assert any("--output-dot=traces/" in arg for arg in command)
        assert any("--output=proofs/" in arg for arg in command)

    def test_docker_cache_key_generation(self, tmp_dir: Path):
        """Test that Docker tasks generate unique cache keys."""
        from batch_tamarin.model.executable_task import ExecutableTask
        from batch_tamarin.modules.cache_manager import CacheManager

        cache_manager = CacheManager()

        theory_file = tmp_dir / "test.spthy"
        theory_file.write_text("theory Test\nbegin\nlemma test: 'true'\nend")

        task = ExecutableTask(
            task_name="test_docker",
            original_task_name="test",
            tamarin_version_name="docker_test",
            tamarin_executable=None,
            docker_image="tamarin-prover:test",
            theory_file=theory_file,
            output_file=tmp_dir / "output.spthy",
            lemma="test_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=2,
            max_memory=4,
            task_timeout=60,
            traces_dir=tmp_dir / "traces",
        )

        # Generate cache key
        cache_key = cache_manager._generate_key(task)  # type: ignore

        # Should be a valid SHA256 hash
        assert len(cache_key) == 64
        assert all(c in "0123456789abcdef" for c in cache_key)

        # Cache key should be different for different Docker images
        task.docker_image = "tamarin-prover:different"

        cache_key2 = cache_manager._generate_key(task)  # type: ignore
        assert cache_key != cache_key2

    @pytest.mark.asyncio
    @patch("batch_tamarin.modules.task_manager.docker_manager")
    @patch("batch_tamarin.modules.task_manager.task_manager._cache_manager")
    async def test_task_manager_routes_docker_tasks(
        self, mock_cache_manager, mock_docker_manager, tmp_dir: Path
    ):
        """Test that TaskManager routes Docker tasks to container execution."""
        from batch_tamarin.model.executable_task import ExecutableTask, MemoryStats
        from batch_tamarin.modules.docker_executor import ContainerResult
        from batch_tamarin.modules.task_manager import task_manager

        # Mock Docker manager
        mock_container_result = ContainerResult(
            exit_code=0,
            stdout="Success",
            stderr="",
            start_time=1000.0,
            end_time=1010.0,
            duration=10.0,
            memory_stats=MemoryStats(peak_memory_mb=512.0, avg_memory_mb=256.0),
        )
        mock_docker_manager.run_container = AsyncMock(
            return_value=mock_container_result
        )

        # Mock cache to always return None (cache miss)
        mock_cache_manager.get_cached_result.return_value = None

        # Create Docker task
        theory_file = tmp_dir / "test.spthy"
        theory_file.write_text("theory Test\nbegin\nlemma test: 'true'\nend")

        task = ExecutableTask(
            task_name="test_docker",
            original_task_name="test",
            tamarin_version_name="docker_test",
            tamarin_executable=None,
            docker_image="tamarin-prover:test",
            theory_file=theory_file,
            output_file=tmp_dir / "output.spthy",
            lemma="test_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=2,
            max_memory=4,
            task_timeout=60,
            traces_dir=tmp_dir / "traces",
        )

        # Execute task
        result = await task_manager.run_executable_task(task)

        # Verify Docker manager was called
        mock_docker_manager.run_container.assert_called_once()
        call_args = mock_docker_manager.run_container.call_args

        # Verify correct parameters passed to Docker manager
        assert call_args[1]["image"] == task.docker_image
        assert call_args[1]["memory_limit_gb"] == float(task.max_memory)
        assert call_args[1]["cpu_limit"] == float(task.max_cores)
        assert call_args[1]["timeout_seconds"] == float(task.task_timeout)

        # Verify result conversion
        assert result.return_code == 0
        assert result.stdout == "Success"
        assert result.memory_stats is not None
        assert result.memory_stats.peak_memory_mb == 512.0

    def test_docker_vs_local_command_builders(self, tmp_dir: Path):
        """Test that Docker and local tasks use different command builders."""
        from batch_tamarin.model.command_builder import (
            DockerCommandBuilder,
            LocalCommandBuilder,
            create_command_builder,
        )
        from batch_tamarin.model.executable_task import ExecutableTask

        # Create theory file
        theory_file = tmp_dir / "test.spthy"
        theory_file.write_text("theory Test\nbegin\nend")

        # Create local executable
        tamarin_exe = tmp_dir / "tamarin-prover"
        tamarin_exe.write_text("#!/bin/bash\necho 'tamarin'")
        tamarin_exe.chmod(0o755)

        # Docker task
        docker_task = ExecutableTask(
            task_name="test_docker",
            original_task_name="test",
            tamarin_version_name="docker_test",
            tamarin_executable=None,
            docker_image="tamarin-prover:test",
            theory_file=theory_file,
            output_file=tmp_dir / "docker_output.spthy",
            lemma="test_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=2,
            max_memory=4,
            task_timeout=60,
            traces_dir=tmp_dir / "traces",
        )

        # Local task
        local_task = ExecutableTask(
            task_name="test_local",
            original_task_name="test",
            tamarin_version_name="local_test",
            tamarin_executable=tamarin_exe,
            docker_image=None,
            theory_file=theory_file,
            output_file=tmp_dir / "local_output.spthy",
            lemma="test_lemma",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=2,
            max_memory=4,
            task_timeout=60,
            traces_dir=tmp_dir / "traces",
        )

        # Verify command builders are different
        docker_builder = create_command_builder(docker_task)
        local_builder = create_command_builder(local_task)

        assert isinstance(docker_builder, DockerCommandBuilder)
        assert isinstance(local_builder, LocalCommandBuilder)
