"""
ExecutableTask model for representing a single execution unit.

This module defines the ExecutableTask dataclass that represents a task
with a specific tamarin version, ready for execution by the ProcessManager.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional, Set


@dataclass
class ExecutableTask:
    """
    Represents a single execution unit (task + specific tamarin version).

    This dataclass combines a task configuration with a specific tamarin version
    to create a complete execution specification that can be converted to a
    command for the ProcessManager.

    Note: Each ExecutableTask handles only one lemma at a time to allow proper
    timeout handling with --prove=lemma.
    """

    task_name: str
    """Generated unique task name for execution"""

    original_task_name: str
    """Name of the original recipe task"""

    tamarin_version_name: str
    """Name of the tamarin version being used"""

    tamarin_executable: Optional[Path]
    """Path to the tamarin executable (for local execution)"""

    docker_image: Optional[str]
    """Docker image to use (for Docker execution)"""

    theory_file: Path
    """Path to the .spthy theory file"""

    output_file: Path
    """Path where results should be written"""

    lemma: str
    """Name of the specific lemma to prove"""

    tamarin_options: Optional[List[str]]
    """Additional command-line options"""

    preprocess_flags: Optional[List[str]]
    """Preprocessor flags"""

    max_cores: int
    """Maximum cores for this task"""

    max_memory: int
    """Maximum memory in GB for this task"""

    task_timeout: int
    """Timeout in seconds for this task"""

    traces_dir: Path
    """Directory where trace files should be written"""

    def __post_init__(self) -> None:
        """Validate that exactly one execution mode is specified."""
        modes: List[Any] = [self.tamarin_executable, self.docker_image]
        non_null_modes = [m for m in modes if m is not None]

        if len(non_null_modes) != 1:
            raise ValueError(
                "Exactly one of tamarin_executable or docker_image must be specified"
            )

    async def to_command(self) -> List[str]:
        """
        Convert this task to a runnable command for ProcessManager.

        Supports both local and Docker execution modes:
        - Local: tamarin-prover +RTS -N{cores} -RTS [args...]
        - Docker: docker run --rm --memory={memory}g -v {pwd}:/workspace -w /workspace {image} tamarin-prover +RTS -N{cores} -RTS [args...]

        Returns:
            List[str]: Command components ready for ProcessManager execution
        """
        # Build base tamarin command
        base_command = ["tamarin-prover"]

        # Add Haskell RTS flags for performance limiting
        base_command.extend(["+RTS", f"-N{self.max_cores}", "-RTS"])

        # Add theory file
        base_command.append(str(self.theory_file))

        if self.lemma:
            # Prove specific lemma
            base_command.append(f"--prove={self.lemma}")

        # Add tamarin options if provided
        if self.tamarin_options:
            base_command.extend(self.tamarin_options)

        # Add preprocessor flags with -D= prefix if provided
        if self.preprocess_flags:
            for flag in self.preprocess_flags:
                base_command.append(f"-D={flag}")

        # Add trace output parameters
        base_command.append(f"--output-json={self.traces_dir}/{self.task_name}.json")
        base_command.append(f"--output-dot={self.traces_dir}/{self.task_name}.dot")

        # Add output file
        base_command.append(f"--output={self.output_file}")

        # Handle execution mode
        if self.docker_image:
            # Docker execution mode
            from ..modules.docker_manager import docker_manager

            return docker_manager.create_docker_command(
                base_command,
                self.docker_image,
                self.theory_file.parent,
                self.max_memory,
            )
        elif self.tamarin_executable:
            # Local execution mode
            # Replace "tamarin-prover" with actual executable path
            base_command[0] = str(self.tamarin_executable)

            # Apply compatibility filtering based on tamarin version
            from ..utils.compatibility_filter import compatibility_filter

            filtered_command = await compatibility_filter(
                base_command, self.tamarin_executable
            )
            return filtered_command
        else:
            # This should never happen due to __post_init__ validation
            raise RuntimeError("No execution mode configured")


class TaskStatus(Enum):
    """Status of a task execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    SIGNAL_INTERRUPTED = "signal_interrupted"


@dataclass
class MemoryStats:
    """Memory usage statistics for a task execution."""

    peak_memory_mb: float
    avg_memory_mb: float


@dataclass
class TaskResult:
    """Result of a completed task execution."""

    task_id: str
    status: TaskStatus
    return_code: int
    stdout: str
    stderr: str
    start_time: float
    end_time: float
    duration: float
    memory_stats: Optional[MemoryStats] = None


@dataclass
class ProgressReport:
    """Current progress report of all tasks."""

    total_tasks: int
    pending_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    current_time: float


@dataclass
class ExecutionSummary:
    """Summary of execution results."""

    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    total_duration: float
    task_results: List[TaskResult]
    cache_entries: int = 0
    cached_tasks: int = 0
    cache_volume: int = 0
    cached_task_ids: Set[str] = field(default_factory=lambda: set())
