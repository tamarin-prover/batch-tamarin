"""
System resource detection utilities for Tamarin Wrapper.

This module provides functions to detect maximum system resources (CPU cores and memory)
that can be used when "max" is specified in configuration files.
"""

import os

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
        memory_bytes = psutil.virtual_memory().total
        memory_gb = int(memory_bytes / (1024**3))
        if memory_gb <= 0:
            return 1
        return memory_gb
    except Exception:
        return 1


def resolve_max_value(value: str | int, resource_type: str) -> int:
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

    if isinstance(value, str) and value.lower() == "max":
        if resource_type.lower() == "cores":
            return get_max_cpu_cores()
        elif resource_type.lower() == "memory":
            return get_max_memory_gb()
        else:
            raise ValueError(
                f"Unknown resource type: {resource_type}. Must be 'cores' or 'memory'"
            )

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
