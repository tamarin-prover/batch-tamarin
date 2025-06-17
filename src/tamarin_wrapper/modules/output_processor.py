"""
Output processor for parsing Tamarin execution results.

This module processes both stdout from Tamarin execution and the generated
.spthy output files to extract structured verification results, timing
information, and proof statistics.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..model.executable_task import TaskResult
from ..model.output_models import LemmaResult, ParsedTamarinOutput
from ..utils.notifications import notification_manager


class TamarinOutputProcessor:
    """
    Processes Tamarin output to extract structured verification results.

    This processor handles both stdout from task execution and the generated
    .spthy files to create comprehensive result.json files containing lemma
    verification results, timing information, and proof statistics.
    """

    # Regex patterns for parsing Tamarin output
    TAMARIN_PATTERNS = {
        # Lemma result line: "nonce_reuse_key_type (all-traces): verified (48 steps)"
        "lemma_result_line": re.compile(
            r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]+)\):\s*(verified|falsified|analysis incomplete)\s*\((\d+)\s+steps?\)"
        ),
        # Processing time: "processing time: 12.10s"
        "processing_time": re.compile(
            r"^\s*processing time:\s*(\d+(?:\.\d+)?)(s|ms|m)"
        ),
        # Output file: "output: results/tamarin_output_models/..."
        "output_file": re.compile(r"^\s*output:\s*(.+)"),
        # Analyzed file: "analyzed: protocols/..."
        "analyzed_file": re.compile(r"^\s*analyzed:\s*(.+)"),
        # Timing extraction: extract milliseconds from various formats
        "timing_ms": re.compile(r"(\d+(?:\.\d+)?)\s*ms"),
        "timing_s": re.compile(r"(\d+(?:\.\d+)?)\s*s"),
        "timing_m": re.compile(r"(\d+(?:\.\d+)?)\s*m"),
        # Summary line: "summary of summaries:"
        "summary_start": re.compile(r"summary\s+of\s+summaries:", re.IGNORECASE),
        # Warnings and errors
        "warning": re.compile(r"WARNING[:\s](.+)", re.IGNORECASE),
        "error": re.compile(r"ERROR[:\s](.+)", re.IGNORECASE),
    }

    def __init__(self, output_directory: Path):
        """
        Initialize the output processor.

        Args:
            output_directory: Directory where output files are stored
        """
        self.output_directory = Path(output_directory)
        self.processed_dir = self.output_directory / "processed"
        self.tamarin_output_dir = self.output_directory / "tamarin_output_models"

        # Ensure directories exist
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.tamarin_output_dir.mkdir(parents=True, exist_ok=True)

    def process_task_output(
        self,
        task_result: TaskResult,
        tamarin_output_file: Optional[Path] = None,
        lemma_filter: Optional[str] = None,
    ) -> Path:
        """
        Process a task's output and generate a result.json file.

        Args:
            task_result: TaskResult containing stdout/stderr from execution
            tamarin_output_file: Optional path to Tamarin's .spthy output file
            lemma_filter: Optional lemma name to filter results (if specified in task)

        Returns:
            Path to the generated result.json file
        """
        task_id = task_result.task_id

        notification_manager.debug(
            f"[OutputProcessor] Processing output for task: {task_id}"
        )

        # Check if task failed and already reported in failed_tasks/
        if self._is_failed_task_already_reported(task_id):
            notification_manager.info(
                f"[OutputProcessor] Skipping failed task {task_id} - already reported in failed_tasks/"
            )
            return (
                self.processed_dir / f"result_{task_id}.json"
            )  # Return expected path without processing

        # Parse output from multiple sources
        parsed_output = self._parse_tamarin_output(
            task_result, tamarin_output_file, lemma_filter
        )

        # Generate result.json
        result_file = self._generate_result_json(task_id, parsed_output, task_result)

        notification_manager.debug(
            f"[OutputProcessor] Generated result file: {result_file}"
        )

        return result_file

    def _parse_tamarin_output(
        self,
        task_result: TaskResult,
        tamarin_output_file: Optional[Path],
        lemma_filter: Optional[str],
    ) -> ParsedTamarinOutput:
        """
        Parse Tamarin output from stdout and output file.

        Args:
            task_result: TaskResult containing stdout/stderr
            tamarin_output_file: Optional path to Tamarin output file
            lemma_filter: Optional lemma name to filter

        Returns:
            ParsedTamarinOutput with extracted information
        """
        lemma_results: Dict[str, LemmaResult] = {}
        warnings: List[str] = []
        errors: List[str] = []
        total_time_ms = 0
        total_steps = 0

        # Parse stdout first
        if task_result.stdout:
            stdout_results = self._parse_output_text(task_result.stdout, lemma_filter)
            lemma_results.update(stdout_results.lemma_results)
            warnings.extend(stdout_results.warnings)
            errors.extend(stdout_results.errors)
            total_time_ms += stdout_results.total_time_ms
            total_steps += stdout_results.total_steps

        # Parse Tamarin output file if available
        if tamarin_output_file and tamarin_output_file.exists():
            try:
                tamarin_content = tamarin_output_file.read_text(encoding="utf-8")
                file_results = self._parse_output_text(tamarin_content, lemma_filter)

                # Merge results (output file takes precedence for lemma details)
                for lemma_name, lemma_result in file_results.lemma_results.items():
                    if lemma_name in lemma_results:
                        # Keep existing but update with more detailed info from file
                        existing = lemma_results[lemma_name]
                        lemma_results[lemma_name] = LemmaResult(
                            name=lemma_name,
                            status=lemma_result.status or existing.status,
                            time_ms=lemma_result.time_ms or existing.time_ms,
                            steps=lemma_result.steps or existing.steps,
                        )
                    else:
                        lemma_results[lemma_name] = lemma_result

                warnings.extend(file_results.warnings)
                errors.extend(file_results.errors)
                total_time_ms = max(total_time_ms, file_results.total_time_ms)
                total_steps = max(total_steps, file_results.total_steps)

            except Exception as e:
                notification_manager.warning(
                    f"[OutputProcessor] Failed to read Tamarin output file {tamarin_output_file}: {e}"
                )
                errors.append(f"Failed to read Tamarin output file: {e}")

        # Parse stderr for additional errors
        if task_result.stderr:
            stderr_errors = self._extract_errors_warnings(task_result.stderr)
            errors.extend(stderr_errors)

        # If no time was parsed from output, use task duration
        if total_time_ms == 0 and task_result.duration > 0:
            total_time_ms = int(task_result.duration * 1000)

        return ParsedTamarinOutput(
            lemma_results=lemma_results,
            total_time_ms=total_time_ms,
            total_steps=total_steps,
            warnings=list(set(warnings)),  # Remove duplicates
            errors=list(set(errors)),  # Remove duplicates
        )

    def _parse_output_text(
        self, text: str, lemma_filter: Optional[str]
    ) -> ParsedTamarinOutput:
        """
        Parse text output from Tamarin (stdout or file content).

        Args:
            text: Text content to parse
            lemma_filter: Optional lemma name to filter

        Returns:
            ParsedTamarinOutput with extracted information
        """
        lines = text.split("\n")
        lemma_results: Dict[str, LemmaResult] = {}
        warnings: List[str] = []
        errors: List[str] = []
        total_time_ms = 0
        total_steps = 0

        # Parse all lines for lemma results (no need to track summary section)
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for summary section (optional - some outputs don't have this marker)
            if self.TAMARIN_PATTERNS["summary_start"].search(line):
                continue

            # Parse analyzed file (can be anywhere)
            analyzed_match = self.TAMARIN_PATTERNS["analyzed_file"].match(line)
            if analyzed_match:
                continue

            # Parse output file (can be anywhere)
            output_match = self.TAMARIN_PATTERNS["output_file"].match(line)
            if output_match:
                continue

            # Parse processing time (can be anywhere)
            time_match = self.TAMARIN_PATTERNS["processing_time"].match(line)
            if time_match:
                time_value = float(time_match.group(1))
                time_unit = time_match.group(2)

                if time_unit == "s":
                    total_time_ms = int(time_value * 1000)
                elif time_unit == "ms":
                    total_time_ms = int(time_value)
                elif time_unit == "m":
                    total_time_ms = int(time_value * 60 * 1000)
                continue

            # Parse lemma result lines (can be anywhere, not just in summary)
            lemma_match = self.TAMARIN_PATTERNS["lemma_result_line"].match(line)
            if lemma_match:
                lemma_name = lemma_match.group(1)
                # lemma_type = lemma_match.group(2)  # e.g., "all-traces" or "exists-trace" - not used
                status = lemma_match.group(3)
                steps = int(lemma_match.group(4))

                # Apply lemma filter if specified
                if lemma_filter and lemma_name != lemma_filter:
                    continue

                # Normalize status
                if status == "analysis incomplete":
                    status = "analysis_incomplete"

                lemma_results[lemma_name] = LemmaResult(
                    name=lemma_name,
                    status=status,
                    time_ms=None,  # Individual lemma timing not available in this format
                    steps=steps,
                )
                total_steps += steps
                continue

            # Check for warnings (including wellformedness warnings)
            if "wellformedness check failed" in line.lower():
                warnings.append(line)
                continue

            warning_match = self.TAMARIN_PATTERNS["warning"].search(line)
            if warning_match:
                warnings.append(warning_match.group(1).strip())
                continue

            error_match = self.TAMARIN_PATTERNS["error"].search(line)
            if error_match:
                errors.append(error_match.group(1).strip())
                continue

        return ParsedTamarinOutput(
            lemma_results=lemma_results,
            total_time_ms=total_time_ms,
            total_steps=total_steps,
            warnings=warnings,
            errors=errors,
        )

    def _parse_time_to_ms(self, time_str: str) -> int:
        """
        Parse time string to milliseconds.

        Args:
            time_str: Time string like "10ms", "1.5s", "2m"

        Returns:
            Time in milliseconds
        """
        if not time_str:
            return 0

        # Try milliseconds
        ms_match = self.TAMARIN_PATTERNS["timing_ms"].search(time_str)
        if ms_match:
            return int(float(ms_match.group(1)))

        # Try seconds
        s_match = self.TAMARIN_PATTERNS["timing_s"].search(time_str)
        if s_match:
            return int(float(s_match.group(1)) * 1000)

        # Try minutes
        m_match = self.TAMARIN_PATTERNS["timing_m"].search(time_str)
        if m_match:
            return int(float(m_match.group(1)) * 60 * 1000)

        return 0

    def _extract_errors_warnings(self, stderr: str) -> List[str]:
        """
        Extract error messages from stderr.

        Args:
            stderr: Standard error output

        Returns:
            List of error messages
        """
        errors: List[str] = []
        lines = stderr.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Common error patterns
            if any(
                pattern in line.lower()
                for pattern in [
                    "error",
                    "exception",
                    "failed",
                    "abort",
                    "fatal",
                    "parse error",
                    "syntax error",
                    "out of memory",
                ]
            ):
                errors.append(line)

        return errors

    def _generate_result_json(
        self, task_id: str, parsed_output: ParsedTamarinOutput, task_result: TaskResult
    ) -> Path:
        """
        Generate a result.json file with the parsed output.
        Only includes global execution metadata, parsing results, and proof information.

        Args:
            task_id: Task identifier
            parsed_output: Parsed Tamarin output
            task_result: Original task result

        Returns:
            Path to the generated result.json file
        """
        # Global execution metadata (only id, execution time, memory_stats)
        global_metadata: Dict[str, Union[str, int, Optional[Dict[str, float]]]] = {
            "task_id": task_id,
            "execution_time_ms": int(task_result.duration * 1000),
            "memory_stats": (
                {
                    "peak_memory_mb": task_result.memory_stats.peak_memory_mb,
                    "avg_memory_mb": task_result.memory_stats.avg_memory_mb,
                }
                if task_result.memory_stats
                else None
            ),
        }

        # Stdout parsing results (warnings, errors, verified/falsified lemmas with time/steps)
        verified_lemmas: List[Dict[str, Union[str, Optional[int]]]] = []
        falsified_lemmas: List[Dict[str, Union[str, Optional[int]]]] = []
        incomplete_lemma_proofs: List[Dict[str, Union[str, Optional[int]]]] = []

        # Categorize lemmas by status
        for _lemma_name, lemma_result in parsed_output.lemma_results.items():
            lemma_info: Dict[str, Union[str, Optional[int]]] = {
                "name": lemma_result.name,
                "time_ms": lemma_result.time_ms,
                "steps": lemma_result.steps,
            }

            if lemma_result.status == "verified":
                verified_lemmas.append(lemma_info)
            elif lemma_result.status == "falsified":
                falsified_lemmas.append(lemma_info)
            elif lemma_result.status == "analysis_incomplete":
                incomplete_lemma_proofs.append(lemma_info)

        parsing_results: Dict[str, Any] = {
            "warnings": parsed_output.warnings,
            "errors": parsed_output.errors,
            "verified_lemmas": verified_lemmas,
            "falsified_lemmas": falsified_lemmas,
            "incomplete_lemma_proofs": incomplete_lemma_proofs,
        }

        # Proof information from spthy file (if available)
        proof_info = self._extract_proof_from_spthy(
            self._find_tamarin_output_file(task_id)
        )

        result_data: Dict[str, Any] = {
            "global_metadata": global_metadata,
            "parsing_results": parsing_results,
            "proof_info": proof_info,
        }

        # Generate result file path
        result_file = self.processed_dir / f"result_{task_id}.json"

        # Write result file
        try:
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False)

            notification_manager.debug(
                f"[OutputProcessor] Wrote result file: {result_file}"
            )

        except Exception as e:
            notification_manager.error(
                f"[OutputProcessor] Failed to write result file {result_file}: {e}"
            )
            raise

        return result_file

    def process_multiple_tasks(
        self, task_results: List[TaskResult], output_directory: Optional[Path] = None
    ) -> List[Path]:
        """
        Process multiple task results and generate result.json files for each.

        Args:
            task_results: List of TaskResult objects to process
            output_directory: Optional output directory (uses self.output_directory if None)

        Returns:
            List of paths to generated result.json files
        """
        if output_directory:
            self.output_directory = Path(output_directory)
            self.processed_dir = self.output_directory / "processed"
            self.tamarin_output_dir = self.output_directory / "tamarin_output_models"
            self.processed_dir.mkdir(parents=True, exist_ok=True)

        result_files: List[Path] = []

        for task_result in task_results:
            try:
                # Look for corresponding Tamarin output file
                tamarin_file = self._find_tamarin_output_file(task_result.task_id)

                # Process the task output
                result_file = self.process_task_output(task_result, tamarin_file)
                result_files.append(result_file)

            except Exception as e:
                notification_manager.error(
                    f"[OutputProcessor] Failed to process task {task_result.task_id}: {e}"
                )

        notification_manager.info(
            f"[OutputProcessor] Processed {len(result_files)} task results"
        )

        return result_files

    def _find_tamarin_output_file(self, task_id: str) -> Optional[Path]:
        """
        Find the Tamarin output file for a given task ID.

        Args:
            task_id: Task identifier

        Returns:
            Path to Tamarin output file, or None if not found
        """
        # Look for files matching various patterns:
        # 1. tam_{task_id}.spthy (in tamarin_output_models directory)
        # 2. {task_id}.txt or {task_id}.spthy (in main output directory)
        # 3. Any .spthy files in output directory containing task_id

        # Extract the lemma name from task_id if it follows the pattern task_lemma_version
        # For example: "stable_wpa2_nonce_reuse_key_type_stable" -> "nonce_reuse_key_type"
        parts = task_id.split("_")
        if len(parts) >= 4:
            # Remove version prefix and suffix to get lemma name
            lemma_name = "_".join(
                parts[2:-1]
            )  # Skip first 2 (version_protocol) and last 1 (version)
        else:
            lemma_name = task_id

        patterns = [
            f"tam_{task_id}.spthy",
            f"tam_*{lemma_name}*.spthy",
            f"{task_id}.txt",
            f"{task_id}.spthy",
            f"*{task_id}*.spthy",
            f"*{lemma_name}*.spthy",
        ]

        search_dirs = [self.tamarin_output_dir, self.output_directory]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for pattern in patterns:
                tamarin_files = list(search_dir.glob(pattern))
                if tamarin_files:
                    if len(tamarin_files) > 1:
                        notification_manager.warning(
                            f"[OutputProcessor] Multiple Tamarin output files found for {task_id} with pattern {pattern}, using most recent"
                        )
                        # Return most recent file
                        return max(tamarin_files, key=lambda p: p.stat().st_mtime)
                    return tamarin_files[0]

        notification_manager.debug(
            f"[OutputProcessor] No Tamarin output file found for {task_id}, searched patterns: {patterns}"
        )
        return None

    def _is_failed_task_already_reported(self, task_id: str) -> bool:
        """
        Check if a failed task is already reported in failed_tasks/ directory.

        Args:
            task_id: Task identifier

        Returns:
            True if task is already reported as failed, False otherwise
        """
        failed_tasks_dir = self.output_directory / "failed_tasks"
        if not failed_tasks_dir.exists():
            return False

        # Look for any file containing the task_id in the failed_tasks directory
        for _failed_file in failed_tasks_dir.glob(f"*{task_id}*"):
            return True

        return False

    def _extract_proof_from_spthy(self, spthy_file: Optional[Path]) -> Dict[str, Any]:
        """
        Extract proof information from the spthy file.

        Args:
            spthy_file: Path to the .spthy file

        Returns:
            Dictionary containing proof information
        """
        if not spthy_file or not spthy_file.exists():
            return {"proofs": [], "source": "spthy_not_available"}

        try:
            content = spthy_file.read_text(encoding="utf-8")
            proofs = self._parse_spthy_proofs(content)
            return {
                "proofs": proofs,
                "source": str(spthy_file.name),
            }
        except Exception as e:
            notification_manager.warning(
                f"[OutputProcessor] Failed to parse spthy file {spthy_file}: {e}"
            )
            return {"proofs": [], "source": "spthy_parse_error", "error": str(e)}

    def _parse_spthy_proofs(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse proof information from spthy file content.

        Args:
            content: Content of the spthy file

        Returns:
            List of proof dictionaries
        """
        proofs: List[Dict[str, Any]] = []
        lines = content.split("\n")

        # Pattern to match lemma definitions and their proofs
        lemma_pattern = re.compile(
            r"^lemma\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(\[[^\]]*\])?\s*:"
        )
        proof_start_pattern = re.compile(r"^(simplify|solve|by\s+)")
        proof_end_pattern = re.compile(r"^qed$")

        current_lemma = None
        current_proof_lines = []
        in_proof = False

        for _line_num, line in enumerate(lines, 1):
            line = line.strip()

            # Check for lemma start
            lemma_match = lemma_pattern.match(line)
            if lemma_match:
                # Save previous lemma if exists
                if current_lemma and current_proof_lines:
                    proof_dict: Dict[str, Any] = {
                        "lemma_name": current_lemma,
                        "proof_lines": current_proof_lines,
                        "line_count": len(current_proof_lines),
                    }
                    proofs.append(proof_dict)

                current_lemma = lemma_match.group(1)
                current_proof_lines = []
                in_proof = False
                continue

            # Check for proof start
            if not in_proof and proof_start_pattern.match(line):
                in_proof = True
                current_proof_lines = [line]
                continue

            # Check for proof end
            if in_proof and proof_end_pattern.match(line):
                current_proof_lines.append(line)
                in_proof = False
                continue

            # Collect proof lines
            if in_proof:
                current_proof_lines.append(line)

        # Handle last lemma
        if current_lemma and current_proof_lines:
            final_proof_dict: Dict[str, Any] = {
                "lemma_name": current_lemma,
                "proof_lines": current_proof_lines,
                "line_count": len(current_proof_lines),
            }
            proofs.append(final_proof_dict)

        return proofs
