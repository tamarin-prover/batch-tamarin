"""
Batch model representing all the context during the execution of the wrapper.
"""

from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from ..model.tamarin_recipe import GlobalConfig, TamarinVersion


class Resources(BaseModel):
    """Resources given to a task"""

    cores: int = Field(..., description="Max cores for a task")
    memory: int = Field(..., description="Max memory for a task, in GB")
    timeout: int = Field(..., description="Max timeout for a task, in seconds")


class TaskConfig(BaseModel):
    """Resolved config from recipe, complete description"""

    tamarin_alias: str = Field(
        ..., description="Alias representing tamarin used for this task"
    )
    lemma: str = Field(..., description="Lemma ran for this task")
    output_theory_file: Path = Field(..., description="Output theory file path")
    output_trace_file: Path = Field(..., description="Output trace file path")
    options: Optional[List[str]] = Field(None, description="Options given to this task")
    preprocessor_flags: Optional[List[str]] = Field(
        None, description="Flags given to the preprocessor"
    )
    resources: Resources = Field(..., description="Resources given to this task")


class TaskStatus(Enum):
    """Status of a task execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    SIGNAL_INTERRUPTED = "signal_interrupted"


class TaskExecMetadata(BaseModel):
    """Metadata of execution"""

    command: List[str] = Field(..., description="Command used to execute this task")
    status: TaskStatus = Field(..., description="Status of the task execution")
    cache_hit: bool = Field(..., description="Whether the task was cached")
    exec_start: str = Field(..., description="Start timestamp of execution")
    exec_end: str = Field(..., description="End timestamp of execution")
    exec_duration_monotonic: float = Field(
        ...,
        description="Duration of execution, in seconds, monotonic time measurement, close to wall-clock measurement (measuring pretty much the same things, batch-tamarin measure ALL the process execution, while tamarin-prover can't) but not using system clock.",
    )
    avg_memory: float = Field(
        ..., description="Average memory usage during execution, in MB"
    )
    peak_memory: float = Field(
        ..., description="Peak memory usage during execution, in MB"
    )


class LemmaResult(Enum):
    """Result for a single lemma."""

    VERIFIED = "verified"
    FALSIFIED = "falsified"
    UNTERMINATED = "unterminated"


class TaskSucceedResult(BaseModel):
    """Result for a successful task"""

    warnings: List[str] = Field(
        default_factory=list, description="Warning messages from Tamarin"
    )
    real_time_tamarin_measure: float = Field(
        ...,
        description="Tamarin reported processing time in seconds, this is a wall-clock time : computation time + I/O operations + external precesses (like Maude) wait + system scheduler wait + system calls. This is NOT : CPU Time, User Time or System Time",
    )
    lemma_result: LemmaResult = Field(..., description="Result of the lemma")
    steps: int = Field(..., description="Number of analysis steps")
    analysis_type: str = Field(
        ..., description="Type of analysis (all-traces, exists-trace)"
    )


class ErrorType(Enum):
    """Error type"""

    WRAPPER_KILLED = "wrapper_killed"
    KILLED = "killed"
    TERMINATED = "terminated"
    TIMEOUT = "timeout"
    MEMORY_LIMIT = "memory_limit"
    TAMARIN_ERROR = "tamarin_error"
    UNKNOWN = "unknown"


class TaskFailedResult(BaseModel):
    """Result for a failed task"""

    return_code: str = Field(default="", description="Return code of the failed task")
    error_type: ErrorType = Field(..., description="Type of error")
    error_description: str = Field(..., description="Deducted error by the wrapper")
    last_stderr_lines: List[str] = Field(
        default_factory=list, description="Last stderr lines"
    )


class ExecMetadata(BaseModel):
    """Global execution metadata"""

    total_tasks: int = Field(..., description="Total number of tasks")
    total_successes: int = Field(..., description="Total number of successful tasks")
    total_failures: int = Field(..., description="Total number of failed tasks")
    total_cache_hit: int = Field(..., description="Total number of cached tasks")
    total_runtime: float = Field(..., description="Total runtime in seconds")
    total_memory: float = Field(
        ..., description="Total memory usage (combined peaks) in MB"
    )
    max_runtime: float = Field(
        ..., description="Maximum runtime of a single task in seconds"
    )
    max_memory: float = Field(
        ..., description="Maximum memory usage (peak) of a single task in MB"
    )


class RichExecutableTask(BaseModel):
    """Task with execution information"""

    model_config = ConfigDict(extra="forbid")

    task_config: TaskConfig = Field(..., description="Task config from recipe")
    task_execution_metadata: TaskExecMetadata = Field(
        ..., description="Execution metadata"
    )
    task_result: Optional[Union[TaskSucceedResult, TaskFailedResult]] = Field(
        None, description="Result of the task"
    )


class RichTask(BaseModel):
    """Original recipe task with generated executable subtasks"""

    model_config = ConfigDict(extra="forbid")

    theory_file: str = Field(
        ..., description="Path to the .spthy theory file to analyze"
    )
    subtasks: Dict[str, RichExecutableTask] = Field(
        ...,
        description="Dictionary of generated executable tasks (lemma--version -> RichExecutableTask)",
    )


class Batch(BaseModel):
    """Global data of the wrapper"""

    model_config = ConfigDict(extra="forbid")

    recipe: str = Field(..., description="Name of the input configuration (recipe)")

    config: GlobalConfig = Field(
        ..., description="Global configuration, after resolution"
    )
    tamarin_versions: Dict[str, TamarinVersion] = Field(
        ..., description="Named aliases for different Tamarin prover executables"
    )
    execution_metadata: ExecMetadata = Field(
        ..., description="Global execution metadata"
    )
    tasks: Dict[str, RichTask] = Field(
        ...,
        description="Dictionary of original recipe tasks with their generated executable subtasks",
    )
