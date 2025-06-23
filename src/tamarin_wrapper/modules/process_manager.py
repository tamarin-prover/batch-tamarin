"""
Centralized process manager for the Tamarin Wrapper.

This module provides a unified interface for launching and managing processes
in a non-blocking manner, with support for timeouts and proper termination.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

from ..model.executable_task import MemoryStats
from ..utils.notifications import notification_manager


@dataclass
class ProcessInfo:
    """Information about a running process."""

    process: asyncio.subprocess.Process
    task: asyncio.Task  # type: ignore
    path: Path
    command: List[str]
    start_time: float


class ProcessManager:
    """
    Centralized process manager.

    Manages launching, monitoring and termination of processes
    with timeout support and automatic cleanup.
    """

    def __init__(self):
        self._active_processes: Dict[str, ProcessInfo] = {}
        self._process_counter = 0
        self._memory_exceeded_processes: Dict[str, bool] = {}

    async def run_command(
        self,
        executable: Path,
        args: List[str],
        timeout: float = 30.0,
        memory_limit_mb: Optional[float] = None,
    ) -> tuple[int, str, str, Optional[MemoryStats]]:
        """
        Launch a command in a non-blocking manner with memory monitoring.

        Args:
            executable: Path to the executable
            args: Command arguments
            timeout: Timeout in seconds
            memory_limit_mb: Memory limit in MB, process will be killed if exceeded

        Returns:
            Tuple (return_code, stdout, stderr, memory_stats)
            return_code will be -2 if memory limit was exceeded
        """
        process_id = f"cmd_{self._process_counter}"
        self._process_counter += 1

        command = [str(executable)] + args

        try:
            # Create the process
            process = await asyncio.create_subprocess_exec(
                *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            # Create the task for process execution
            task = asyncio.create_task(self._wait_for_process(process))

            # Start memory monitoring
            memory_task = asyncio.create_task(
                self._monitor_memory(process, memory_limit_mb, process_id)
            )

            # Register the process
            process_info = ProcessInfo(
                process=process,
                task=task,
                path=executable,
                command=command,
                start_time=asyncio.get_event_loop().time(),
            )
            self._active_processes[process_id] = process_info
            self._memory_exceeded_processes[process_id] = False

            notification_manager.debug(
                f"[ProcessManager] Running command: {' '.join(command)}"
            )

            try:
                # Wait with timeout for both tasks
                done, pending = await asyncio.wait(
                    [task, memory_task],
                    timeout=timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Check if memory limit was exceeded
                if self._memory_exceeded_processes.get(process_id, False):
                    # Memory limit was exceeded
                    # Cancel any pending tasks
                    for pending_task in pending:
                        pending_task.cancel()

                    # Get memory stats from memory task
                    memory_stats = None
                    if memory_task in done:
                        try:
                            memory_stats = await memory_task
                        except Exception:
                            pass

                    notification_manager.warning(
                        f"[ProcessManager] Command exceeded memory limit: {' '.join(command)}"
                    )
                    return (-2, "", "Process exceeded memory limit", memory_stats)
                elif task in done:
                    # Process completed normally
                    result = await task
                    memory_task.cancel()

                    # Get memory stats if available
                    memory_stats = None
                    try:
                        memory_stats = await asyncio.wait_for(memory_task, timeout=1.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        pass

                    return (*result, memory_stats)
                else:
                    # Timeout occurred
                    notification_manager.warning(
                        f"[ProcessManager] Command timed out: {' '.join(command)}"
                    )
                    await self._kill_process(process_id)

                    # Try to get current memory stats before cancelling
                    memory_stats = None
                    if not memory_task.done():
                        try:
                            memory_stats = await asyncio.wait_for(
                                memory_task, timeout=0.5
                            )
                        except (asyncio.TimeoutError, asyncio.CancelledError):
                            pass

                    # Cancel memory monitoring if still running
                    if not memory_task.done():
                        memory_task.cancel()

                    return (-1, "", "Process timed out", memory_stats)

            except asyncio.TimeoutError:
                notification_manager.warning(
                    f"[ProcessManager] Command timed out: {' '.join(command)}"
                )
                await self._kill_process(process_id)

                # Try to get current memory stats before cancelling
                memory_stats = None
                if not memory_task.done():
                    try:
                        memory_stats = await asyncio.wait_for(memory_task, timeout=0.5)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        pass

                # Cancel memory monitoring if still running
                if not memory_task.done():
                    memory_task.cancel()

                return (-1, "", "Process timed out", memory_stats)

        except Exception as e:
            notification_manager.error(
                f"[ProcessManager] Error running command {' '.join(command)}: {e}"
            )
            return (-1, "", str(e), None)

        finally:
            # Clean up the process
            if process_id in self._active_processes:
                del self._active_processes[process_id]
            if process_id in self._memory_exceeded_processes:
                del self._memory_exceeded_processes[process_id]

    async def _wait_for_process(
        self, process: asyncio.subprocess.Process
    ) -> tuple[int, str, str]:
        """Wait for process completion and return results."""
        stdout, stderr = await process.communicate()

        return_code = process.returncode or 0
        stdout_str = stdout.decode() if stdout else ""
        stderr_str = stderr.decode() if stderr else ""

        return (return_code, stdout_str, stderr_str)

    async def _monitor_memory(
        self,
        process: asyncio.subprocess.Process,
        memory_limit_mb: Optional[float] = None,
        process_id: Optional[str] = None,
    ) -> Optional[MemoryStats]:
        """
        Monitor memory usage of a process during execution.

        Samples memory usage every 1 second and calculates peak and average memory efficiently.
        If memory_limit_mb is specified, kills the process when limit is exceeded.

        Args:
            process: The subprocess to monitor
            memory_limit_mb: Memory limit in MB, process will be killed if exceeded

        Returns:
            MemoryStats with peak and average memory usage in MB, or None if monitoring failed
            If memory limit is exceeded, returns the MemoryStats at time of termination
        """
        peak_memory_mb: float = 0.0
        avg_memory_mb: float = 0.0
        sample_count: int = 0

        try:
            # Get the psutil process object
            if not process.pid:
                return None

            psutil_process: psutil.Process = psutil.Process(process.pid)

            while process.returncode is None:
                try:
                    # Get memory info for the process and all its children
                    memory_info = psutil_process.memory_info()
                    memory_mb: float = float(
                        # Convert bytes to MB
                        getattr(memory_info, "rss", 0)
                    ) / (1024 * 1024)

                    # Also include memory from child processes
                    try:
                        children: List[psutil.Process] = psutil_process.children(recursive=True)  # type: ignore
                        for child in children:
                            child_memory = child.memory_info()
                            child_rss = float(getattr(child_memory, "rss", 0))
                            memory_mb += child_rss / (1024 * 1024)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        # Child processes may have terminated or we don't have access
                        pass

                    # Update peak memory
                    peak_memory_mb = max(peak_memory_mb, memory_mb)

                    # Calculate running average efficiently
                    sample_count += 1
                    avg_memory_mb = (
                        avg_memory_mb + (memory_mb - avg_memory_mb) / sample_count
                    )

                    # Check memory limit if specified
                    if memory_limit_mb is not None and memory_mb > memory_limit_mb:
                        notification_manager.warning(
                            f"[ProcessManager] Memory limit exceeded: {memory_mb:.1f}MB > {memory_limit_mb:.1f}MB"
                        )

                        # Mark this process as memory exceeded
                        if process_id and process_id in self._memory_exceeded_processes:
                            self._memory_exceeded_processes[process_id] = True

                        # Kill the process immediately
                        try:
                            if process.returncode is None:
                                process.terminate()
                                try:
                                    await asyncio.wait_for(process.wait(), timeout=2.0)
                                except asyncio.TimeoutError:
                                    process.kill()
                                    await process.wait()
                        except Exception as e:
                            notification_manager.debug(
                                f"[ProcessManager] Error killing process due to memory limit: {e}"
                            )

                        # Return memory stats at time of termination
                        return MemoryStats(
                            peak_memory_mb=peak_memory_mb, avg_memory_mb=avg_memory_mb
                        )

                    # Sample every 1 second
                    await asyncio.sleep(1.0)

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # Process terminated or we don't have access
                    break

        except (psutil.NoSuchProcess, ValueError):
            # Process doesn't exist or invalid PID
            return None
        except asyncio.CancelledError:
            # Monitoring was cancelled - return current stats if we have any
            if sample_count > 0:
                return MemoryStats(
                    peak_memory_mb=peak_memory_mb, avg_memory_mb=avg_memory_mb
                )
            return None
        except Exception as e:
            notification_manager.debug(f"[ProcessManager] Memory monitoring error: {e}")

        # Return memory stats if we have at least one sample
        if sample_count > 0:
            return MemoryStats(
                peak_memory_mb=peak_memory_mb, avg_memory_mb=avg_memory_mb
            )

        return None

    async def _kill_process(self, process_id: str) -> None:
        """Kill a process gracefully."""
        if process_id not in self._active_processes:
            return

        process_info = self._active_processes[process_id]
        process = process_info.process

        try:
            # Try SIGTERM first
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    # If SIGTERM doesn't work, use SIGKILL
                    process.kill()
                    await process.wait()

            # Cancel the task if it still exists
            if not process_info.task.done():  # type: ignore
                process_info.task.cancel()  # type: ignore

        except Exception as e:
            notification_manager.error(
                f"[ProcessManager] Error killing process {process_id}: {e}"
            )

    async def kill_all_processes(self) -> None:
        """Kill all active processes."""
        if not self._active_processes:
            return

        notification_manager.debug(
            f"[ProcessManager] Killing {len(self._active_processes)} active processes..."
        )

        # Create a list of IDs to avoid modification during iteration
        process_ids = list(self._active_processes.keys())

        # Kill all processes in parallel
        tasks = [self._kill_process(pid) for pid in process_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Clean up the registry
        self._active_processes.clear()

    def get_active_processes_count(self) -> int:
        """Return the number of active processes."""
        return len(self._active_processes)

    def get_active_processes_info(self) -> Dict[str, Dict[str, Any]]:
        """Return information about active processes."""
        result: Dict[str, Dict[str, Any]] = {}
        current_time = asyncio.get_event_loop().time()

        for process_id, info in self._active_processes.items():
            result[process_id] = {
                "path": str(info.path),
                "command": " ".join(info.command),
                "duration": current_time - info.start_time,
                "pid": info.process.pid if info.process.pid else None,
            }

        return result


# Global instance of the process manager
process_manager = ProcessManager()
