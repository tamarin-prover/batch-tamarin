"""
Output manager for the Tamarin Wrapper.

This module provides functionality to parse Tamarin execution output,
create structured JSON results, and manage output directories.
Uses singleton pattern for global access.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from ..model.executable_task import MemoryStats, TaskResult, TaskStatus
from ..utils.notifications import notification_manager


class WrapperMeasures(BaseModel):
    """Wrapper measurement data."""

    time: float = Field(..., description="Execution time in seconds")
    avg_memory: float = Field(..., description="Average memory usage in MB")
    peak_memory: float = Field(..., description="Peak memory usage in MB")


class LemmaResult(BaseModel):
    """Result for a single lemma."""

    steps: int = Field(..., description="Number of analysis steps")
    analysis_type: str = Field(
        ..., description="Type of analysis (all-traces, exists-trace)"
    )


class SuccessfulTaskResult(BaseModel):
    """Result structure for successful tasks."""

    task_id: str = Field(..., description="Unique task identifier")
    warnings: List[str] = Field(
        default_factory=list, description="Warning messages from Tamarin"
    )
    tamarin_timing: float = Field(
        ..., description="Tamarin reported processing time in seconds"
    )
    wrapper_measures: WrapperMeasures = Field(
        ..., description="Wrapper performance measurements"
    )
    output_spthy: str = Field(..., description="Path to the generated model file")
    verified_lemma: Dict[str, LemmaResult] = Field(
        default_factory=dict, description="Successfully verified lemmas"
    )
    falsified_lemma: Dict[str, LemmaResult] = Field(
        default_factory=dict, description="Falsified lemmas (counterexamples found)"
    )
    unterminated_lemma: List[str] = Field(
        default_factory=list, description="Lemmas with incomplete analysis"
    )

    class Config:
        json_encoders = {Path: str}


class FailedTaskResult(BaseModel):
    """Result structure for failed tasks."""

    task_id: str = Field(..., description="Unique task identifier")
    error_description: str = Field(
        ..., description="Error description (maybe not accurate)"
    )
    wrapper_measures: WrapperMeasures = Field(
        ..., description="Wrapper performance measurements"
    )
    return_code: int = Field(..., description="Process exit code")
    last_stderr_lines: List[str] = Field(
        default_factory=list, description="Last lines of stderr output"
    )

    class Config:
        json_encoders = {Path: str}


class OutputManager:
    """
    Singleton output manager for parsing Tamarin results and creating JSON files.

    Handles parsing of stdout/stderr from Tamarin execution and creates
    structured JSON results in appropriate directories.
    """

    _instance: Optional["OutputManager"] = None
    _initialized: bool = False

    def __new__(cls) -> "OutputManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent re-initialization
        if OutputManager._initialized:
            return
        OutputManager._initialized = True

        # Initialize as uninitialized - will be set up when needed
        self.output_dir: Path = Path(".")  # Will be set during initialize()
        self.success_dir: Path = Path(".")  # Will be set during initialize()
        self.failed_dir: Path = Path(".")  # Will be set during initialize()
        self.models_dir: Path = Path(".")  # Will be set during initialize()
        self._is_setup = False

    def initialize(self, output_dir: Path) -> None:
        """
        Initialize the output manager with output directory.

        Handles directory creation and user prompting for existing directories.

        Args:
            output_dir: Base output directory path
        """
        if self._is_setup:
            # Already initialized
            return

        self.output_dir = Path(output_dir)
        self.success_dir = self.output_dir / "success"
        self.failed_dir = self.output_dir / "failed"
        self.models_dir = self.output_dir / "models"
        self._is_setup = True

        # Handle existing directory
        self._handle_existing_directory()

        # Create directories
        self._create_directories()

        notification_manager.debug(
            f"[OutputManager] Initialized with output directory: {self.output_dir}"
        )

    def _handle_existing_directory(self) -> None:
        """Handle existing output directory and prompt user if not empty."""
        if not self._is_setup:
            raise RuntimeError("[OutputManager] OutputManager not initialized")

        if not self.output_dir.exists():
            return

        if not self.output_dir.is_dir():
            raise RuntimeError(
                f"[OutputManager] Output path is not a directory: {self.output_dir}"
            )

        # Check if directory is empty
        if any(self.output_dir.iterdir()):
            # Directory is not empty, prompt user
            should_wipe = notification_manager.prompt_user(
                f"Output directory '{self.output_dir}' is not empty. Do you want to [bold #ff0000]DELETE[/bold #ff0000] its contents?",
                default=False,
            )

            if should_wipe:
                try:
                    # Remove all contents of the directory
                    for item in self.output_dir.iterdir():
                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()
                    notification_manager.info(
                        f"[OutputManager] Wiped contents of output directory: {self.output_dir}"
                    )
                except Exception as e:
                    raise RuntimeError(
                        f"[OutputManager] Failed to wipe output directory {self.output_dir}: {e}"
                    ) from e
            else:
                # Use a new directory name with a timestamp
                parent = self.output_dir.parent
                base_name = self.output_dir.name
                timestamp = datetime.now().strftime("%d-%m-%y_%H-%M-%S")
                self.output_dir = parent / f"{base_name}_{timestamp}"
                self.success_dir = self.output_dir / "success"
                self.failed_dir = self.output_dir / "failed"
                self.models_dir = self.output_dir / "models"

                # Create the new base directory (empty)
                self.output_dir.mkdir(parents=True, exist_ok=True)

                notification_manager.info(
                    f"[OutputManager] Output directory not wiped, using new directory: {self.output_dir}"
                )

    def _create_directories(self) -> None:
        """Create output directories if they don't exist."""
        if not self._is_setup:
            raise RuntimeError("[OutputManager] OutputManager not initialized")

        try:
            self.success_dir.mkdir(parents=True, exist_ok=True)
            self.failed_dir.mkdir(parents=True, exist_ok=True)
            self.models_dir.mkdir(parents=True, exist_ok=True)

            notification_manager.debug(
                "[OutputManager] Created output directory structure"
            )
        except Exception as e:
            raise RuntimeError(
                f"[OutputManager] Failed to create output directories: {e}"
            ) from e

    def process_task_result(
        self, task_result: TaskResult, output_file_name: str
    ) -> None:
        """
        Process a TaskResult and create appropriate JSON file.

        Args:
            task_result: The TaskResult from task execution
            output_file_name: Name of the output file (with .spthy extension)
        """
        if not self._is_setup:
            raise RuntimeError(
                "[OutputManager] OutputManager not initialized. Call initialize() first."
            )

        # Generate JSON filename from output file name
        json_filename = Path(output_file_name).with_suffix(".json").name

        if task_result.status == TaskStatus.COMPLETED:
            self._process_successful_task(task_result, json_filename, output_file_name)
        else:
            self._process_failed_task(task_result, json_filename)

    def _process_successful_task(
        self, task_result: TaskResult, json_filename: str, output_file_name: str
    ) -> None:
        """Process successful task and create JSON in success directory."""
        try:
            # Parse the stdout/stderr for successful task
            parsed_result = self._parse_successful_output(
                task_result.task_id,
                task_result.stdout,
                task_result.stderr,
                task_result.duration,
                task_result.memory_stats,
                output_file_name,
            )

            # Save JSON file
            json_path: Path = self.success_dir / json_filename
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(parsed_result.model_dump_json(indent=2))

            notification_manager.debug(
                f"[OutputManager] Created success result: {json_path}"
            )

        except Exception as e:
            notification_manager.error(
                f"[OutputManager] Failed to process successful task {task_result.task_id}: {e}"
            )

    def _process_failed_task(self, task_result: TaskResult, json_filename: str) -> None:
        """Process failed task and create JSON in failed directory."""
        try:
            # Parse the stdout/stderr for failed task
            parsed_result = self._parse_failed_output(
                task_result.task_id,
                task_result.stdout,
                task_result.stderr,
                task_result.duration,
                task_result.memory_stats,
                task_result.return_code,
                task_result.status,
            )

            # Save JSON file
            json_path: Path = self.failed_dir / json_filename
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(parsed_result.model_dump_json(indent=2))

            notification_manager.debug(
                f"[OutputManager] Created failed result: {json_path}"
            )

        except Exception as e:
            notification_manager.error(
                f"[OutputManager] Failed to process failed task {task_result.task_id}: {e}"
            )

    def _parse_successful_output(
        self,
        task_id: str,
        stdout: str,
        stderr: str,
        duration: float,
        memory_stats: Optional[MemoryStats],
        output_file_name: str,
    ) -> SuccessfulTaskResult:
        """Parse stdout/stderr from successful Tamarin execution."""

        combined_output = stdout + "\n" + stderr

        # Extract tamarin timing
        tamarin_timing = self._extract_tamarin_timing(combined_output)

        # Create wrapper measures
        wrapper_measures = WrapperMeasures(
            time=duration,
            avg_memory=memory_stats.avg_memory_mb if memory_stats else 0.0,
            peak_memory=memory_stats.peak_memory_mb if memory_stats else 0.0,
        )

        # Parse lemma results
        verified_lemma, falsified_lemma, unterminated_lemma = self._parse_lemma_results(
            combined_output
        )

        # Extract warnings
        warnings = self._extract_warnings(combined_output)

        # Get output spthy path from the actual output file name
        output_spthy = self.models_dir / output_file_name

        return SuccessfulTaskResult(
            task_id=task_id,
            tamarin_timing=tamarin_timing,
            wrapper_measures=wrapper_measures,
            verified_lemma=verified_lemma,
            falsified_lemma=falsified_lemma,
            unterminated_lemma=unterminated_lemma,
            warnings=warnings,
            output_spthy=str(output_spthy),
        )

    def _parse_failed_output(
        self,
        task_id: str,
        stdout: str,
        stderr: str,
        duration: float,
        memory_stats: Optional[MemoryStats],
        return_code: int,
        status: TaskStatus,
    ) -> FailedTaskResult:
        """Parse stdout/stderr from failed Tamarin execution."""

        # Create wrapper measures
        wrapper_measures = WrapperMeasures(
            time=duration,
            avg_memory=memory_stats.avg_memory_mb if memory_stats else 0.0,
            peak_memory=memory_stats.peak_memory_mb if memory_stats else 0.0,
        )

        # Get last stderr lines (last 10 lines)
        stderr_lines = stderr.strip().split("\n") if stderr.strip() else []
        last_stderr_lines = (
            stderr_lines[-10:] if len(stderr_lines) > 10 else stderr_lines
        )

        error_description = self._handle_error_description(
            stderr, stdout, return_code, status
        )

        return FailedTaskResult(
            task_id=task_id,
            error_description=error_description,
            wrapper_measures=wrapper_measures,
            return_code=return_code,
            last_stderr_lines=last_stderr_lines,
        )

    def _extract_tamarin_timing(self, output: str) -> float:
        """Extract processing time from Tamarin output."""
        # Look for "processing time: X.XXs"
        time_pattern = r"processing time:\s+(\d+\.?\d*)s"
        match = re.search(time_pattern, output)
        if match:
            return float(match.group(1))
        return 0.0

    def _parse_lemma_results(
        self, output: str
    ) -> Tuple[Dict[str, LemmaResult], Dict[str, LemmaResult], List[str]]:
        """Parse lemma results from Tamarin output."""
        verified_lemma: Dict[str, LemmaResult] = {}
        falsified_lemma: Dict[str, LemmaResult] = {}
        unterminated_lemma: List[str] = []

        # Pattern for lemma results
        # Example: "nonce_reuse_key_type (all-traces): analysis incomplete (1 steps)"
        # Example: "lemma_name (exists-trace): verified (5 steps)"
        # Example: "lemma_name (all-traces): falsified (3 steps)"

        lemma_pattern = r"(\w+)\s+\(([^)]+)\):\s+(verified|falsified|analysis incomplete)\s*(?:\((\d+)\s+steps?\))?"

        for match in re.finditer(lemma_pattern, output):
            lemma_name = match.group(1)
            analysis_type = match.group(2)
            result = match.group(3)
            steps_str = match.group(4)

            steps = int(steps_str) if steps_str else 0

            if result == "verified":
                verified_lemma[lemma_name] = LemmaResult(
                    steps=steps, analysis_type=analysis_type
                )
            elif result == "falsified":
                falsified_lemma[lemma_name] = LemmaResult(
                    steps=steps, analysis_type=analysis_type
                )
            elif result == "analysis incomplete":
                unterminated_lemma.append(lemma_name)

        return verified_lemma, falsified_lemma, unterminated_lemma

    def _extract_warnings(self, output: str) -> List[str]:
        """Extract warnings from Tamarin output."""
        warnings: List[str] = []

        # Look for WARNING: lines
        warning_pattern = r"WARNING:\s*(.+?)(?=\n|$)"
        for match in re.finditer(warning_pattern, output, re.MULTILINE):
            warning_text = match.group(1).strip()
            if warning_text:
                warnings.append(warning_text)

        # Look for wellformedness check failures
        if "wellformedness checks failed" in output:
            wellformedness_pattern = r"(\d+)\s+wellformedness checks? failed"
            match = re.search(wellformedness_pattern, output)
            if match:
                count = match.group(1)
                warnings.append(f"{count} wellformedness check(s) failed")

        # Look for derivation check timeouts
        if "Derivation checks timed out" in output:
            warnings.append("Derivation checks timed out")

        # Look for unsupported version warnings
        if "unsupported version" in output:
            version_pattern = r"'([^']+)' returned unsupported version '([^']+)'"
            match = re.search(version_pattern, output)
            if match:
                tool = match.group(1)
                version = match.group(2)
                warnings.append(f"Unsupported {tool} version: {version}")

        return warnings

    def _handle_error_description(
        self, stderr: str, stdout: str, return_code: int, status: TaskStatus
    ) -> str:
        """Handle error description
        Possible enhancement: search for patterns in stderr/stdout to report a known tamarin-prover error
        """
        if status == TaskStatus.FAILED:
            if return_code == -2:
                return "The task was likely killed by the wrapper, probably by a user action."
            if return_code == -9:
                return "The task was likely killed (SIGKILL) by the user"
            if return_code == -15:
                return "The task was likely terminated (SIGTERM) by the user"
        elif status == TaskStatus.TIMEOUT:
            return "The task timed out. Review the timeout setting for this task."
        elif status == TaskStatus.MEMORY_LIMIT_EXCEEDED:
            return "The task exceeded its memory limit. Review the memory limit setting for this task."
        return "An unexpected error occured, see stderr output below for details."

    def get_output_paths(self) -> Dict[str, Path]:
        """Get output directory paths."""
        if not self._is_setup:
            raise RuntimeError(
                "[OutputManager] OutputManager not initialized. Call initialize() first."
            )

        return {
            "base": self.output_dir,
            "success": self.success_dir,
            "failed": self.failed_dir,
            "models": self.models_dir,
        }

    def is_initialized(self) -> bool:
        """Check if the output manager is initialized."""
        return self._is_setup


# Global singleton instance
output_manager = OutputManager()
