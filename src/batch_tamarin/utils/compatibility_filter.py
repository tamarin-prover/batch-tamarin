"""
Compatibility filter for Tamarin options based on version.

This module provides utilities to filter Tamarin command-line options
based on the version of the Tamarin executable being used.
"""

import re
from pathlib import Path
from typing import List

from ..modules.tamarin_test_cmd import extract_tamarin_version


def parse_version(version_str: str) -> tuple[int, int, int]:
    """
    Parse a version string into major, minor, patch components.

    Args:
        version_str: Version string in format "vX.X.X" or "X.X.X"

    Returns:
        Tuple of (major, minor, patch) integers

    Raises:
        ValueError: If version string cannot be parsed
    """
    # Remove 'v' prefix if present
    clean_version = version_str.lstrip("v")

    # Extract version components
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", clean_version)
    if not match:
        raise ValueError(f"Invalid version format: {version_str}")

    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def is_version_greater_than(
    version_str: str, target_major: int, target_minor: int, target_patch: int = 0
) -> bool:
    """
    Check if a version string represents a version greater than or equal to the target.

    Args:
        version_str: Version string to check
        target_major: Target major version
        target_minor: Target minor version
        target_patch: Target patch version (default: 0)

    Returns:
        True if version is greater than or equal to target, False otherwise
    """
    try:
        major, minor, patch = parse_version(version_str)

        if major > target_major:
            return True
        elif major == target_major:
            if minor > target_minor:
                return True
            elif minor == target_minor:
                return patch >= target_patch

        return False
    except ValueError:
        # If we can't parse the version, assume it's not greater or equal
        return False


async def compatibility_filter(
    command: List[str], tamarin_executable: Path
) -> List[str]:
    """
    Filter Tamarin command options based on version compatibility.

    This function removes options that are not supported by the given
    Tamarin version to prevent command failures.

    Args:
        command: List of command arguments
        tamarin_executable: Path to the Tamarin executable

    Returns:
        Filtered command list with incompatible options removed
    """
    # Extract version from the executable
    version_str = await extract_tamarin_version(tamarin_executable)

    if not version_str:
        # If we can't determine the version, return command as-is
        return command

    filtered_command: list[str] = []

    for arg in command:
        # Filter --output-json for versions <= 1.10
        if arg.startswith("--output-json="):
            if is_version_greater_than(version_str, 1, 10):
                filtered_command.append(arg)
            # Skip this argument for versions <= 1.10
            continue

        # Filter --output-dot for versions <= 1.10
        if arg.startswith("--output-dot="):
            if is_version_greater_than(version_str, 1, 10):
                filtered_command.append(arg)
            # Skip this argument for versions <= 1.10
            continue

        # Add other version-specific filters here in the future
        # Example:
        # if arg.startswith('--some-new-option='):
        #     if is_version_greater_than(version_str, 1, 15):
        #         filtered_command.append(arg)
        #     continue

        # Keep all other arguments
        filtered_command.append(arg)

    return filtered_command
