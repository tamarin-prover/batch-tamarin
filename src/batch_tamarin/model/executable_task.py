"""
ExecutableTask model for representing a single execution unit.

This module defines the ExecutableTask dataclass that represents a task
with a specific tamarin version, ready for execution by the ProcessManager.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional


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
    """Name of the original task"""

    tamarin_version_name: str
    """Name of the tamarin version being used"""

    tamarin_executable: Path
    """Path to the tamarin executable"""

    theory_file: Path
    """Path to the .spthy theory file"""

    output_file: Path
    """Path where results should be written"""

    lemma: Optional[str]
    """Name of the specific lemma to prove, or None to prove all lemmas"""

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

    def to_command(self) -> List[str]:
        """
        Convert this task to a runnable command for ProcessManager.

        Generates command based on Tamarin CLI reference with Haskell RTS performance limiters:
        tamarin-prover +RTS -N{cores} -RTS [theory_file] [--prove=lemma] [tamarin_options] [preprocess_flags] --output=[output_file]

        Returns:
            List[str]: Command components ready for ProcessManager execution

        Examples:
            All lemmas: ["tamarin-prover", "+RTS", "-N4", "-RTS", "protocols/example.spthy", "--prove", "--output=results_stable.txt"]
            Specific lemma: ["tamarin-prover", "+RTS", "-N4", "-RTS", "protocols/complex.spthy", "--prove=secrecy",
                           "--diff", "-D=GoodKeysOnly", "--output=results_stable.txt"]
        """
        command = [str(self.tamarin_executable)]

        # Add Haskell RTS flags for performance limiting
        command.extend(["+RTS", f"-N{self.max_cores}"])

        command.append("-RTS")

        # Add theory file
        command.append(str(self.theory_file))

        # Handle lemma - if None, prove all lemmas
        if self.lemma:
            # Prove specific lemma
            command.append(f"--prove={self.lemma}")
        else:
            # Prove all lemmas
            command.append("--prove")

        # Add tamarin options if provided
        if self.tamarin_options:
            command.extend(self.tamarin_options)

        # Add preprocessor flags with -D= prefix if provided
        if self.preprocess_flags:
            for flag in self.preprocess_flags:
                command.append(f"-D={flag}")

        # Add output file
        command.append(f"--output={self.output_file}")

        return command


class TaskStatus(Enum):
    """Status of a task execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"


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
