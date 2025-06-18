"""
Data models for output processing and analysis.

This module defines the data structures used for capturing, storing,
and analyzing Tamarin execution outputs using a hybrid regex + tree-sitter approach.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


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

    analysis_type: str
    """Analysis type: 'all-traces' or 'exists-trace'."""

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


# Enhanced data models for hybrid parsing approach


@dataclass
class StdoutAnalysis:
    """Results from parsing stdout using regex patterns."""

    analyzed_file: str
    """Path to the analyzed theory file."""

    output_file: str
    """Path to the generated output file."""

    processing_time: float
    """Total processing time in seconds."""

    warnings: List[str]
    """List of warning messages from stdout."""

    lemma_results: Dict[str, LemmaResult]
    """Map of lemma names to their verification results."""

    maude_version_warning: Optional[str] = None
    """Maude version compatibility warning if present."""

    tool_version_info: Optional[str] = None
    """Tool version information if present."""


@dataclass
class StderrAnalysis:
    """Results from analyzing stderr for error patterns."""

    error_type: Optional[ErrorType]
    """Categorized type of error if detected."""

    error_patterns_found: List[str]
    """List of error patterns that were matched."""

    context_lines: List[str]
    """Relevant context lines around errors."""

    is_critical_error: bool
    """Whether this is a critical error that prevents execution."""

    tamarin_logs: List[str]
    """Tamarin debug/info logs separated from errors."""


@dataclass
class SpthyLemmaInfo:
    """Detailed lemma information extracted from spthy file."""

    name: str
    """Lemma name."""

    attributes: List[str]
    """Lemma attributes like [sources], [reuse], etc."""

    analysis_type: str
    """Analysis type: all-traces, exists-trace."""

    formula: str
    """The lemma formula."""

    proof_status: str
    """Proof status: proven, unproven, failed."""

    proof_method: Optional[str] = None
    """Proof method: induction, contradiction, etc."""

    proof_steps: Optional[List[str]] = None
    """List of proof steps if available."""

    line_number: int = 0
    """Line number where lemma starts."""

    end_line: int = 0
    """Line number where lemma ends."""


@dataclass
class FunctionDeclaration:
    """Function declaration from spthy file."""

    name: str
    signature: str
    line_number: int


@dataclass
class RuleDeclaration:
    """Rule declaration from spthy file."""

    name: str
    premises: List[str]
    conclusions: List[str]
    line_number: int


@dataclass
class RestrictionDeclaration:
    """Restriction declaration from spthy file."""

    name: str
    formula: str
    line_number: int


@dataclass
class SpthyAnalysis:
    """Results from tree-sitter based spthy file parsing."""

    theory_name: str
    """Name of the theory."""

    lemmas: Dict[str, SpthyLemmaInfo]
    """Map of lemma names to detailed lemma information."""

    functions: List[FunctionDeclaration]
    """List of function declarations."""

    rules: List[RuleDeclaration]
    """List of rule declarations."""

    restrictions: List[RestrictionDeclaration]
    """List of restriction declarations."""

    parsing_errors: List[str]
    """List of parsing errors encountered."""


@dataclass
class EnhancedLemmaResult:
    """Combined lemma info from stdout parsing and spthy analysis."""

    name: str
    """Lemma name."""

    status: str
    """Status: verified, falsified, analysis_incomplete."""

    analysis_type: str
    """Analysis type: all-traces, exists-trace."""

    steps: Optional[int] = None
    """Number of proof steps."""

    time_ms: Optional[int] = None
    """Time taken in milliseconds."""

    # Enhanced from spthy analysis
    proof_method: Optional[str] = None
    """Proof method used."""

    proof_details: Optional[List[str]] = None
    """Detailed proof steps."""

    attributes: List[str] = field(default_factory=lambda: [])
    """Lemma attributes."""

    formula: Optional[str] = None
    """Lemma formula."""

    line_number: Optional[int] = None
    """Line number in source file."""


@dataclass
class ProcessingMetadata:
    """Metadata about the processing operation."""

    analyzed_file: str
    """Path to the analyzed file."""

    output_file: str
    """Path to the output file."""

    theory_name: Optional[str]
    """Name of the theory."""

    total_lemmas_found: int
    """Total number of lemmas found."""

    lemmas_with_proofs: int
    """Number of lemmas with proof information."""

    parsing_errors: List[str]
    """List of parsing errors."""

    maude_version_warning: Optional[str] = None
    """Maude version warning if present."""


@dataclass
class ProcessedTaskResult:
    """Final processed result for successful tasks."""

    task_id: str
    """Task identifier."""

    status: str
    """Overall task status."""

    processing_time: float
    """Total processing time."""

    lemma_results: Dict[str, EnhancedLemmaResult]
    """Map of lemma names to enhanced results."""

    warnings: List[str]
    """List of warnings."""

    metadata: ProcessingMetadata
    """Processing metadata."""

    spthy_analysis: Optional[SpthyAnalysis] = None
    """Optional spthy file analysis."""

    timestamp: datetime = field(default_factory=datetime.now)
    """When the processing was completed."""


@dataclass
class RawOutputSummary:
    """Summary of raw outputs for failed tasks."""

    last_stdout_lines: List[str]
    """Last few lines from stdout."""

    last_stderr_lines: List[str]
    """Last few lines from stderr."""

    stdout_length: int
    """Total length of stdout."""

    stderr_length: int
    """Total length of stderr."""


@dataclass
class FailureContext:
    """Additional context for failure analysis."""

    theory_name: Optional[str]
    """Name of the theory if parseable."""

    partial_lemma_results: Dict[str, LemmaResult]
    """Any lemma results that were parsed before failure."""

    last_successful_lemma: Optional[str]
    """Last lemma that was successfully processed."""

    failure_point: Optional[str]
    """Point in execution where failure occurred."""

    resource_usage: Optional[Dict[str, Any]]
    """Resource usage information if available."""


@dataclass
class FailedTaskResult:
    """Enhanced failure analysis with suggestions."""

    task_id: str
    """Task identifier."""

    error_analysis: ErrorAnalysis
    """Detailed error analysis."""

    suggested_modifications: TaskModifications
    """Suggested modifications for retry."""

    raw_outputs: RawOutputSummary
    """Summary of raw outputs."""

    context_info: FailureContext
    """Additional failure context."""

    timestamp: datetime = field(default_factory=datetime.now)
    """When the failure analysis was completed."""
