"""
Cache manager for Batch Tamarin using diskcache for persistent storage.

This module provides caching functionality to avoid re-executing identical
Tamarin tasks. Uses file content hashing and task parameters to generate
unique cache keys.
"""

import hashlib
from pathlib import Path
from typing import Optional

from diskcache import Cache

from ..model.executable_task import ExecutableTask, TaskResult


class CacheManager:
    """Manages persistent caching of Tamarin task results."""

    def __init__(self) -> None:
        """Initialize cache manager with user-specific cache directory."""
        cache_dir = Path.home() / ".batch-tamarin" / "cache"
        self.cache: Cache = Cache(str(cache_dir), size_limit=int(2e9))  # 2GB limit

    def get_cached_result(self, task: ExecutableTask) -> Optional[TaskResult]:
        """
        Retrieve cached result for a task if available.

        Args:
            task: ExecutableTask to check cache for

        Returns:
            TaskResult if cache hit, None if cache miss
        """
        key = self._generate_key(task)
        # Type ignore for diskcache complex return type - we know we stored TaskResult objects
        return self.cache.get(key)  # type: ignore[return-value]

    def store_result(self, task: ExecutableTask, result: TaskResult) -> None:
        """
        Store successful task result in cache.

        Args:
            task: ExecutableTask that was executed
            result: TaskResult to cache
        """
        key = self._generate_key(task)
        self.cache[key] = result

    def clear_cache(self) -> None:
        """Clear all cached results."""
        self.cache.clear()

    def get_stats(self) -> dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache size and volume information
        """
        # Type ignore for diskcache inconsistent type annotations
        cache_size: int = len(self.cache)  # type: ignore[assignment]
        cache_volume: int = self.cache.volume()  # type: ignore[assignment]
        return {"size": cache_size, "volume": cache_volume}

    def _generate_key(self, task: ExecutableTask) -> str:
        """
        Generate unique cache key for a task.

        Args:
            task: ExecutableTask to generate key for

        Returns:
            SHA256 hash string representing the task
        """
        # Fast file hashing with chunked reading
        hasher = hashlib.sha256()
        with open(task.theory_file, "rb") as f:
            while chunk := f.read(65536):  # 64KB chunks for speed
                hasher.update(chunk)
        theory_hash = hasher.hexdigest()

        # Hash executable info (cross-platform compatible)
        exe_stat = task.tamarin_executable.stat()
        exe_info = f"{task.tamarin_executable}_{exe_stat.st_mtime}_{exe_stat.st_size}"
        exe_hash = hashlib.sha256(exe_info.encode()).hexdigest()

        # Combine all relevant fields
        key_data = "|".join(
            [
                theory_hash,
                exe_hash,
                str(task.lemma),
                ",".join(sorted(task.tamarin_options or [])),
                ",".join(sorted(task.preprocess_flags or [])),
                str(task.max_cores),
                str(task.max_memory),
                str(task.task_timeout),
            ]
        )

        return hashlib.sha256(key_data.encode()).hexdigest()
