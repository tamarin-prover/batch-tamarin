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

    async def run_command(
        self,
        executable: Path,
        args: List[str],
        timeout: float = 30.0,
        memory_limit_mb: Optional[float] = None,
    ) -> tuple[int, str, str, Optional[MemoryStats]]:
        """
        Launch a command in a non-blocking manner with memory monitoring and optional memory limit.

        # Fresh memory info for this specific task - ensure no cross-task contamination
        mem_info: Dict[str, Any] = {"memory_stats": None, "oom_detected": False, "task_id": process_id}

        Args:
            executable: Path to the executable
            args: Command arguments
            timeout: Timeout in seconds

        Returns:
            Tuple (return_code, stdout, stderr, memory_stats)
        """
        mem_info: Dict[str, Any] = {"memory_stats": None}
        process_id = f"cmd_{self._process_counter}"
        self._process_counter += 1

        command = [str(executable)] + args

        memory_task = None
        try:
            # Create the process
            process = await asyncio.create_subprocess_exec(
                *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            # Create the task for process execution
            task = asyncio.create_task(self._wait_for_process(process, mem_info))

            # Start memory monitoring
            memory_task = asyncio.create_task(
                self._monitor_memory(process, memory_limit_mb, process_id, mem_info)
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

            notification_manager.debug(
                f"[ProcessManager] Running command: {' '.join(command)}"
            )

            try:
                # Wait with timeout for both tasks
                done, _ = await asyncio.wait(
                    [task, memory_task],
                    timeout=timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if task in done:
                    # Process completed normally
                    result = await task

                    # Get memory stats if available
                    memory_stats = None
                    if memory_task and not memory_task.done():
                        try:
                            memory_task.cancel()
                            memory_stats = await asyncio.wait_for(
                                memory_task, timeout=1.0
                            )
                        except (asyncio.TimeoutError, asyncio.CancelledError):
                            memory_stats = (
                                mem_info.get("memory_stats") if mem_info else None
                            )
                    else:
                        memory_stats = (
                            mem_info.get("memory_stats") if mem_info else None
                        )

                    notification_manager.debug(
                        f"[ProcessManager] Task completed normally: return_code={result[0]}, "
                        f"stderr='{result[2][:50] if len(result) > 2 and result[2] else ''}'"
                    )
                    return (*result, memory_stats)
                elif memory_task in done:
                    # Memory task completed - check if it was due to OOM
                    memory_stats = await memory_task
                    # Check if OOM was explicitly detected for THIS task
                    if mem_info and mem_info.get("oom_detected", False):
                        # Actual OOM condition detected for this specific task
                        notification_manager.debug(
                            f"[ProcessManager] OOM detected by memory monitoring for {process_id} - returning -2"
                        )
                        task.cancel()
                        await self._kill_process(process_id)
                        return (
                            -2,
                            "",
                            "Process killed due to memory limit exceeded",
                            memory_stats,
                        )
                    else:
                        # Memory monitoring completed normally (process ended), get main task result
                        result = await task
                        notification_manager.debug(
                            f"[ProcessManager] Memory monitoring completed for {process_id}, main task result: return_code={result[0]}"
                        )
                        return (*result, memory_stats)

                else:
                    # Timeout occurred
                    notification_manager.warning(
                        f"[ProcessManager] Command timed out: {' '.join(command)}"
                    )
                    await self._kill_process(process_id)

                    # Capture memory stats before cancelling
                    memory_stats = None
                    if memory_task and not memory_task.done():
                        try:
                            memory_task.cancel()
                            memory_stats = await asyncio.wait_for(
                                memory_task, timeout=1.0
                            )
                        except (asyncio.TimeoutError, asyncio.CancelledError):
                            memory_stats = (
                                mem_info.get("memory_stats") if mem_info else None
                            )
                    else:
                        memory_stats = (
                            mem_info.get("memory_stats") if mem_info else None
                        )

                    notification_manager.debug(
                        "[ProcessManager] Timeout occurred - returning -1"
                    )
                    return (-1, "", "Process timed out", memory_stats)

            except asyncio.TimeoutError:
                notification_manager.warning(
                    f"[ProcessManager] Command timed out: {' '.join(command)}"
                )
                await self._kill_process(process_id)

                # Ensure we capture memory stats before cancelling
                memory_stats = None
                if memory_task and not memory_task.done():
                    try:
                        memory_task.cancel()
                        memory_stats = await asyncio.wait_for(memory_task, timeout=1.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        memory_stats = (
                            mem_info.get("memory_stats") if mem_info else None
                        )
                else:
                    memory_stats = mem_info.get("memory_stats") if mem_info else None

                return (-1, "", "Process timed out", memory_stats)

        except asyncio.CancelledError:
            # Task was cancelled externally
            notification_manager.warning(
                f"[ProcessManager] Task cancelled for process_id={process_id}"
            )

            # Capture memory stats before cleanup
            memory_stats = None
            if memory_task and not memory_task.done():
                try:
                    memory_task.cancel()
                    memory_stats = await asyncio.wait_for(memory_task, timeout=1.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    memory_stats = mem_info.get("memory_stats") if mem_info else None
            else:
                memory_stats = mem_info.get("memory_stats") if mem_info else None

            # Always treat cancellation as regular failure, not OOM
            # OOM should only be detected through the memory monitoring completing first
            notification_manager.debug(
                "[ProcessManager] Process cancelled (external) - returning -1"
            )
            return (-1, "", "Process was cancelled", memory_stats)
        except Exception as e:
            notification_manager.error(
                f"[ProcessManager] Error running command {' '.join(command)}: {e}"
            )
            notification_manager.debug(
                "[ProcessManager] Exception occurred - returning -1"
            )
            return (-1, "", str(e), None)

        finally:
            # Clean up the process
            if process_id in self._active_processes:
                del self._active_processes[process_id]

    async def _wait_for_process(
        self,
        process: asyncio.subprocess.Process,
        mem_info: Optional[Dict[str, Any]] = None,
    ) -> tuple[int, str, str]:
        """Wait for process completion and return results."""
        try:
            stdout, stderr = await process.communicate()
        except asyncio.CancelledError:
            # Process was cancelled - always treat as regular cancellation
            # OOM detection should happen through the memory monitoring task completing first
            return (process.returncode or -1, "", "Process was cancelled")

        return_code = process.returncode or 0
        stdout_str = stdout.decode() if stdout else ""
        stderr_str = stderr.decode() if stderr else ""

        return (return_code, stdout_str, stderr_str)

    async def _monitor_memory(
        self,
        process: asyncio.subprocess.Process,
        memory_limit_mb: Optional[float] = None,
        process_id: Optional[str] = None,
        mem_info: Optional[Dict[str, Any]] = None,
    ) -> Optional[MemoryStats]:
        """
        Monitor memory usage of a process during execution.
        Raises OutOfMemoryError if memory limit is exceeded.

        Samples memory usage every 1 second and calculates peak and average memory efficiently.

        Args:
            process: The subprocess to monitor

        Returns:
            MemoryStats with peak and average memory usage in MB, or None if monitoring failed
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
                        children: List[psutil.Process] = psutil_process.children(  # type: ignore
                            recursive=True
                        )
                        for child in children:
                            child_memory = child.memory_info()
                            child_rss = float(getattr(child_memory, "rss", 0))
                            memory_mb += child_rss / (1024 * 1024)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        # Child processes may have terminated or we don't have access
                        pass

                    # Update peak memory
                    peak_memory_mb = max(peak_memory_mb, memory_mb)

                    # If memory limit is set and exceeded, kill process and mark OOM
                    if memory_limit_mb is not None and memory_mb > memory_limit_mb:
                        notification_manager.error(
                            f"[ProcessManager] Memory limit exceeded: {memory_mb:.2f} MB > {memory_limit_mb:.2f} MB - killing process {process_id}"
                        )

                        # Save final memory stats and mark OOM detected for THIS specific task
                        final_memory_stats = MemoryStats(
                            peak_memory_mb=peak_memory_mb, avg_memory_mb=avg_memory_mb
                        )
                        if mem_info is not None:
                            mem_info["memory_stats"] = final_memory_stats
                            mem_info["oom_detected"] = True
                            notification_manager.debug(
                                f"[ProcessManager] Set oom_detected=True for task {process_id}"
                            )

                        # Kill the process
                        if process_id:
                            await self._kill_process(process_id)
                        else:
                            process.kill()

                        # Break out of monitoring loop - process will be detected as killed
                        break
                    else:
                        # Log memory usage occasionally for debugging
                        if sample_count % 10 == 0:  # Every 10 seconds
                            notification_manager.debug(
                                f"[ProcessManager] Task {process_id} memory: {memory_mb:.1f}MB (limit: {memory_limit_mb:.1f}MB)"
                            )

                    # Calculate running average efficiently
                    sample_count += 1
                    avg_memory_mb = (
                        avg_memory_mb + (memory_mb - avg_memory_mb) / sample_count
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
            # Monitoring was cancelled (normal when process completes)
            pass
        except Exception as e:
            notification_manager.debug(f"[ProcessManager] Memory monitoring error: {e}")

        # Save final memory stats to mem_info before returning
        if sample_count > 0:
            final_stats = MemoryStats(
                peak_memory_mb=peak_memory_mb, avg_memory_mb=avg_memory_mb
            )
            if mem_info is not None:
                mem_info["memory_stats"] = final_stats
            return final_stats

        # Always return last known stats if available
        if mem_info is not None and mem_info.get("memory_stats") is not None:
            return mem_info["memory_stats"]
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
