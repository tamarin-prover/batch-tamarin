"""
Model checking utilities for Tamarin validation.

This module provides functionality to validate theory files with tamarin executables
without running full proofs, to check for warnings and errors.
"""

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List

from .notifications import notification_manager

if TYPE_CHECKING:
    from ..model.executable_task import ExecutableTask


async def validate_with_tamarin(
    executable_tasks: List["ExecutableTask"], report: bool = False
) -> Dict[str, List[str]]:
    """
    Validate theory files with tamarin executables.

    Runs tamarin without --prove flags to check for warnings/errors in theory files.
    Groups tasks by unique (tamarin_executable, theory_file) combinations to avoid
    duplicate validation runs.

    Args:
        executable_tasks: List of ExecutableTask objects to validate
        report: If True, include detailed output in the report

    Returns:
        Dict mapping tamarin version names to lists of error/warning messages
    """
    validation_errors: Dict[str, List[str]] = {}

    # Group tasks by unique (tamarin_executable, theory_file) combinations
    unique_validations: Dict[tuple[str, str], "ExecutableTask"] = {}
    for task in executable_tasks:
        key = (str(task.tamarin_executable), str(task.theory_file))
        if key not in unique_validations:
            unique_validations[key] = task

    for (_, _), task in unique_validations.items():
        try:
            # Run tamarin without any prove flags to check for warnings/errors
            cmd = [str(task.tamarin_executable), str(task.theory_file)]

            notification_manager.debug(f"Running validation: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,  # 1 minute timeout for validation
                cwd=Path.cwd(),
            )

            # Parse output for warnings and errors
            errors = parse_tamarin_output(result.stdout, report, task)

            if errors or result.returncode != 0:
                validation_errors[task.task_name] = errors
                if result.returncode != 0 and not errors:
                    validation_errors[task.task_name] = [
                        f"Non-zero exit code: {result.returncode}"
                    ]

        except subprocess.TimeoutExpired:
            validation_errors[task.task_name] = [
                "Validation timed out after 60 seconds"
            ]
        except Exception as e:
            validation_errors[task.task_name] = [f"Validation failed: {str(e)}"]

    return validation_errors


def parse_tamarin_output(
    output: str, report: bool, task: "ExecutableTask"
) -> List[str]:
    """
    Parse tamarin output to extract warnings and errors.

    Args:
        output: Stdout from tamarin execution
        report: If True, include detailed output in the report and write wellformedness report to file
        task: ExecutableTask containing output file path for determining report directory

    Returns:
        List of error/warning messages found in the output
    """
    errors: List[str] = []

    # Check for WARNING in summary of summaries
    lines = output.split("\n")
    for line in lines:
        if "WARNING:" in line and "wellformedness check failed" in line:
            errors.append(line.strip())

    # Extract detailed wellformedness report if present and report is True
    if report:
        start_marker = "/*\nWARNING: the following wellformedness checks failed!"
        end_marker = "*/"

        start_idx = output.find(start_marker)
        if start_idx != -1:
            # Find the end marker after the start
            end_idx = output.find(end_marker, start_idx + len(start_marker))
            if end_idx != -1:
                wellformedness_report = output[start_idx : end_idx + len(end_marker)]

                # Create the wellformedness-check-report directory if it doesn't exist
                report_dir = (
                    task.output_file.parent.parent / "wellformedness-check-report"
                )
                report_dir.mkdir(parents=True, exist_ok=True)

                # Write to wellformedness-check-report file
                report_file = (
                    task.output_file.parent.parent
                    / "wellformedness-check-report"
                    / f"{task.task_name}.txt"
                )
                try:
                    with open(report_file, "w") as f:
                        f.write(wellformedness_report)
                    notification_manager.debug(
                        f"Wrote wellformedness report to {report_file}"
                    )
                except Exception as e:
                    notification_manager.debug(
                        f"Failed to write wellformedness report: {e}"
                    )

    return errors
