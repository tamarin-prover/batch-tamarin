"""
Centralized process manager for the Tamarin Wrapper.

This module provides a unified interface for launching and managing processes
in a non-blocking manner, with support for timeouts and proper termination.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from utils.notifications import notification_manager


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
        self, executable: Path, args: List[str], timeout: float = 30.0
    ) -> tuple[int, str, str]:
        """
        Launch a command in a non-blocking manner.

        Args:
            executable: Path to the executable
            args: Command arguments
            timeout: Timeout in seconds

        Returns:
            Tuple (return_code, stdout, stderr)
        """
        process_id = f"cmd_{self._process_counter}"
        self._process_counter += 1

        command = [str(executable)] + args

        try:
            # Create the process
            process = await asyncio.create_subprocess_exec(
                *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            # Create the task
            task = asyncio.create_task(self._wait_for_process(process))

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
                # Wait with timeout
                result = await asyncio.wait_for(task, timeout=timeout)
                return result

            except asyncio.TimeoutError:
                notification_manager.warning(
                    f"[ProcessManager] Command timed out: {' '.join(command)}"
                )
                await self._kill_process(process_id)
                return (-1, "", "Process timed out")

        except Exception as e:
            notification_manager.error(
                f"[ProcessManager] Error running command {' '.join(command)}: {e}"
            )
            return (-1, "", str(e))

        finally:
            # Clean up the process
            if process_id in self._active_processes:
                del self._active_processes[process_id]

    async def _wait_for_process(
        self, process: asyncio.subprocess.Process
    ) -> tuple[int, str, str]:
        """Wait for process completion and return results."""
        stdout, stderr = await process.communicate()

        return_code = process.returncode or 0
        stdout_str = stdout.decode() if stdout else ""
        stderr_str = stderr.decode() if stderr else ""

        return (return_code, stdout_str, stderr_str)

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
