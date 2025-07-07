"""
System resource detection utilities for batch Tamarin.

This module provides functions to detect maximum system resources (CPU cores and memory)
that can be used when "max" is specified in configuration files.
"""

import os
import shutil
from pathlib import Path

import psutil


def get_max_cpu_cores() -> int:
    """
    Get the maximum number of CPU cores available on the system.

    Returns:
        Number of CPU cores available. Defaults to 1 if detection fails.

    Note:
        Uses os.cpu_count() which returns the number of logical CPUs.
        Falls back to 1 core if detection fails to ensure safe operation.
    """
    try:
        cores = os.cpu_count()
        if cores is None or cores <= 0:
            return 1
        return cores
    except Exception:
        return 1


def get_max_memory_gb() -> int:
    """
    Get the maximum amount of system memory available in GB.

    Returns:
        Total system memory in GB (rounded down). Defaults to 1GB if detection fails.

    Note:
        Uses psutil.virtual_memory() to get total system memory.
        Falls back to 1GB if detection fails to ensure safe operation.
    """
    try:
        memory_bytes = psutil.virtual_memory().total  # type: ignore
        memory_gb = int(memory_bytes / (1024**3))  # type: ignore
        if memory_gb <= 0:
            return 1
        return memory_gb
    except Exception:
        return 1


def resolve_resource_value(value: str | int, resource_type: str) -> int:
    """
    Resolve a "max" string or integer value to actual system maximum.

    Args:
        value: Either an integer or the string "max"
        resource_type: Type of resource ("cores" or "memory") for appropriate detection

    Returns:
        Integer value representing the resolved resource amount

    Raises:
        ValueError: If resource_type is not "cores" or "memory"
        TypeError: If value is neither int nor "max" string
    """
    if isinstance(value, int):
        return value

    elif value.lower() == "max":
        if resource_type.lower() == "cores":
            return get_max_cpu_cores()
        elif resource_type.lower() == "memory":
            return get_max_memory_gb()
        else:
            raise ValueError(
                f"Unknown resource type: {resource_type}. Must be 'cores' or 'memory'"
            )

    elif value.endswith("%"):
        percentage = int(value[:-1])
        if resource_type.lower() == "cores":
            raise ValueError(
                "Percentage values are not supported for CPU cores. Use 'max' or an integer."
            )
        elif resource_type.lower() == "memory":
            max_memory = get_max_memory_gb()
            memory = max(1, min(max_memory, int(max_memory * percentage / 100)))
            return memory

    raise TypeError(
        f"Value must be an integer or 'max', got {type(value).__name__}: {value}"
    )


def get_system_info() -> dict[str, int]:
    """
    Get comprehensive system resource information.

    Returns:
        Dictionary containing system resource information with keys:
        - 'max_cores': Maximum CPU cores available
        - 'max_memory_gb': Maximum memory in GB available
    """
    return {"max_cores": get_max_cpu_cores(), "max_memory_gb": get_max_memory_gb()}


def resolve_executable_path(path_or_command: str) -> Path:
    """
    Resolve an executable path, handling both file paths and bare commands.

    Args:
        path_or_command: Either a file path (absolute/relative) or a command name

    Returns:
        Resolved Path object to the executable

    Raises:
        FileNotFoundError: If the path/command cannot be resolved
        ValueError: If the resolved path is not a file
    """
    # If it looks like a path (contains / or \), treat it as a file path
    if "/" in path_or_command or "\\" in path_or_command:
        resolved_path = Path(path_or_command)
        if not resolved_path.exists():
            raise FileNotFoundError(f"Executable file not found: {resolved_path}")
        if not resolved_path.is_file():
            raise ValueError(f"Path is not a file: {resolved_path}")
        return resolved_path

    # Otherwise, try to resolve as a command in PATH
    resolved_command = shutil.which(path_or_command)
    if resolved_command is None:
        raise FileNotFoundError(f"Command '{path_or_command}' not found in PATH")

    return Path(resolved_command)
