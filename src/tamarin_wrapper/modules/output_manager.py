"""
Storage manager for task outputs.

This module handles the storage and retrieval of task outputs.
"""

from pathlib import Path
from typing import Optional, Tuple

from ..utils.notifications import notification_manager


class TaskOutputManager:
    """Handles storage and retrieval of task outputs."""

    def __init__(self, output_directory: Path, raw_outputs: bool = False):
        """
        Initialize the storage manager.

        Args:
            output_directory: Base directory for storing outputs
            raw_outputs: Whether to create raw outputs directory
        """
        self.output_directory = Path(output_directory)

        # Ensure output directory exists
        self.output_directory.mkdir(parents=True, exist_ok=True)

        # Create subdirectories for organization
        if raw_outputs:
            self.raw_outputs_dir = self.output_directory / "raw_outputs"
        self.processed_dir = self.output_directory / "processed"
        self.tamarin_output_models = self.output_directory / "tamarin_output_models"

        for directory in [
            self.processed_dir,
            self.tamarin_output_models,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

        if raw_outputs:
            self.raw_outputs_dir.mkdir(parents=True, exist_ok=True)

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
