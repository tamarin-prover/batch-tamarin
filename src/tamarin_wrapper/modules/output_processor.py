"""
Output processor for parsing Tamarin execution results using hybrid approach.

This module implements the hybrid parsing architecture combining regex-based
stdout/stderr analysis with tree-sitter based spthy file parsing.
"""

import json
from pathlib import Path
from typing import Any, Optional

from ..model.executable_task import TaskResult, TaskStatus
from ..model.output_models import (
    ErrorAnalysis,
    FailureContext,
    ProcessingMetadata,
    StderrAnalysis,
)
from ..utils.notifications import notification_manager
from .analyzers.error_analyzer import ErrorAnalyzer
from .analyzers.lemma_analyzer import LemmaAnalyzer
from .analyzers.proof_analyzer import ProofAnalyzer
from .generators.failed_generator import FailedTaskGenerator
from .generators.processed_generator import ProcessedOutputGenerator
from .parsers.spthy_parser import SpthyFileParser
from .parsers.stderr_parser import StderrParser
from .parsers.stdout_parser import StdoutParser


class TamarinOutputProcessor:
    """
    Main processor coordinating hybrid parsing approach.

    Combines regex-based parsing of stdout/stderr with tree-sitter based
    parsing of spthy files to generate comprehensive analysis results.
    """

    def __init__(self, output_directory: Path):
        """
        Initialize the output processor with all components.

        Args:
            output_directory: Directory where output files are stored
        """
        notification_manager.phase_separator("Output Processing Initialization")
        notification_manager.debug(
            "[OutputProcessor] Initializing TamarinOutputProcessor"
        )

        self.output_directory = Path(output_directory)
        self.processed_dir = self.output_directory / "processed"
        self.failed_tasks_dir = self.output_directory / "failed_tasks"

        # Ensure directories exist
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.failed_tasks_dir.mkdir(parents=True, exist_ok=True)

        notification_manager.debug(
            f"[OutputProcessor] Output directories created: {self.processed_dir}, {self.failed_tasks_dir}"
        )

        # Initialize parsers
        notification_manager.debug("[OutputProcessor] Initializing parsers...")
        self.stdout_parser = StdoutParser()
        self.stderr_parser = StderrParser()

        # Try to initialize tree-sitter parser
        try:
            notification_manager.debug(
                "[OutputProcessor] Attempting to initialize tree-sitter spthy parser..."
            )
            self.spthy_parser = SpthyFileParser()
            self.spthy_available = True
            notification_manager.success(
                "[OutputProcessor] Tree-sitter spthy parser initialized successfully"
            )
        except (ImportError, FileNotFoundError, RuntimeError) as e:
            notification_manager.error(
                f"[OutputProcessor] Tree-sitter spthy parser not available: {e}"
            )
            ignore_tree_sitter = notification_manager.prompt_user(
                "Tree-sitter parser initialization failed. Do you want to continue without it?",
                False,
            )
            if not ignore_tree_sitter:
                notification_manager.critical(
                    "[OutputProcessor] Exiting due to user choice to not ignore tree-sitter"
                )
            self.spthy_parser = None
            self.spthy_available = False

        # Initialize analyzers
        notification_manager.debug("[OutputProcessor] Initializing analyzers...")
        self.error_analyzer = ErrorAnalyzer()
        self.lemma_analyzer = LemmaAnalyzer()
        self.proof_analyzer = ProofAnalyzer()

        # Initialize generators
        notification_manager.debug(
            "[OutputProcessor] Initializing result generators..."
        )
        self.processed_generator = ProcessedOutputGenerator()
        self.failed_generator = FailedTaskGenerator()

        notification_manager.info(
            f"[OutputProcessor] TamarinOutputProcessor initialized (tree-sitter: {'[bold green]✓[/bold green]' if self.spthy_available else '[bold #ff0000]✗[/bold #ff0000]'})"
        )

    def process_task_output(
        self,
        task_result: TaskResult,
        tamarin_output_file: Optional[Path] = None,
        lemma_filter: Optional[str] = None,
    ) -> Path:
        """
        Main processing entry point with enhanced error handling.

        Args:
            task_result: TaskResult containing stdout/stderr from execution
            tamarin_output_file: Optional path to Tamarin's .spthy output file
            lemma_filter: Optional lemma name filter for targeted analysis

        Returns:
            Path to the generated result file (either processed or failed)
        """
        task_id = task_result.task_id
        notification_manager.debug(
            f"[OutputProcessor] Processing output for task: {task_id}"
        )

        try:
            # Step 1: Parse stderr first to detect critical errors
            notification_manager.debug(
                "[OutputProcessor] Step 1: Analyzing stderr for critical errors..."
            )
            stderr_analysis = self.stderr_parser.analyze(task_result.stderr)

            if stderr_analysis.error_type:
                notification_manager.debug(
                    f"[OutputProcessor] Detected error type: {stderr_analysis.error_type.value}"
                )

            # If critical error detected, generate failed result
            if stderr_analysis.is_critical_error:
                notification_manager.debug(
                    f"[OutputProcessor] Tamarin error detected in task {task_id}, generating failed result"
                )
                return self._handle_critical_error(task_result, stderr_analysis)

            # Step 2: Parse stdout for execution results
            notification_manager.debug(
                "[OutputProcessor] Step 2: Parsing stdout for execution results..."
            )
            stdout_analysis = self.stdout_parser.parse(task_result.stdout)

            notification_manager.debug(
                f"[OutputProcessor] Found {len(stdout_analysis.lemma_results)} lemma results from stdout"
            )
            notification_manager.debug(
                f"[OutputProcessor] Processing time: {stdout_analysis.processing_time}s"
            )

            # Step 3: Parse spthy file if available and tree-sitter is working
            spthy_analysis = None
            if tamarin_output_file and tamarin_output_file.exists():
                notification_manager.debug(
                    f"[OutputProcessor] Step 3: Attempting to parse spthy file: {tamarin_output_file}"
                )

                if self.spthy_available and self.spthy_parser is not None:
                    try:
                        spthy_analysis = self.spthy_parser.parse_file(
                            tamarin_output_file
                        )
                        notification_manager.debug(
                            f"[OutputProcessor] Successfully parsed spthy file, found {len(spthy_analysis.lemmas)} lemmas"
                        )
                    except Exception as e:
                        notification_manager.debug(
                            f"[OutputProcessor] Failed to parse spthy file {tamarin_output_file}: {e}"
                        )
                else:
                    notification_manager.debug(
                        "[OutputProcessor] Tree-sitter parser not available, skipping spthy analysis"
                    )
            else:
                notification_manager.debug(
                    "[OutputProcessor] No spthy output file provided or file doesn't exist"
                )

            # Step 4: Combine analyses to create enhanced lemma results
            notification_manager.debug(
                "[OutputProcessor] Step 4: Combining analyses to create enhanced lemma results..."
            )
            enhanced_lemmas = self.lemma_analyzer.combine_analyses(
                stdout_analysis, spthy_analysis
            )

            notification_manager.debug(
                f"[OutputProcessor] Created {len(enhanced_lemmas)} enhanced lemma results"
            )

            # Step 5: Create processing metadata
            notification_manager.debug(
                "[OutputProcessor] Step 5: Creating processing metadata..."
            )
            metadata = ProcessingMetadata(
                analyzed_file=stdout_analysis.analyzed_file,
                output_file=stdout_analysis.output_file,
                theory_name=spthy_analysis.theory_name if spthy_analysis else None,
                total_lemmas_found=len(enhanced_lemmas),
                lemmas_with_proofs=sum(
                    1
                    for lemma in enhanced_lemmas.values()
                    if lemma.proof_method or lemma.proof_details
                ),
                parsing_errors=spthy_analysis.parsing_errors if spthy_analysis else [],
                maude_version_warning=stdout_analysis.maude_version_warning,
            )

            # Step 6: Generate processed result file
            notification_manager.debug(
                "[OutputProcessor] Step 6: Generating processed result file..."
            )
            result_file = self.processed_dir / f"result_{task_id}.json"

            generated_file = self.processed_generator.generate_result_file(
                task_id=task_id,
                processing_time=stdout_analysis.processing_time,
                lemma_results=enhanced_lemmas,
                warnings=stdout_analysis.warnings,
                metadata=metadata,
                spthy_analysis=spthy_analysis,
                output_path=result_file,
                task_result=task_result,  # Pass task_result for resource usage
            )

            notification_manager.success(
                f"[OutputProcessor] Successfully processed task {task_id} result in {generated_file}"
            )
            return generated_file

        except Exception as e:
            # Unexpected error during processing
            notification_manager.error(
                f"[OutputProcessor] Error processing task {task_id}: {e}"
            )
            return self._handle_processing_error(task_result, str(e))

    def _handle_critical_error(
        self, task_result: TaskResult, stderr_analysis: StderrAnalysis
    ) -> Path:
        """
        Handle critical errors that prevent normal processing.

        Args:
            task_result: Original task result
            stderr_analysis: Analysis of stderr indicating critical error

        Returns:
            Path to generated failed result file
        """
        # Create failure context
        failure_context = FailureContext(
            theory_name=None,  # Unable to determine due to critical error
            partial_lemma_results={},
            last_successful_lemma=None,
            failure_point="startup" if stderr_analysis.error_type else "unknown",
            resource_usage=None,
        )

        # Analyze error and get suggestions
        error_analysis = self.error_analyzer.analyze_error(
            stderr_analysis, failure_context
        )

        # Get suggested modifications
        suggested_modifications = self.error_analyzer.suggest_task_modifications(
            error_analysis.error_type,
            current_timeout=300,  # Default timeout
            current_memory=4,  # Default memory
        )

        # Generate failed result file
        result_file = self.failed_tasks_dir / f"failed_{task_result.task_id}.json"
        generated_file = self.failed_generator.generate_failed_result_file(
            task_result=task_result,
            error_analysis=error_analysis,
            suggested_modifications=suggested_modifications,
            failure_context=failure_context,
            output_path=result_file,
        )

        notification_manager.debug(
            f"[OutputProcessor] Generated failed result file: {generated_file}"
        )
        return generated_file

    def _handle_processing_error(
        self, task_result: TaskResult, error_message: str
    ) -> Path:
        """
        Handle unexpected processing errors.

        Args:
            task_result: Original task result
            error_message: Error message from exception

        Returns:
            Path to generated failed result file
        """
        # Create minimal error analysis for processing failure
        from ..model.output_models import ErrorType

        error_analysis = ErrorAnalysis(
            error_type=ErrorType.SYSTEM_ERROR,
            description=f"Processing error: {error_message}",
            context_lines=[],
            suggested_fixes=[
                "Check tamarin-wrapper configuration",
                "Verify output file permissions",
                "Review stdout/stderr for parsing issues",
            ],
        )

        failure_context = FailureContext(
            theory_name=None,
            partial_lemma_results={},
            last_successful_lemma=None,
            failure_point="processing",
            resource_usage=None,
        )

        suggested_modifications = self.error_analyzer.suggest_task_modifications(
            ErrorType.SYSTEM_ERROR, current_timeout=300, current_memory=4
        )

        # Generate failed result file
        result_file = self.failed_tasks_dir / f"failed_{task_result.task_id}.json"
        generated_file = self.failed_generator.generate_failed_result_file(
            task_result=task_result,
            error_analysis=error_analysis,
            suggested_modifications=suggested_modifications,
            failure_context=failure_context,
            output_path=result_file,
        )

        notification_manager.debug(
            f"[OutputProcessor] Generated failed result file: {generated_file}"
        )
        return generated_file

    def generate_batch_summary(self, task_results: list[TaskResult]) -> dict[str, Path]:
        """
        Generate summary files for a batch of processed tasks.

        Args:
            task_results: List of processed task results

        Returns:
            Dictionary mapping summary types to file paths
        """
        summary_files: dict[str, Path] = {}

        # Separate successful and failed results
        # Note: This would need to be enhanced to actually load the processed results
        # For now, this is a placeholder structure

        # Generate overall summary
        summary_file = self.output_directory / "batch_summary.json"
        summary_data: dict[str, Any] = {
            "total_tasks": len(task_results),
            "successful_tasks": sum(
                1 for r in task_results if r.status == TaskStatus.COMPLETED
            ),
            "failed_tasks": sum(
                1 for r in task_results if r.status == TaskStatus.FAILED
            ),
            "processing_summary": {
                "spthy_parser_available": self.spthy_available,
                "output_directories": {
                    "processed": str(self.processed_dir),
                    "failed_tasks": str(self.failed_tasks_dir),
                },
            },
        }

        summary_file.write_text(
            json.dumps(summary_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        summary_files["overall"] = summary_file

        notification_manager.info(
            f"[OutputProcessor] Generated batch summary: {summary_file}"
        )

        return summary_files
