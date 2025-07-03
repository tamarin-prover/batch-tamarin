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
    executable_tasks: List["ExecutableTask"],
) -> Dict[str, List[str]]:
    """
    Validate theory files with tamarin executables.

    Runs tamarin without --prove flags to check for warnings/errors in theory files.
    Groups tasks by unique (tamarin_executable, theory_file) combinations to avoid
    duplicate validation runs.

    Args:
        executable_tasks: List of ExecutableTask objects to validate

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
            errors = parse_tamarin_output(result.stdout + result.stderr)

            if errors or result.returncode != 0:
                validation_errors[task.tamarin_version_name] = errors
                if result.returncode != 0 and not errors:
                    validation_errors[task.tamarin_version_name] = [
                        f"Non-zero exit code: {result.returncode}"
                    ]

        except subprocess.TimeoutExpired:
            validation_errors[task.tamarin_version_name] = [
                "Validation timed out after 60 seconds"
            ]
        except Exception as e:
            validation_errors[task.tamarin_version_name] = [
                f"Validation failed: {str(e)}"
            ]

    return validation_errors


def parse_tamarin_output(output: str) -> List[str]:
    """
    Parse tamarin output to extract warnings and errors.

    Args:
        output: Combined stdout and stderr from tamarin execution

    Returns:
        List of error/warning messages found in the output
    """
    errors: list[str] = []

    for line in output.split("\n"):
        line = line.strip()
        if line and any(
            keyword in line.lower()
            for keyword in ["warning", "error", "fail", "abort", "exception"]
        ):
            # Filter out some common non-error messages
            if not any(
                ignore in line.lower()
                for ignore in ["no warning", "warning: none", "successfully"]
            ):
                errors.append(line)

    return errors
