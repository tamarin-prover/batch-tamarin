"""
Generator for failed task result JSON files.

This module creates structured JSON output files for failed Tamarin
execution results with error analysis and suggestions.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ...model.executable_task import TaskResult
from ...model.output_models import (
    ErrorAnalysis,
    FailedTaskResult,
    FailureContext,
    RawOutputSummary,
    TaskModifications,
)


class FailedTaskGenerator:
    """
    Generates structured JSON files for failed task results.
    """

    def generate_failed_result_file(
        self,
        task_result: TaskResult,
        error_analysis: ErrorAnalysis,
        suggested_modifications: TaskModifications,
        failure_context: FailureContext,
        output_path: Path,
    ) -> Path:
        """
        Generate a failed task result JSON file.

        Args:
            task_result: Original task result with failure information
            error_analysis: Analysis of the error
            suggested_modifications: Suggested modifications for retry
            failure_context: Additional context about the failure
            output_path: Path where to write the result file

        Returns:
            Path to the generated file
        """
        # Create raw output summary
        raw_outputs = self._create_raw_output_summary(task_result)

        # Create the failed task result
        failed_result = FailedTaskResult(
            task_id=task_result.task_id,
            error_analysis=error_analysis,
            suggested_modifications=suggested_modifications,
            raw_outputs=raw_outputs,
            context_info=failure_context,
            timestamp=datetime.now(),
        )

        # Convert to JSON-serializable format
        result_data = self._convert_to_json_format(failed_result, task_result)

        # Write to file
        output_path.write_text(
            json.dumps(result_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        return output_path

    def _create_raw_output_summary(self, task_result: TaskResult) -> RawOutputSummary:
        """
        Create a summary of raw outputs from task result.

        Args:
            task_result: Task result containing stdout/stderr

        Returns:
            RawOutputSummary with key information
        """
        # Get last few lines of stdout and stderr
        stdout_lines = (
            task_result.stdout.strip().split("\n") if task_result.stdout else []
        )
        stderr_lines = (
            task_result.stderr.strip().split("\n") if task_result.stderr else []
        )

        # Take last 10 lines for context
        last_stdout = stdout_lines[-10:] if len(stdout_lines) > 10 else stdout_lines
        last_stderr = stderr_lines[-10:] if len(stderr_lines) > 10 else stderr_lines

        return RawOutputSummary(
            last_stdout_lines=last_stdout,
            last_stderr_lines=last_stderr,
            stdout_length=len(task_result.stdout) if task_result.stdout else 0,
            stderr_length=len(task_result.stderr) if task_result.stderr else 0,
        )

    def _convert_to_json_format(
        self, failed_result: FailedTaskResult, task_result: TaskResult
    ) -> dict[str, Any]:
        """
        Convert FailedTaskResult to JSON-serializable format.

        Args:
            failed_result: FailedTaskResult to convert
            task_result: Original task result for additional info

        Returns:
            Dictionary ready for JSON serialization
        """
        # Calculate resource usage
        resource_usage: dict[str, Any] = {
            "peak_memory_mb": None,  # Would be filled by process manager if available
            "execution_time_s": (
                task_result.duration if hasattr(task_result, "duration") else None
            ),
        }

        # Add memory stats if available
        if task_result.memory_stats:
            resource_usage["peak_memory_mb"] = task_result.memory_stats.peak_memory_mb
            resource_usage["average_memory_mb"] = task_result.memory_stats.avg_memory_mb

        return {
            "task_id": failed_result.task_id,
            "return_code": task_result.return_code,
            "error": {
                "error_type": failed_result.error_analysis.error_type.value,
                "description": failed_result.error_analysis.description,
                "last_stderr_lines": failed_result.raw_outputs.last_stderr_lines,
                "suggested_fixes": failed_result.error_analysis.suggested_fixes,
            },
            "resource_usage": resource_usage,
            "failure_context": {
                "theory_name": failed_result.context_info.theory_name,
                "last_successful_lemma": failed_result.context_info.last_successful_lemma,
                "failure_point": failed_result.context_info.failure_point,
                "partial_results_count": len(
                    failed_result.context_info.partial_lemma_results
                ),
            },
            "suggested_modifications": {
                "timeout_multiplier": failed_result.suggested_modifications.timeout_multiplier,
                "memory_limit_gb": failed_result.suggested_modifications.memory_limit_gb,
                "additional_args": failed_result.suggested_modifications.additional_args,
            },
            "raw_output_summary": {
                "stdout_length": failed_result.raw_outputs.stdout_length,
                "stderr_length": failed_result.raw_outputs.stderr_length,
                # Only last 5 for JSON
                "last_stdout_lines": failed_result.raw_outputs.last_stdout_lines[-5:],
                # Only last 5 for JSON
                "last_stderr_lines": failed_result.raw_outputs.last_stderr_lines[-5:],
            },
            "timestamp": failed_result.timestamp.isoformat(),
        }

    def generate_failure_summary(
        self, failed_results: list[FailedTaskResult], output_path: Path
    ) -> Path:
        """
        Generate a summary file for multiple failed results.

        Args:
            failed_results: List of failed task results
            output_path: Path where to write the summary file

        Returns:
            Path to the generated summary file
        """
        if not failed_results:
            summary_data: dict[str, Any] = {
                "total_failed_tasks": 0,
                "error_patterns": {},
                "timestamp": datetime.now().isoformat(),
            }
        else:
            # Analyze error patterns
            error_counts: dict[str, int] = {}
            for result in failed_results:
                error_type = result.error_analysis.error_type.value
                error_counts[error_type] = error_counts.get(error_type, 0) + 1

            # Generate recommendations
            common_recommendations = self._generate_common_recommendations(
                failed_results
            )

            summary_data = {
                "total_failed_tasks": len(failed_results),
                "error_patterns": error_counts,
                "most_common_error": (
                    max(error_counts.items(), key=lambda x: x[1])[0]
                    if error_counts
                    else None
                ),
                "common_recommendations": common_recommendations,
                "failed_tasks": [
                    {
                        "task_id": r.task_id,
                        "error_type": r.error_analysis.error_type.value,
                        "theory_name": r.context_info.theory_name,
                        "description": r.error_analysis.description,
                    }
                    for r in failed_results
                ],
                "timestamp": datetime.now().isoformat(),
            }

        # Write summary to file
        output_path.write_text(
            json.dumps(summary_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        return output_path

    def _generate_common_recommendations(
        self, failed_results: list[FailedTaskResult]
    ) -> list[str]:
        """
        Generate common recommendations across all failures.

        Args:
            failed_results: List of failed task results

        Returns:
            List of common recommendations
        """
        recommendations: list[str] = []

        # Count error types
        error_counts: dict[str, int] = {}
        for result in failed_results:
            error_type = result.error_analysis.error_type.value
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

        total_failures = len(failed_results)

        # Memory issues
        if error_counts.get("memory", 0) > total_failures * 0.3:
            recommendations.append(
                "Multiple memory exhaustion failures detected. "
                "Consider increasing default memory limits in recipe configuration."
            )

        # Timeout issues
        if error_counts.get("timeout", 0) > total_failures * 0.3:
            recommendations.append(
                "Multiple timeout failures detected. "
                "Consider increasing default timeout values or using proof heuristics."
            )

        # Syntax errors
        if error_counts.get("syntax", 0) > 0:
            recommendations.append(
                "Syntax errors detected. "
                "Review theory files for formatting and syntax issues."
            )

        # System errors
        if error_counts.get("system", 0) > 0:
            recommendations.append(
                "System errors detected. "
                "Check file permissions, disk space, and tamarin-prover installation."
            )

        # General recommendation if many failures
        if total_failures > 5:
            recommendations.append(
                "High number of failures detected. "
                "Consider reviewing theory complexity and breaking down into smaller tasks."
            )

        return recommendations
