"""
Data models for output processing and analysis.

This module defines the data structures used for capturing, storing,
and analyzing Tamarin execution outputs.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union


@dataclass
class CapturedOutput:
    """Raw output captured from task execution."""

    task_id: str
    """Unique identifier for the task that generated this output."""

    raw_stdout: str
    """Complete stdout from the task execution."""

    raw_stderr: str
    """Complete stderr from the task execution."""

    timestamp: datetime
    """When the task was started (from TaskResult.start_time)."""

    stdout_file_path: Optional[Path] = None
    """Path to the stored stdout file on disk."""

    stderr_file_path: Optional[Path] = None
    """Path to the stored stderr file on disk."""

    tamarin_output_file_path: Optional[Path] = None
    """Path to the Tamarin output file (generated with --output flag)."""


@dataclass
class LemmaResult:
    """Individual lemma verification result parsed from Tamarin output."""

    name: str
    """Name of the lemma."""

    status: str
    """Status: 'verified', 'falsified', or 'analysis_incomplete'."""

    time_ms: Optional[int] = None
    """Time taken to verify the lemma in milliseconds."""

    steps: Optional[int] = None
    """Number of proof steps taken."""


@dataclass
class ParsedTamarinOutput:
    """Structured Tamarin output after parsing raw execution output."""

    lemma_results: Dict[str, LemmaResult]
    """Map of lemma names to their verification results."""

    total_time_ms: int
    """Total execution time in milliseconds."""

    total_steps: int
    """Total number of proof steps across all lemmas."""

    warnings: List[str]
    """List of warning messages from Tamarin output."""

    errors: List[str]
    """List of error messages from Tamarin output."""


class ErrorType(Enum):
    """Types of errors that can occur during task execution."""

    TIMEOUT = "timeout"
    """Task exceeded its timeout limit."""

    MEMORY_EXHAUSTED = "memory"
    """Task ran out of available memory."""

    SYNTAX_ERROR = "syntax"
    """Syntax error in the theory file."""

    PROOF_FAILURE = "proof_failure"
    """Proof could not be completed."""

    SYSTEM_ERROR = "system"
    """System-level error (file not found, permission denied, etc.)."""


@dataclass
class ErrorAnalysis:
    """Analysis of a failed task execution."""

    error_type: ErrorType
    """Categorized type of the error."""

    description: str
    """Human-readable description of the error."""

    context_lines: List[str]
    """Relevant lines from stderr or stdout for context."""

    suggested_fixes: List[str]
    """List of suggested actions to resolve the error."""


@dataclass
class TaskModifications:
    """Modifications to apply when rerunning failed tasks."""

    timeout_multiplier: float = 1.0
    """Factor to multiply the original timeout by."""

    memory_limit_gb: Optional[int] = None
    """New memory limit in GB, or None to use recipe default."""

    additional_args: List[str] = field(default_factory=lambda: [])
    """Additional command-line arguments to add."""


@dataclass
class RerunRecipe:
    """Recipe for rerunning failed tasks with modifications."""

    task_ids: List[str]
    """List of task IDs to rerun."""

    modifications: TaskModifications
    """Modifications to apply to the tasks."""

    retry_count: int = 1
    """Number of times to retry each task."""


@dataclass
class Suggestion:
    """A suggested fix for an error."""

    description: str
    """Human-readable description of the suggestion."""

    confidence: float
    """Confidence level from 0.0 to 1.0."""

    config_changes: Dict[str, Union[str, int, float, bool]]
    """Suggested configuration changes."""

    explanation: str
    """Detailed explanation of why this suggestion might help."""
