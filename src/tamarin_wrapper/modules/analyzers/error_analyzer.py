"""
Error analyzer for categorizing and suggesting fixes for Tamarin execution failures.

This module analyzes stderr patterns and execution context to provide
actionable suggestions for resolving issues.
"""

from typing import Any, Dict, List

from ...model.output_models import (
    ErrorAnalysis,
    ErrorType,
    FailureContext,
    StderrAnalysis,
    TaskModifications,
)


class ErrorAnalyzer:
    """
    Analyzes errors and provides suggestions for resolution.
    """

    # Mapping of error types to suggested modifications
    ERROR_FIXES: Dict[ErrorType, Dict[str, Any]] = {
        ErrorType.MEMORY_EXHAUSTED: {
            "timeout_multiplier": 1.0,  # Don't increase timeout for memory issues
            "memory_multiplier": 2.0,  # Double memory allocation
            "additional_args": ["+RTS", "-H1G", "-RTS"],  # Increase heap size
            "suggested_actions": [
                "Increase memory limit in recipe configuration",
                "Consider splitting complex theories into smaller parts",
                "Use more specific lemma targeting with --prove=lemma_name",
                "Check if the theory has unbounded loops or infinite search spaces",
            ],
        },
        ErrorType.TIMEOUT: {
            "timeout_multiplier": 2.0,  # Double timeout
            "memory_multiplier": 1.0,  # Keep same memory
            "additional_args": ["--heuristic=o", "--oraclename=oracle.py"],
            "suggested_actions": [
                "Increase timeout in recipe configuration",
                "Use proof automation heuristics",
                "Consider manual proof guidance",
                "Split complex lemmas into smaller sub-lemmas",
            ],
        },
        ErrorType.SYNTAX_ERROR: {
            "timeout_multiplier": 1.0,
            "memory_multiplier": 1.0,
            "additional_args": [],
            "suggested_actions": [
                "Check theory file syntax carefully",
                "Verify all rules and lemmas are properly formatted",
                "Check for missing semicolons or brackets",
                "Validate theory file with tamarin-prover --parse-only",
            ],
        },
        ErrorType.SYSTEM_ERROR: {
            "timeout_multiplier": 1.0,
            "memory_multiplier": 1.0,
            "additional_args": [],
            "suggested_actions": [
                "Check file permissions and paths",
                "Verify tamarin-prover is properly installed",
                "Ensure output directory is writable",
                "Check available disk space",
            ],
        },
        ErrorType.PROOF_FAILURE: {
            "timeout_multiplier": 1.5,  # Slightly more time
            "memory_multiplier": 1.2,  # Slightly more memory
            "additional_args": ["--lemma-mode=incremental"],
            "suggested_actions": [
                "Review lemma formulation - it might be false",
                "Add helper lemmas or restrictions",
                "Use manual proof construction",
                "Check if the protocol model is correct",
            ],
        },
    }

    def analyze_error(
        self, stderr_analysis: StderrAnalysis, failure_context: FailureContext
    ) -> ErrorAnalysis:
        """
        Analyze error and provide categorized analysis with suggestions.

        Args:
            stderr_analysis: Analysis of stderr content
            failure_context: Additional context about the failure

        Returns:
            ErrorAnalysis with categorized error and suggestions
        """
        if not stderr_analysis.error_type:
            return self._create_unknown_error_analysis(stderr_analysis)

        error_type = stderr_analysis.error_type
        description = self._generate_error_description(error_type, stderr_analysis)
        context_lines = stderr_analysis.context_lines
        suggested_fixes = self._generate_suggested_fixes(error_type, failure_context)

        return ErrorAnalysis(
            error_type=error_type,
            description=description,
            context_lines=context_lines,
            suggested_fixes=suggested_fixes,
        )

    def suggest_task_modifications(
        self, error_type: ErrorType, current_timeout: int, current_memory: int
    ) -> TaskModifications:
        """
        Suggest modifications for task retry based on error type.

        Args:
            error_type: The type of error encountered
            current_timeout: Current timeout in seconds
            current_memory: Current memory limit in GB

        Returns:
            TaskModifications with suggested changes
        """
        if error_type not in self.ERROR_FIXES:
            return TaskModifications()

        fixes = self.ERROR_FIXES[error_type]

        new_timeout_multiplier = fixes.get("timeout_multiplier", 1.0)
        memory_multiplier = fixes.get("memory_multiplier", 1.0)
        additional_args = fixes.get("additional_args", [])

        new_memory = None
        if memory_multiplier > 1.0:
            new_memory = max(
                int(current_memory * memory_multiplier), current_memory + 1
            )

        return TaskModifications(
            timeout_multiplier=new_timeout_multiplier,
            memory_limit_gb=new_memory,
            additional_args=additional_args,
        )

    def _create_unknown_error_analysis(
        self, stderr_analysis: StderrAnalysis
    ) -> ErrorAnalysis:
        """Create error analysis for unknown error types."""
        description = "Unknown error occurred during execution"

        if stderr_analysis.context_lines:
            description += f". Check stderr output for details."

        suggested_fixes = [
            "Review complete stderr output for error details",
            "Check tamarin-prover version compatibility",
            "Verify theory file is valid",
            "Try running with increased verbosity",
        ]

        return ErrorAnalysis(
            error_type=ErrorType.SYSTEM_ERROR,  # Default to system error
            description=description,
            context_lines=stderr_analysis.context_lines,
            suggested_fixes=suggested_fixes,
        )

    def _generate_error_description(
        self, error_type: ErrorType, stderr_analysis: StderrAnalysis
    ) -> str:
        """Generate human-readable error description."""
        base_descriptions = {
            ErrorType.MEMORY_EXHAUSTED: "Task ran out of available memory during execution",
            ErrorType.TIMEOUT: "Task exceeded its timeout limit",
            ErrorType.SYNTAX_ERROR: "Syntax error in the theory file",
            ErrorType.SYSTEM_ERROR: "System-level error occurred",
            ErrorType.PROOF_FAILURE: "Proof could not be completed",
        }

        description = base_descriptions.get(error_type, "Unknown error occurred")

        # Add specific details if available
        if stderr_analysis.error_patterns_found:
            pattern_info = ", ".join(
                stderr_analysis.error_patterns_found[:2]
            )  # Limit to 2 patterns
            description += f". Detected: {pattern_info}"

        return description

    def _generate_suggested_fixes(
        self, error_type: ErrorType, failure_context: FailureContext
    ) -> List[str]:
        """Generate specific suggested fixes based on error type and context."""
        base_fixes = self.ERROR_FIXES.get(error_type, {}).get("suggested_actions", [])
        suggested_fixes = base_fixes.copy()

        # Add context-specific suggestions
        if failure_context.last_successful_lemma:
            suggested_fixes.append(
                f"Issue occurred after lemma '{failure_context.last_successful_lemma}'. "
                f"Consider targeting subsequent lemmas individually."
            )

        if failure_context.theory_name and failure_context.theory_name != "Unknown":
            suggested_fixes.append(
                f"Review the '{failure_context.theory_name}' theory specification."
            )

        if (
            error_type == ErrorType.MEMORY_EXHAUSTED
            and failure_context.partial_lemma_results
        ):
            successful_count = len(
                [
                    r
                    for r in failure_context.partial_lemma_results.values()
                    if r.status == "verified"
                ]
            )
            if successful_count > 0:
                suggested_fixes.append(
                    f"{successful_count} lemmas were successfully verified before failure. "
                    f"Consider running remaining lemmas separately."
                )

        return suggested_fixes
