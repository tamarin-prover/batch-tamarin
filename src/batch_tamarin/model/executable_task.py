"""
ExecutableTask model for representing a single execution unit.

This module defines the ExecutableTask dataclass that represents a task
with a specific tamarin version, ready for execution by the ProcessManager.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional, Set

if TYPE_CHECKING:
    from .command_builder import CommandBuilder


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

    tamarin_version: Optional[str]
    """Version string of the tamarin version (e.g., '1.6.1', '1.10.0')"""

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

        # Initialize command builder
        from .command_builder import create_command_builder

        self._command_builder: "CommandBuilder" = create_command_builder(self)

    async def to_command(self) -> List[str]:
        """
        Convert this task to a runnable command.

        Uses the appropriate command builder based on the execution mode:
        - LocalCommandBuilder for local execution
        - DockerCommandBuilder for Docker execution

        Returns:
            List[str]: Command components ready for execution
        """
        return await self._command_builder.build(self)


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
