"""Tests for command builder interfaces and implementations."""

from pathlib import Path
from unittest.mock import patch

import pytest

from batch_tamarin.model.command_builder import (
    CommandBuilder,
    DockerCommandBuilder,
    LocalCommandBuilder,
    create_command_builder,
)
from batch_tamarin.model.executable_task import ExecutableTask


@pytest.fixture
def sample_theory_file(tmp_dir: Path) -> Path:
    """Create a sample theory file for testing."""
    theory_file = tmp_dir / "test.spthy"
    theory_file.write_text('theory Test\nbegin\nlemma test: "true"\nend')
    return theory_file


@pytest.fixture
def sample_tamarin_executable(tmp_dir: Path) -> Path:
    """Create a sample tamarin executable for testing."""
    executable = tmp_dir / "tamarin-prover"
    executable.write_text("#!/bin/bash\necho 'mock tamarin'")
    executable.chmod(0o755)
    return executable


@pytest.fixture
def local_task(
    sample_theory_file: Path, sample_tamarin_executable: Path, tmp_dir: Path
) -> ExecutableTask:
    """Create a local ExecutableTask for testing."""
    return ExecutableTask(
        task_name="test_local",
        original_task_name="test",
        tamarin_version_name="local",
        tamarin_executable=sample_tamarin_executable,
        docker_image=None,
        theory_file=sample_theory_file,
        output_file=tmp_dir / "output.spthy",
        lemma="test_lemma",
        tamarin_options=["--heuristic=O"],
        preprocess_flags=["FLAG1"],
        max_cores=2,
        max_memory=4,
        task_timeout=60,
        traces_dir=tmp_dir / "traces",
    )


@pytest.fixture
def docker_task(sample_theory_file: Path, tmp_dir: Path) -> ExecutableTask:
    """Create a Docker ExecutableTask for testing."""
    return ExecutableTask(
        task_name="test_docker",
        original_task_name="test",
        tamarin_version_name="docker",
        tamarin_executable=None,
        docker_image="tamarin-prover:test",
        theory_file=sample_theory_file,
        output_file=tmp_dir / "output.spthy",
        lemma="test_lemma",
        tamarin_options=["--heuristic=O"],
        preprocess_flags=["FLAG1"],
        max_cores=2,
        max_memory=4,
        task_timeout=60,
        traces_dir=tmp_dir / "traces",
    )


class TestCommandBuilder:
    """Tests for abstract CommandBuilder interface."""

    def test_command_builder_is_abstract(self):
        """Test that CommandBuilder cannot be instantiated directly."""
        with pytest.raises(TypeError):
            CommandBuilder()


class TestLocalCommandBuilder:
    """Tests for LocalCommandBuilder implementation."""

    @pytest.mark.asyncio
    @patch("batch_tamarin.model.command_builder.compatibility_filter")
    async def test_build_local_command(self, mock_filter, local_task):
        """Test building a local command."""
        builder = LocalCommandBuilder()
        mock_filter.return_value = ["filtered_command"]

        command = await builder.build(local_task)

        # Verify compatibility filter was called
        mock_filter.assert_called_once()
        assert command == ["filtered_command"]

    @pytest.mark.asyncio
    @patch("batch_tamarin.model.command_builder.compatibility_filter")
    async def test_build_local_command_structure(self, mock_filter, local_task):
        """Test the structure of a built local command before filtering."""
        builder = LocalCommandBuilder()

        # Mock the filter to return the input unchanged
        async def identity_filter(command, executable):
            return command

        mock_filter.side_effect = identity_filter

        command = await builder.build(local_task)

        # Verify command structure
        expected_elements = [
            str(local_task.tamarin_executable),  # Executable path
            "+RTS",
            f"-N{local_task.max_cores}",
            "-RTS",  # RTS flags
            str(local_task.theory_file),  # Theory file
            f"--prove={local_task.lemma}",  # Lemma
            "--heuristic=O",  # Tamarin options
            "-D=FLAG1",  # Preprocessor flags
            f"--output-json={local_task.traces_dir}/{local_task.task_name}.json",  # JSON output
            f"--output-dot={local_task.traces_dir}/{local_task.task_name}.dot",  # DOT output
            f"--output={local_task.output_file}",  # Output file
        ]

        for element in expected_elements:
            assert element in command

    @pytest.mark.asyncio
    async def test_build_local_command_no_executable(self, local_task):
        """Test building local command without executable raises error."""
        local_task.tamarin_executable = None
        builder = LocalCommandBuilder()

        with pytest.raises(
            RuntimeError, match="Local execution requires tamarin_executable"
        ):
            await builder.build(local_task)

    @pytest.mark.asyncio
    @patch("batch_tamarin.model.command_builder.compatibility_filter")
    async def test_build_local_command_optional_fields(self, mock_filter, local_task):
        """Test building local command with optional fields missing."""
        # Remove optional fields
        local_task.lemma = None
        local_task.tamarin_options = None
        local_task.preprocess_flags = None

        builder = LocalCommandBuilder()
        mock_filter.return_value = ["filtered_command"]

        command = await builder.build(local_task)

        # Should not raise error and should call filter
        mock_filter.assert_called_once()
        assert command == ["filtered_command"]

    @pytest.mark.asyncio
    @patch("batch_tamarin.model.command_builder.compatibility_filter")
    async def test_build_local_command_multiple_flags(self, mock_filter, local_task):
        """Test building local command with multiple preprocessor flags."""
        local_task.preprocess_flags = ["FLAG1", "FLAG2", "FLAG3"]

        async def identity_filter(command, executable):
            return command

        mock_filter.side_effect = identity_filter
        builder = LocalCommandBuilder()

        command = await builder.build(local_task)

        # Verify all flags are present
        assert "-D=FLAG1" in command
        assert "-D=FLAG2" in command
        assert "-D=FLAG3" in command


class TestDockerCommandBuilder:
    """Tests for DockerCommandBuilder implementation."""

    @pytest.mark.asyncio
    async def test_build_docker_command(self, docker_task):
        """Test building a Docker command."""
        builder = DockerCommandBuilder()

        command = await builder.build(docker_task)

        # Verify command structure
        expected_elements = [
            "tamarin-prover",  # Base executable name
            "+RTS",
            f"-N{docker_task.max_cores}",
            "-RTS",  # RTS flags
            docker_task.theory_file.name,  # Theory file (relative)
            f"--prove={docker_task.lemma}",  # Lemma
            "--heuristic=O",  # Tamarin options
            "-D=FLAG1",  # Preprocessor flags
            f"--output-json=traces/{docker_task.task_name}.json",  # JSON output (relative)
            f"--output-dot=traces/{docker_task.task_name}.dot",  # DOT output (relative)
            f"--output=proofs/{docker_task.output_file.name}",  # Output file (relative)
        ]

        for element in expected_elements:
            assert element in command

    @pytest.mark.asyncio
    async def test_build_docker_command_no_image(self, docker_task):
        """Test building Docker command without image raises error."""
        docker_task.docker_image = None
        builder = DockerCommandBuilder()

        with pytest.raises(
            RuntimeError, match="Docker execution requires docker_image"
        ):
            await builder.build(docker_task)

    @pytest.mark.asyncio
    async def test_build_docker_command_relative_paths(self, docker_task):
        """Test that Docker command uses relative paths."""
        builder = DockerCommandBuilder()

        command = await builder.build(docker_task)

        # Verify paths are relative
        theory_file_arg = docker_task.theory_file.name
        assert theory_file_arg in command

        json_output = f"traces/{docker_task.task_name}.json"
        assert f"--output-json={json_output}" in command

        dot_output = f"traces/{docker_task.task_name}.dot"
        assert f"--output-dot={dot_output}" in command

        spthy_output = f"proofs/{docker_task.output_file.name}"
        assert f"--output={spthy_output}" in command

    @pytest.mark.asyncio
    async def test_build_docker_command_optional_fields(self, docker_task):
        """Test building Docker command with optional fields missing."""
        # Remove optional fields
        docker_task.lemma = None
        docker_task.tamarin_options = None
        docker_task.preprocess_flags = None

        builder = DockerCommandBuilder()

        command = await builder.build(docker_task)

        # Should not raise error
        assert "tamarin-prover" in command
        assert docker_task.theory_file.name in command

        # Should not have lemma or flags
        assert not any("--prove=" in arg for arg in command)
        assert not any(arg.startswith("-D=") for arg in command)
        assert "--heuristic=O" not in command


class TestCreateCommandBuilder:
    """Tests for command builder factory function."""

    def test_create_command_builder_local(self, local_task):
        """Test creating LocalCommandBuilder for local task."""
        builder = create_command_builder(local_task)

        assert isinstance(builder, LocalCommandBuilder)

    def test_create_command_builder_docker(self, docker_task):
        """Test creating DockerCommandBuilder for Docker task."""
        builder = create_command_builder(docker_task)

        assert isinstance(builder, DockerCommandBuilder)

    def test_create_command_builder_no_execution_mode(self, local_task):
        """Test creating command builder with no execution mode raises error."""
        local_task.tamarin_executable = None
        local_task.docker_image = None

        with pytest.raises(
            ValueError, match="Task must have either docker_image or tamarin_executable"
        ):
            create_command_builder(local_task)

    def test_create_command_builder_both_execution_modes(self, local_task):
        """Test creating command builder with both execution modes."""
        # This should not happen due to ExecutableTask validation,
        # but test the factory behavior
        local_task.docker_image = "test:latest"

        # Docker takes precedence
        builder = create_command_builder(local_task)
        assert isinstance(builder, DockerCommandBuilder)
