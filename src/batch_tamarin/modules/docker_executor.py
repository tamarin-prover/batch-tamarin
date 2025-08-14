"""Docker execution module for batch-tamarin.

This module provides async container execution with real-time resource monitoring,
timeout handling, and proper cleanup. It integrates with the Docker SDK for Python
to provide seamless containerized execution of Tamarin tasks.
"""

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import docker
from docker import DockerClient
from docker.errors import APIError, ContainerError, ImageNotFound
from docker.models.containers import Container

from ..model.executable_task import MemoryStats
from ..utils.notifications import notification_manager


@dataclass
class ContainerConfig:
    """Configuration for Docker container execution."""

    image: str
    command: List[str]
    working_dir: Path
    memory_limit_mb: float
    cpu_limit: float
    timeout_seconds: float
    environment: Optional[Dict[str, str]] = None


@dataclass
class ContainerResult:
    """Result of container execution with stats and output."""

    exit_code: int
    stdout: str
    stderr: str
    start_time: float
    end_time: float
    duration: float
    memory_stats: Optional[MemoryStats] = None


class DockerExecutor:
    """Async Docker container executor with resource monitoring."""

    def __init__(self):
        """Initialize the DockerExecutor with a Docker client."""
        self._client: Optional[DockerClient] = None

    def _get_client(self) -> DockerClient:
        """Get Docker client, creating it lazily."""
        if self._client is None:
            try:
                self._client = docker.from_env()
                # Test connection
                self._client.ping()
            except Exception as e:
                raise RuntimeError(f"Failed to connect to Docker: {e}")
        return self._client

    async def run_container_with_monitoring(
        self, config: ContainerConfig
    ) -> ContainerResult:
        """
        Run a container with real-time monitoring and resource enforcement.

        Args:
            config: Container configuration including limits and command

        Returns:
            ContainerResult with execution details and stats

        Raises:
            RuntimeError: If Docker is not available or container execution fails
        """
        client = self._get_client()
        container: Optional[Container] = None
        start_time = time.time()

        try:
            # Convert memory limit from MB to bytes
            memory_bytes = int(config.memory_limit_mb * 1024 * 1024)

            # Calculate CPU quota and period for CPU limit
            # Docker uses CPU quota (microseconds per period) to limit CPU usage
            # 1.0 CPU = 100000 microseconds per 100000 microseconds period
            cpu_period = 100000  # 100ms
            cpu_quota = int(config.cpu_limit * cpu_period)

            # Create container with resource limits
            # Mount the working directory and use it as the working directory inside container
            working_dir_abs = str(config.working_dir.absolute())
            container = client.containers.create(
                image=config.image,
                command=config.command,
                working_dir=working_dir_abs,
                volumes={working_dir_abs: {"bind": working_dir_abs, "mode": "rw"}},
                mem_limit=memory_bytes,
                cpu_quota=cpu_quota,
                cpu_period=cpu_period,
                detach=True,
                auto_remove=False,  # Don't auto-remove - we need to get logs first
                environment=config.environment or {},
                network_disabled=False,  # Allow network access for potential dependencies
            )

            notification_manager.debug(
                f"[DockerExecutor] Created container {container.short_id} "
                f"with limits: {config.memory_limit_mb}MB, {config.cpu_limit} CPUs"
            )

            # Start the container
            container.start()

            notification_manager.debug(
                f"[DockerExecutor] Started container {container.short_id}, "
                f"waiting up to {config.timeout_seconds}s for completion"
            )

            # Start monitoring task
            monitor_task = asyncio.create_task(
                self._monitor_container(container, config.memory_limit_mb)
            )

            # Wait for completion with timeout
            wait_task = asyncio.create_task(self._wait_for_container(container))

            try:
                # Wait for either completion or timeout
                wait_start = time.time()
                done, pending = await asyncio.wait(
                    [wait_task, monitor_task],
                    timeout=config.timeout_seconds,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                wait_duration = time.time() - wait_start

                notification_manager.debug(
                    f"[DockerExecutor] Wait completed after {wait_duration:.2f}s, "
                    f"done tasks: {len(done)}, pending: {len(pending)}"
                )

                if wait_task in done:
                    # Container completed normally
                    try:
                        exit_code, logs = await wait_task
                        monitor_task.cancel()

                        # Get memory stats if available
                        memory_stats = None
                        try:
                            memory_stats = await asyncio.wait_for(
                                monitor_task, timeout=1.0
                            )
                        except (asyncio.TimeoutError, asyncio.CancelledError):
                            pass

                        end_time = time.time()

                        # Split logs into stdout and stderr
                        # Docker logs are interleaved, we'll try to separate them
                        stdout, stderr = self._parse_container_logs(logs, exit_code)

                        notification_manager.debug(
                            f"[DockerExecutor] Container {container.short_id} "
                            f"completed with exit code {exit_code} in {end_time - start_time:.2f}s"
                        )

                        return ContainerResult(
                            exit_code=exit_code,
                            stdout=stdout,
                            stderr=stderr,
                            start_time=start_time,
                            end_time=end_time,
                            duration=end_time - start_time,
                            memory_stats=memory_stats,
                        )
                    except Exception as wait_error:
                        # Error getting container results - this might be the actual issue
                        notification_manager.error(
                            f"[DockerExecutor] Error getting container results: {wait_error}"
                        )

                        # Try to get logs directly from container before it's cleaned up
                        try:
                            container.reload()
                            logs = container.logs(stdout=True, stderr=True).decode(
                                "utf-8"
                            )
                            exit_code = (
                                container.attrs["State"]["ExitCode"]
                                if container.attrs
                                else -1
                            )

                            end_time = time.time()
                            stdout, stderr = self._parse_container_logs(logs, exit_code)

                            return ContainerResult(
                                exit_code=exit_code,
                                stdout=stdout,
                                stderr=stderr,
                                start_time=start_time,
                                end_time=end_time,
                                duration=end_time - start_time,
                                memory_stats=None,
                            )
                        except Exception as logs_error:
                            notification_manager.error(
                                f"[DockerExecutor] Could not get container logs: {logs_error}"
                            )

                            # Return the original wait error
                            end_time = time.time()
                            return ContainerResult(
                                exit_code=-1,
                                stdout="",
                                stderr=f"Error getting container results: {wait_error}",
                                start_time=start_time,
                                end_time=end_time,
                                duration=end_time - start_time,
                                memory_stats=None,
                            )

                else:
                    # Timeout occurred - but let's check if container is actually still running
                    try:
                        container.reload()
                        container_status = container.status
                        exit_code = (
                            container.attrs.get("State", {}).get("ExitCode", "unknown")
                            if container.attrs
                            else "unknown"
                        )

                        notification_manager.warning(
                            f"[DockerExecutor] Container {container.short_id} hit timeout after {wait_duration:.2f}s "
                            f"(limit: {config.timeout_seconds}s), status: {container_status}, exit_code: {exit_code}"
                        )

                        # If container already exited, try to get its logs instead of treating as timeout
                        if container_status in ["exited", "dead"]:
                            notification_manager.debug(
                                f"[DockerExecutor] Container {container.short_id} already exited, getting logs"
                            )
                            try:
                                logs = container.logs(stdout=True, stderr=True).decode(
                                    "utf-8"
                                )
                                actual_exit_code = (
                                    container.attrs.get("State", {}).get("ExitCode", -1)
                                    if container.attrs
                                    else -1
                                )

                                end_time = time.time()
                                stdout, stderr = self._parse_container_logs(
                                    logs, actual_exit_code
                                )

                                # Cancel monitoring task
                                monitor_task.cancel()

                                notification_manager.debug(
                                    f"[DockerExecutor] Retrieved logs from exited container {container.short_id}, "
                                    f"exit_code: {actual_exit_code}"
                                )

                                return ContainerResult(
                                    exit_code=actual_exit_code,
                                    stdout=stdout,
                                    stderr=stderr,
                                    start_time=start_time,
                                    end_time=end_time,
                                    duration=end_time - start_time,
                                    memory_stats=None,
                                )
                            except Exception as logs_error:
                                notification_manager.error(
                                    f"[DockerExecutor] Failed to get logs from exited container: {logs_error}"
                                )

                    except Exception as status_error:
                        notification_manager.debug(
                            f"[DockerExecutor] Could not check container status: {status_error}"
                        )

                    notification_manager.warning(
                        f"[DockerExecutor] Container {container.short_id} timed out after {wait_duration:.2f}s"
                    )

                    # Get current memory stats before killing
                    memory_stats = None
                    if not monitor_task.done():
                        try:
                            memory_stats = await asyncio.wait_for(
                                monitor_task, timeout=0.5
                            )
                        except (asyncio.TimeoutError, asyncio.CancelledError):
                            pass

                    # Kill the container
                    try:
                        container.kill()
                        container.wait(timeout=5)
                    except Exception as e:
                        notification_manager.debug(
                            f"[DockerExecutor] Error killing container: {e}"
                        )

                    # Cancel pending tasks
                    for pending_task in pending:
                        pending_task.cancel()

                    end_time = time.time()

                    return ContainerResult(
                        exit_code=-1,
                        stdout="",
                        stderr="Process timed out",
                        start_time=start_time,
                        end_time=end_time,
                        duration=end_time - start_time,
                        memory_stats=memory_stats,
                    )

            except asyncio.TimeoutError:
                # Fallback timeout handling
                notification_manager.warning(
                    f"[DockerExecutor] Container {container.short_id} timed out (fallback)"
                )

                try:
                    container.kill()
                    container.wait(timeout=5)
                except Exception:
                    pass

                # Cancel monitoring
                monitor_task.cancel()
                wait_task.cancel()

                end_time = time.time()

                return ContainerResult(
                    exit_code=-1,
                    stdout="",
                    stderr="Process timed out",
                    start_time=start_time,
                    end_time=end_time,
                    duration=end_time - start_time,
                    memory_stats=None,
                )

        except ImageNotFound:
            notification_manager.error(
                f"[DockerExecutor] Docker image not found: {config.image}"
            )
            end_time = time.time()
            return ContainerResult(
                exit_code=-1,
                stdout="",
                stderr=f"Docker image not found: {config.image}",
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                memory_stats=None,
            )

        except (ContainerError, APIError) as e:
            notification_manager.error(
                f"[DockerExecutor] Container execution failed: {e}"
            )
            end_time = time.time()
            return ContainerResult(
                exit_code=-1,
                stdout="",
                stderr=f"Container execution failed: {e}",
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                memory_stats=None,
            )

        except Exception as e:
            notification_manager.error(f"[DockerExecutor] Unexpected error: {e}")
            end_time = time.time()
            return ContainerResult(
                exit_code=-1,
                stdout="",
                stderr=f"Unexpected error: {e}",
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                memory_stats=None,
            )

        finally:
            # Ensure container cleanup
            if container:
                try:
                    container.remove(force=True)
                except Exception as e:
                    notification_manager.debug(
                        f"[DockerExecutor] Error removing container: {e}"
                    )

    async def _wait_for_container(self, container: Container) -> tuple[int, str]:
        """Wait for container to complete and return exit code and logs."""
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()

        def wait_and_get_logs():
            result = container.wait()
            logs = container.logs(stdout=True, stderr=True).decode("utf-8")
            return result["StatusCode"], logs

        return await loop.run_in_executor(None, wait_and_get_logs)

    async def _monitor_container(
        self, container: Container, memory_limit_mb: float
    ) -> Optional[MemoryStats]:
        """Monitor container memory usage and collect stats."""
        peak_memory_mb = 0.0
        avg_memory_mb = 0.0
        sample_count = 0

        try:
            while True:
                # Check if container is still running
                container.reload()
                if container.status != "running":
                    break

                # Get container stats
                try:
                    stats_stream = container.stats(stream=False)

                    # Parse memory usage
                    memory_stats = stats_stream.get("memory_stats", {})
                    if memory_stats:
                        usage = memory_stats.get("usage", 0)
                        memory_mb = float(usage) / (1024 * 1024)

                        # Update peak memory
                        peak_memory_mb = max(peak_memory_mb, memory_mb)

                        # Calculate running average
                        sample_count += 1
                        avg_memory_mb = (
                            avg_memory_mb + (memory_mb - avg_memory_mb) / sample_count
                        )

                        # Check memory limit (Docker should handle this, but double-check)
                        if memory_mb > memory_limit_mb:
                            notification_manager.warning(
                                f"[DockerExecutor] Container memory usage "
                                f"{memory_mb:.1f}MB exceeds limit {memory_limit_mb:.1f}MB"
                            )
                            # Docker should kill the container automatically
                            break

                except Exception as e:
                    notification_manager.debug(
                        f"[DockerExecutor] Error getting container stats: {e}"
                    )
                    break

                # Sample every second
                await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            # Monitoring was cancelled
            pass
        except Exception as e:
            notification_manager.debug(f"[DockerExecutor] Memory monitoring error: {e}")

        # Return stats if we have samples
        if sample_count > 0:
            return MemoryStats(
                peak_memory_mb=peak_memory_mb, avg_memory_mb=avg_memory_mb
            )
        return None

    def _parse_container_logs(self, logs: str, exit_code: int) -> tuple[str, str]:
        """
        Parse container logs into stdout and stderr.

        Docker logs are interleaved, so we use some heuristics to separate them.
        For Tamarin, errors typically go to stderr and results to stdout.
        """
        if not logs:
            return "", ""

        # If exit code is 0, most output is likely stdout
        if exit_code == 0:
            # Look for error patterns that might be stderr
            error_lines = []
            stdout_lines = []

            for line in logs.split("\n"):
                line_lower = line.lower()
                if any(
                    pattern in line_lower
                    for pattern in [
                        "error",
                        "warning",
                        "fail",
                        "exception",
                        "traceback",
                    ]
                ):
                    error_lines.append(line)
                else:
                    stdout_lines.append(line)

            return "\n".join(stdout_lines), "\n".join(error_lines)
        else:
            # If exit code != 0, more likely that output contains errors
            return "", logs

    def close(self) -> None:
        """Close the Docker client connection."""
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                notification_manager.debug(
                    f"[DockerExecutor] Error closing Docker client: {e}"
                )
            finally:
                self._client = None


# Global instance for reuse
docker_executor = DockerExecutor()
