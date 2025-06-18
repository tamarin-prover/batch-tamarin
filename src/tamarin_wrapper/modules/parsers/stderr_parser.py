"""
Stderr parser for Tamarin output error pattern detection.

This module implements regex-based analysis of stderr to categorize
errors and extract relevant context information.
"""

import re
from typing import List, Optional

from ...model.output_models import ErrorType, StderrAnalysis


class StderrParser:
    """
    Advanced stderr analysis with comprehensive error categorization.
    """

    ERROR_PATTERNS = {
        ErrorType.MEMORY_EXHAUSTED: [
            re.compile(r"Heap exhausted", re.IGNORECASE),
            re.compile(r"Current maximum heap size", re.IGNORECASE),
            re.compile(r"out of memory", re.IGNORECASE),
            re.compile(r"Allocation failed", re.IGNORECASE),
            re.compile(r"cannot allocate", re.IGNORECASE),
            re.compile(r"Stack space overflow", re.IGNORECASE),
        ],
        ErrorType.TIMEOUT: [
            re.compile(r"Process timed out", re.IGNORECASE),
            re.compile(r"timeout", re.IGNORECASE),
        ],
        ErrorType.SYNTAX_ERROR: [
            re.compile(r"Parse error", re.IGNORECASE),
            re.compile(r"Syntax error", re.IGNORECASE),
            re.compile(r"malformed", re.IGNORECASE),
            re.compile(r"unexpected token", re.IGNORECASE),
            re.compile(r"parse failed", re.IGNORECASE),
        ],
        ErrorType.SYSTEM_ERROR: [
            re.compile(r"cannot read file", re.IGNORECASE),
            re.compile(r"Permission denied", re.IGNORECASE),
            re.compile(r"Directory not found", re.IGNORECASE),
            re.compile(r"Error writing", re.IGNORECASE),
            re.compile(r"Failed to generate", re.IGNORECASE),
            re.compile(r"No such file", re.IGNORECASE),
            re.compile(r"Access denied", re.IGNORECASE),
        ],
        ErrorType.PROOF_FAILURE: [
            re.compile(r"proof failed", re.IGNORECASE),
            re.compile(r"could not prove", re.IGNORECASE),
            re.compile(r"lemma.*failed", re.IGNORECASE),
        ],
    }

    # Patterns to identify Tamarin debug logs vs actual errors
    DEBUG_LOG_PATTERNS = [
        re.compile(r"^\s*checking.*", re.IGNORECASE),
        re.compile(r"^\s*loading.*", re.IGNORECASE),
        re.compile(r"^\s*analyzing.*", re.IGNORECASE),
        re.compile(r"^\s*\[.*\]", re.IGNORECASE),  # Timestamped logs
    ]

    def analyze(self, stderr: str) -> StderrAnalysis:
        """
        Analyze stderr for error patterns and context.

        Args:
            stderr: Raw stderr string from Tamarin execution

        Returns:
            StderrAnalysis containing categorized error information
        """
        if not stderr.strip():
            return StderrAnalysis(
                error_type=None,
                error_patterns_found=[],
                context_lines=[],
                is_critical_error=False,
                tamarin_logs=[],
            )

        # Detect error type and patterns
        error_type, error_patterns_found = self._detect_error_type(stderr)

        # Extract context lines around errors
        context_lines = self._extract_context_lines(stderr, error_patterns_found)

        # Separate Tamarin logs from actual errors
        tamarin_logs = self._filter_tamarin_logs(stderr)

        # Determine if this is a critical error
        is_critical_error = self._is_critical_error(error_type, stderr)

        return StderrAnalysis(
            error_type=error_type,
            error_patterns_found=error_patterns_found,
            context_lines=context_lines,
            is_critical_error=is_critical_error,
            tamarin_logs=tamarin_logs,
        )

    def _detect_error_type(self, stderr: str) -> tuple[Optional[ErrorType], List[str]]:
        """
        Detect the primary error type and matching patterns.

        Returns:
            Tuple of (error_type, list_of_matched_patterns)
        """
        matched_patterns: List[str] = []
        detected_types: List[ErrorType] = []

        for error_type, patterns in self.ERROR_PATTERNS.items():
            for pattern in patterns:
                matches = pattern.findall(stderr)
                if matches:
                    detected_types.append(error_type)
                    matched_patterns.extend(matches)

        # Prioritize error types (memory and timeout are most critical)
        if ErrorType.MEMORY_EXHAUSTED in detected_types:
            primary_error = ErrorType.MEMORY_EXHAUSTED
        elif ErrorType.TIMEOUT in detected_types:
            primary_error = ErrorType.TIMEOUT
        elif ErrorType.SYNTAX_ERROR in detected_types:
            primary_error = ErrorType.SYNTAX_ERROR
        elif ErrorType.SYSTEM_ERROR in detected_types:
            primary_error = ErrorType.SYSTEM_ERROR
        elif ErrorType.PROOF_FAILURE in detected_types:
            primary_error = ErrorType.PROOF_FAILURE
        else:
            primary_error = None

        return primary_error, matched_patterns

    def _extract_context_lines(
        self, stderr: str, error_patterns: List[str]
    ) -> List[str]:
        """
        Extract relevant context lines around errors.

        Args:
            stderr: The stderr content
            error_patterns: List of matched error pattern strings

        Returns:
            List of context lines around errors
        """
        if not error_patterns:
            # If no specific patterns, return last few lines of stderr
            lines = stderr.strip().split("\n")
            return lines[-5:] if len(lines) > 5 else lines

        context_lines: List[str] = []
        lines = stderr.split("\n")

        for i, line in enumerate(lines):
            # Check if this line contains any error pattern
            line_has_error = any(
                pattern.lower() in line.lower() for pattern in error_patterns
            )

            if line_has_error:
                # Add context: 2 lines before and after the error
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                context_lines.extend(lines[start:end])

        # Remove duplicates while preserving order
        seen: set[str] = set()
        unique_context: List[str] = []
        for line in context_lines:
            if line not in seen:
                seen.add(line)
                unique_context.append(line)

        return unique_context

    def _filter_tamarin_logs(self, stderr: str) -> List[str]:
        """
        Separate Tamarin debug logs from actual errors.

        Args:
            stderr: The stderr content

        Returns:
            List of lines that appear to be debug/info logs
        """
        logs: List[str] = []
        lines = stderr.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line matches debug log patterns
            is_debug_log = any(
                pattern.match(line) for pattern in self.DEBUG_LOG_PATTERNS
            )

            if is_debug_log:
                logs.append(line)

        return logs

    def _is_critical_error(self, error_type: Optional[ErrorType], stderr: str) -> bool:
        """
        Determine if the detected error is critical and prevents execution.

        Args:
            error_type: The detected error type
            stderr: The stderr content

        Returns:
            True if this is a critical error
        """
        if error_type is None:
            return False

        # Memory exhaustion and system errors are always critical
        if error_type in [ErrorType.MEMORY_EXHAUSTED, ErrorType.SYSTEM_ERROR]:
            return True

        # Syntax errors are critical
        if error_type == ErrorType.SYNTAX_ERROR:
            return True

        # Timeout might not be critical (could be a partial result)
        if error_type == ErrorType.TIMEOUT:
            return False

        # Proof failures are not critical (expected in some cases)
        if error_type == ErrorType.PROOF_FAILURE:
            return False

        return False
