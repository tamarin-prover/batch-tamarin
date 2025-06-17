"""
Storage manager for task outputs.

This module handles the storage and retrieval of task outputs.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..model.executable_task import TaskResult
from ..utils.notifications import notification_manager


class TaskOutputManager:
    """Handles storage and retrieval of task outputs."""

    def __init__(self, output_directory: Path):
        """
        Initialize the storage manager.

        Args:
            output_directory: Base directory for storing outputs
        """
        self.output_directory = Path(output_directory)

        # Ensure output directory exists
        self.output_directory.mkdir(parents=True, exist_ok=True)

        # Create subdirectories for organization
        self.raw_outputs_dir = self.output_directory / "raw_outputs"
        self.failed_tasks_dir = self.output_directory / "failed_tasks"
        self.processed_dir = self.output_directory / "processed"
        self.tamarin_output_models = self.output_directory / "tamarin_output_models"

        for directory in [
            self.raw_outputs_dir,
            self.failed_tasks_dir,
            self.processed_dir,
            self.tamarin_output_models,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def store_raw_output(
        self,
        task_id: str,
        stdout: str,
        stderr: str,
    ) -> Tuple[Optional[Path], Optional[Path]]:
        """
        Store raw output from a task execution.

        Args:
            task_id: Unique identifier for the task
            stdout: Standard output from the task
            stderr: Standard error from the task

        Returns:
            Tuple of (stdout_file_path, stderr_file_path)
        """
        stdout_path = None
        stderr_path = None

        try:
            # Store stdout if not empty
            if stdout.strip():
                stdout_filename = f"stdout_{task_id}.txt"
                stdout_path = self.raw_outputs_dir / stdout_filename
                stdout_path.write_text(stdout, encoding="utf-8")
                notification_manager.debug(
                    f"[StorageManager] Stored stdout for {task_id}: {stdout_path}"
                )

            # Store stderr if not empty
            if stderr.strip():
                stderr_filename = f"stderr_{task_id}.txt"
                stderr_path = self.raw_outputs_dir / stderr_filename
                stderr_path.write_text(stderr, encoding="utf-8")
                notification_manager.debug(
                    f"[StorageManager] Stored stderr for {task_id}: {stderr_path}"
                )

            return stdout_path, stderr_path

        except Exception as e:
            notification_manager.error(
                f"[StorageManager] Failed to store output for {task_id}: {e}"
            )
            raise

    def store_failed_task(self, task_id: str, task_result: TaskResult) -> Path:
        """
        Store information about a failed task.

        Args:
            task_id: Unique identifier for the task
            task_result: TaskResult containing failure information

        Returns:
            Path to the stored failed task file
        """
        filename = f"failed_{task_id}.json"
        failed_path = self.failed_tasks_dir / filename

        # Create a comprehensive failure record
        failure_data: Dict[str, Any] = {
            "task_id": task_id,
            "status": task_result.status.value,
            "return_code": task_result.return_code,
            "stderr": task_result.stderr,
            "stdout": task_result.stdout,
            "start_time": task_result.start_time,
            "end_time": task_result.end_time,
            "duration": task_result.duration,
            "memory_stats": (
                {
                    "peak_memory_mb": task_result.memory_stats.peak_memory_mb,
                    "avg_memory_mb": task_result.memory_stats.avg_memory_mb,
                }
                if task_result.memory_stats
                else None
            ),
        }

        try:
            with open(failed_path, "w", encoding="utf-8") as f:
                json.dump(failure_data, f, indent=2)

            notification_manager.debug(
                f"[StorageManager] Stored failed task info: {failed_path}"
            )
            return failed_path

        except Exception as e:
            notification_manager.error(
                f"[StorageManager] Failed to store failed task info for {task_id}: {e}"
            )
            raise

    def get_tamarin_output_content(self, task_id: str) -> Optional[str]:
        """
        Get the Tamarin output content for a task.

        This is the main method we use to read Tamarin output for processing.

        Args:
            task_id: Unique identifier for the task

        Returns:
            Tamarin output content as string, or None if not found
        """
        tamarin_files = list(self.tamarin_output_models.glob(f"tam_{task_id}.spthy"))

        if not tamarin_files:
            notification_manager.debug(
                f"[StorageManager] No Tamarin output found for task {task_id}"
            )
            return None

        if len(tamarin_files) > 1:
            notification_manager.warning(
                f"[StorageManager] Multiple Tamarin output files found for {task_id}, using most recent"
            )

        tamarin_file = max(tamarin_files, key=lambda p: p.stat().st_mtime)

        try:
            return tamarin_file.read_text(encoding="utf-8")
        except Exception as e:
            notification_manager.error(
                f"[StorageManager] Failed to read Tamarin output for {task_id}: {e}"
            )
            return None

    def list_failed_tasks(self) -> list[Path]:
        """
        List all stored failed task files.

        Returns:
            List of paths to failed task JSON files
        """
        return list(self.failed_tasks_dir.glob("failed_*.json"))
