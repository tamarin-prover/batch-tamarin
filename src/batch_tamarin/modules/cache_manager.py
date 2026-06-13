"""
Cache manager for Batch Tamarin using diskcache for persistent storage.

This module provides caching functionality to avoid re-executing identical
Tamarin tasks. Uses file content hashing and task parameters to generate
unique cache keys.
"""

import hashlib
from pathlib import Path

import typer
from diskcache import Cache

from ..model.executable_task import ExecutableTask, TaskResult, TaskStatus
from ..utils.notifications import notification_manager
from ..utils.system_resources import get_human_readable_volume_size


class CachedTaskData:
    """Container for cached task data including result and files."""

    def __init__(self, task_result: TaskResult, files: dict[str, bytes]):
        """
        Initialize cached task data.

        Args:
            task_result: The TaskResult object
            files: Dictionary mapping relative file paths to their content
        """
        self.task_result = task_result
        self.files = files


class CacheManager:
    """Manages persistent caching of Tamarin task results."""

    CACHE_SIZE_LIMIT: int = int(2e9)  # 2GB limit

    @staticmethod
    def get_cache_dir() -> Path:
        return Path.home() / ".batch-tamarin" / "cache"

    @staticmethod
    def _get_directory_size(path: Path) -> int:
        """Recursively calculate the total size of all files in a directory.

        Args:
            path: Directory to measure

        Returns:
            Total size in bytes of all regular files under the directory
        """
        return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())

    def __init__(self) -> None:
        """Initialize cache manager with user-specific cache directory."""

        cache_dir = self.get_cache_dir()
        if (
            cache_dir.exists()
            and self._get_directory_size(cache_dir) > self.CACHE_SIZE_LIMIT
        ):
            current_size = get_human_readable_volume_size(
                self._get_directory_size(cache_dir)
            )
            limit_size = get_human_readable_volume_size(self.CACHE_SIZE_LIMIT)
            print(
                f"The maximum cache size has been exceeded "
                f"({current_size} / {limit_size}), "
                f"use `batch-tamarin cache prune` to clear it!"
            )
            raise typer.Exit(1)

        self.cache: Cache = Cache(str(cache_dir), size_limit=self.CACHE_SIZE_LIMIT)

    def get_cached_result(self, task: ExecutableTask) -> TaskResult | None:
        """
        Retrieve cached result for a task if available and recreate associated files.

        Args:
            task: ExecutableTask to check cache for

        Returns:
            TaskResult if cache hit, None if cache miss
        """
        key = self._generate_key(task)
        cached_data: CachedTaskData | None = self.cache.get(key)

        if cached_data is None:
            return None

        # For backward compatibility, handle old TaskResult objects
        if isinstance(cached_data, TaskResult):
            notification_manager.debug(
                "[CacheManager] Found legacy cache entry without files"
            )
            return cached_data

        # Recreate files from cache
        self._restore_cached_files(task, cached_data.files)

        return cached_data.task_result

    def store_result(self, task: ExecutableTask, result: TaskResult) -> None:
        """
        Store successful task result in cache along with generated files.

        Args:
            task: ExecutableTask that was executed
            result: TaskResult to cache
        """
        key = self._generate_key(task)

        # Collect files to cache
        files_to_cache = self._collect_task_files(task)

        # Create cached data container
        cached_data = CachedTaskData(result, files_to_cache)

        # Store in cache
        self.cache[key] = cached_data

    def clear_cache(self, errors_only: bool = False) -> None:
        """
        Clear all cached results.

        Args:
            errors_only (bool, optional): Clear only failed/error tasks. Defaults to False.
        """

        if not errors_only:
            self.cache.clear()
        else:
            for key in self.cache:
                value = self.cache.get(key)
                if value.task_result.status in [
                    TaskStatus.FAILED,
                    TaskStatus.SIGNAL_INTERRUPTED,
                    TaskStatus.MEMORY_LIMIT_EXCEEDED,
                    TaskStatus.TIMEOUT,
                ]:
                    self._delete_cache_entry(key)

    def _delete_cache_entry(self, key: str) -> None:
        """
        Deletes a single cache entry by key.

        Args:
            key (str): The key of the entry to delete
        """

        self.cache.delete(key=key)

    def get_stats(self) -> dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache size and volume information
        """
        # Type ignore for diskcache inconsistent type annotations
        cache_size: int = len(self.cache)
        cache_volume: int = self.cache.volume()
        return {"size": cache_size, "volume": cache_volume}

    def _collect_task_files(self, task: ExecutableTask) -> dict[str, bytes]:
        """
        Collect all files generated by a task for caching.

        Args:
            task: ExecutableTask that generated the files

        Returns:
            Dictionary mapping relative file paths to their content
        """
        files_to_cache: dict[str, bytes] = {}

        try:
            # Collect proof file (.spthy output file)
            if task.output_file.exists():
                files_to_cache[f"proofs/{task.output_file.name}"] = (
                    task.output_file.read_bytes()
                )
                notification_manager.debug(
                    f"[CacheManager] Cached proof file: {task.output_file}"
                )

            # Collect trace files
            trace_json_file = task.traces_dir / f"{task.task_name}.json"
            if trace_json_file.exists():
                files_to_cache[f"traces/{trace_json_file.name}"] = (
                    trace_json_file.read_bytes()
                )
                notification_manager.debug(
                    f"[CacheManager] Cached trace JSON file: {trace_json_file}"
                )

            trace_dot_file = task.traces_dir / f"{task.task_name}.dot"
            if trace_dot_file.exists():
                files_to_cache[f"traces/{trace_dot_file.name}"] = (
                    trace_dot_file.read_bytes()
                )
                notification_manager.debug(
                    f"[CacheManager] Cached trace DOT file: {trace_dot_file}"
                )

            # Also check for SVG files that might have been generated
            trace_svg_file = task.traces_dir / f"{task.task_name}.svg"
            if trace_svg_file.exists():
                files_to_cache[f"traces/{trace_svg_file.name}"] = (
                    trace_svg_file.read_bytes()
                )
                notification_manager.debug(
                    f"[CacheManager] Cached trace SVG file: {trace_svg_file}"
                )

        except Exception as e:
            notification_manager.error(
                f"[CacheManager] Failed to collect files for task {task.task_name}: {e}"
            )

        return files_to_cache

    def _restore_cached_files(
        self, task: ExecutableTask, cached_files: dict[str, bytes]
    ) -> None:
        """
        Restore cached files to the filesystem.

        Args:
            task: ExecutableTask for context about where files should be placed
            cached_files: Dictionary mapping relative file paths to their content
        """
        try:
            for relative_path, content in cached_files.items():
                if relative_path.startswith("proofs/"):
                    # Restore proof file - use task.output_file as destination
                    target_file = task.output_file
                elif relative_path.startswith("traces/"):
                    # Restore trace files to task traces directory
                    filename = Path(relative_path).name
                    target_file = task.traces_dir / filename
                else:
                    notification_manager.warning(
                        f"[CacheManager] Unknown cached file path: {relative_path}"
                    )
                    continue

                # Ensure parent directory exists
                target_file.parent.mkdir(parents=True, exist_ok=True)

                # Write file content
                target_file.write_bytes(content)

                notification_manager.debug(
                    f"[CacheManager] Restored cached file: {target_file}"
                )

        except Exception as e:
            notification_manager.error(
                f"[CacheManager] Failed to restore cached files for task {task.task_name}: {e}"
            )

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
        exe_stat = Path(task.tamarin_executable).stat()
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
