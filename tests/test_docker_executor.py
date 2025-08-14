"""Tests for DockerExecutor module."""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from batch_tamarin.model.executable_task import MemoryStats
from batch_tamarin.modules.docker_executor import (
    ContainerConfig,
    ContainerResult,
    DockerExecutor,
)


@pytest.fixture
def docker_executor():
    """Create a DockerExecutor instance for testing."""
    return DockerExecutor()


@pytest.fixture
def container_config():
    """Create a sample ContainerConfig for testing."""
    return ContainerConfig(
        image="tamarin-prover:test",
        command=["tamarin-prover", "test.spthy"],
        working_dir=Path("/tmp/test"),
        memory_limit_mb=1024.0,
        cpu_limit=2.0,
        timeout_seconds=60.0,
    )


class TestDockerExecutor:
    """Tests for DockerExecutor class."""

    @patch("batch_tamarin.modules.docker_executor.docker")
    def test_get_client_success(self, mock_docker, docker_executor):
        """Test successful Docker client creation."""
        # Mock Docker client
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_docker.from_env.return_value = mock_client

        client = docker_executor._get_client()

        assert client == mock_client
        mock_docker.from_env.assert_called_once()
        mock_client.ping.assert_called_once()

    @patch("batch_tamarin.modules.docker_executor.docker")
    def test_get_client_failure(self, mock_docker, docker_executor):
        """Test Docker client creation failure."""
        # Mock Docker client that fails to connect
        mock_docker.from_env.side_effect = Exception("Docker not available")

        with pytest.raises(RuntimeError, match="Failed to connect to Docker"):
            docker_executor._get_client()

    @pytest.mark.asyncio
    @patch("batch_tamarin.modules.docker_executor.docker")
    async def test_run_container_success(
        self, mock_docker, docker_executor, container_config
    ):
        """Test successful container execution."""
        # Mock Docker client and container
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.short_id = "abc123"
        mock_container.status = "running"
        mock_container.logs.return_value.decode.return_value = "Tamarin output"

        mock_client.ping.return_value = True
        mock_client.containers.create.return_value = mock_container
        mock_docker.from_env.return_value = mock_client

        # Mock container wait result
        async def mock_wait_for_container(container):
            return 0, "Tamarin output"

        # Mock container monitoring
        async def mock_monitor_container(container, memory_limit):
            return MemoryStats(peak_memory_mb=512.0, avg_memory_mb=256.0)

        docker_executor._wait_for_container = AsyncMock(
            return_value=(0, "Tamarin output")
        )
        docker_executor._monitor_container = AsyncMock(
            return_value=MemoryStats(peak_memory_mb=512.0, avg_memory_mb=256.0)
        )

        result = await docker_executor.run_container_with_monitoring(container_config)

        # Verify result
        assert isinstance(result, ContainerResult)
        assert result.exit_code == 0
        assert result.stdout == "Tamarin output"
        assert result.stderr == ""
        assert result.memory_stats is not None
        assert result.memory_stats.peak_memory_mb == 512.0

        # Verify Docker calls
        mock_client.containers.create.assert_called_once()
        create_kwargs = mock_client.containers.create.call_args[1]
        assert create_kwargs["image"] == container_config.image
        assert create_kwargs["command"] == container_config.command
        assert create_kwargs["mem_limit"] == int(
            container_config.memory_limit_mb * 1024 * 1024
        )
        assert create_kwargs["cpu_quota"] == int(container_config.cpu_limit * 100000)

    @pytest.mark.asyncio
    @patch("batch_tamarin.modules.docker_executor.docker")
    async def test_run_container_timeout(
        self, mock_docker, docker_executor, container_config
    ):
        """Test container execution timeout."""
        # Mock Docker client and container
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.short_id = "abc123"

        mock_client.ping.return_value = True
        mock_client.containers.create.return_value = mock_container
        mock_docker.from_env.return_value = mock_client

        # Mock timeout by making wait_for_container hang
        async def mock_hang():
            await asyncio.sleep(100)  # Simulate long-running process

        docker_executor._wait_for_container = AsyncMock(side_effect=mock_hang)
        docker_executor._monitor_container = AsyncMock(side_effect=mock_hang)

        # Use very short timeout for test
        container_config.timeout_seconds = 0.1

        result = await docker_executor.run_container_with_monitoring(container_config)

        # Verify timeout result
        assert result.exit_code == -1
        assert "timed out" in result.stderr
        assert result.memory_stats is None

    @pytest.mark.asyncio
    @patch("batch_tamarin.modules.docker_executor.docker")
    async def test_run_container_image_not_found(
        self, mock_docker, docker_executor, container_config
    ):
        """Test container execution with image not found."""
        from docker.errors import ImageNotFound

        # Mock Docker client
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.containers.create.side_effect = ImageNotFound("Image not found")
        mock_docker.from_env.return_value = mock_client

        result = await docker_executor.run_container_with_monitoring(container_config)

        # Verify error result
        assert result.exit_code == -1
        assert "Docker image not found" in result.stderr
        assert result.memory_stats is None

    @pytest.mark.asyncio
    @patch("batch_tamarin.modules.docker_executor.docker")
    async def test_run_container_api_error(
        self, mock_docker, docker_executor, container_config
    ):
        """Test container execution with API error."""
        from docker.errors import APIError

        # Mock Docker client
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.containers.create.side_effect = APIError("API error")
        mock_docker.from_env.return_value = mock_client

        result = await docker_executor.run_container_with_monitoring(container_config)

        # Verify error result
        assert result.exit_code == -1
        assert "Container execution failed" in result.stderr
        assert result.memory_stats is None

    @pytest.mark.asyncio
    async def test_wait_for_container(self, docker_executor):
        """Test waiting for container completion."""
        # Mock container
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_container.logs.return_value = b"Test output"

        exit_code, logs = await docker_executor._wait_for_container(mock_container)

        assert exit_code == 0
        assert logs == "Test output"
        mock_container.wait.assert_called_once()
        mock_container.logs.assert_called_once_with(stdout=True, stderr=True)

    @pytest.mark.asyncio
    async def test_monitor_container_normal(self, docker_executor):
        """Test normal container monitoring."""
        # Mock container
        mock_container = MagicMock()
        mock_container.status = "exited"  # Container exits immediately
        mock_container.reload = MagicMock()
        mock_container.stats.return_value = {
            "memory_stats": {"usage": 536870912}  # 512MB in bytes
        }

        memory_stats = await docker_executor._monitor_container(mock_container, 1024.0)

        assert memory_stats is not None
        assert memory_stats.peak_memory_mb == 512.0
        assert memory_stats.avg_memory_mb == 512.0

    @pytest.mark.asyncio
    async def test_monitor_container_memory_limit_exceeded(self, docker_executor):
        """Test container monitoring with memory limit exceeded."""
        # Mock container
        mock_container = MagicMock()
        mock_container.reload = MagicMock()

        # First call: running and over memory limit
        # Second call: not running (simulates container being killed)
        mock_container.status = "running"

        def side_effect(*args, **kwargs):
            mock_container.status = "exited"  # Change status after first call
            return {"memory_stats": {"usage": 2147483648}}  # 2GB in bytes

        mock_container.stats.side_effect = side_effect

        memory_stats = await docker_executor._monitor_container(
            mock_container, 1024.0
        )  # 1GB limit

        assert memory_stats is not None
        assert memory_stats.peak_memory_mb == 2048.0  # 2GB
        assert memory_stats.avg_memory_mb == 2048.0

    def test_parse_container_logs_success(self, docker_executor):
        """Test parsing container logs for successful execution."""
        logs = "Theory verification completed\nResult: All lemmas proved"

        stdout, stderr = docker_executor._parse_container_logs(logs, 0)

        assert stdout == logs
        assert stderr == ""

    def test_parse_container_logs_failure(self, docker_executor):
        """Test parsing container logs for failed execution."""
        logs = "Error: Failed to parse theory file\nException: Invalid syntax"

        stdout, stderr = docker_executor._parse_container_logs(logs, 1)

        assert stdout == ""
        assert stderr == logs

    def test_parse_container_logs_with_errors_in_success(self, docker_executor):
        """Test parsing container logs with error messages in successful execution."""
        logs = "Warning: Deprecated syntax\nTheory verification completed\nError pattern detected"

        stdout, stderr = docker_executor._parse_container_logs(logs, 0)

        assert "Theory verification completed" in stdout
        assert "Warning" in stderr
        assert "Error pattern detected" in stderr

    def test_close_client(self, docker_executor):
        """Test closing the Docker client."""
        # Mock client
        mock_client = MagicMock()
        docker_executor._client = mock_client

        docker_executor.close()

        mock_client.close.assert_called_once()
        assert docker_executor._client is None

    def test_close_client_with_error(self, docker_executor):
        """Test closing the Docker client with error."""
        # Mock client that raises exception on close
        mock_client = MagicMock()
        mock_client.close.side_effect = Exception("Close error")
        docker_executor._client = mock_client

        # Should not raise exception
        docker_executor.close()

        assert docker_executor._client is None


class TestContainerConfig:
    """Tests for ContainerConfig dataclass."""

    def test_container_config_creation(self):
        """Test ContainerConfig creation."""
        config = ContainerConfig(
            image="test:latest",
            command=["echo", "hello"],
            working_dir=Path("/tmp"),
            memory_limit_mb=512.0,
            cpu_limit=1.0,
            timeout_seconds=30.0,
            environment={"TEST": "value"},
        )

        assert config.image == "test:latest"
        assert config.command == ["echo", "hello"]
        assert config.working_dir == Path("/tmp")
        assert config.memory_limit_mb == 512.0
        assert config.cpu_limit == 1.0
        assert config.timeout_seconds == 30.0
        assert config.environment == {"TEST": "value"}

    def test_container_config_optional_environment(self):
        """Test ContainerConfig with optional environment."""
        config = ContainerConfig(
            image="test:latest",
            command=["echo", "hello"],
            working_dir=Path("/tmp"),
            memory_limit_mb=512.0,
            cpu_limit=1.0,
            timeout_seconds=30.0,
        )

        assert config.environment is None


class TestContainerResult:
    """Tests for ContainerResult dataclass."""

    def test_container_result_creation(self):
        """Test ContainerResult creation."""
        memory_stats = MemoryStats(peak_memory_mb=512.0, avg_memory_mb=256.0)
        start_time = time.time()
        end_time = start_time + 10.0

        result = ContainerResult(
            exit_code=0,
            stdout="Success",
            stderr="",
            start_time=start_time,
            end_time=end_time,
            duration=10.0,
            memory_stats=memory_stats,
        )

        assert result.exit_code == 0
        assert result.stdout == "Success"
        assert result.stderr == ""
        assert result.start_time == start_time
        assert result.end_time == end_time
        assert result.duration == 10.0
        assert result.memory_stats == memory_stats

    def test_container_result_optional_memory_stats(self):
        """Test ContainerResult with optional memory stats."""
        start_time = time.time()
        end_time = start_time + 10.0

        result = ContainerResult(
            exit_code=1,
            stdout="",
            stderr="Error",
            start_time=start_time,
            end_time=end_time,
            duration=10.0,
        )

        assert result.memory_stats is None
