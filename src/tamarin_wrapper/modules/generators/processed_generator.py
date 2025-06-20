"""
Generator for successful task result JSON files.

This module creates structured JSON output files for successfully processed
Tamarin execution results with enhanced lemma information.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from ...model.executable_task import TaskResult
from ...model.output_models import (
    EnhancedLemmaResult,
    ProcessedTaskResult,
    ProcessingMetadata,
    SpthyAnalysis,
)


class ProcessedOutputGenerator:
    """
    Generates structured JSON files for successful task results.
    """

    def generate_result_file(
        self,
        task_id: str,
        processing_time: float,
        lemma_results: Dict[str, EnhancedLemmaResult],
        warnings: list[str],
        metadata: ProcessingMetadata,
        spthy_analysis: SpthyAnalysis | None,
        output_path: Path,
        task_result: TaskResult | None,
    ) -> Path:
        """
        Generate a processed result JSON file.

        Args:
            task_id: Task identifier
            processing_time: Total processing time in seconds
            lemma_results: Enhanced lemma results
            warnings: List of warnings
            metadata: Processing metadata
            spthy_analysis: Optional spthy analysis results
            output_path: Path where to write the result file

        Returns:
            Path to the generated file
        """
        # Create the processed task result
        processed_result = ProcessedTaskResult(
            task_id=task_id,
            status="completed",
            processing_time=processing_time,
            lemma_results=lemma_results,
            warnings=warnings,
            metadata=metadata,
            spthy_analysis=spthy_analysis,
            timestamp=datetime.now(),
        )

        # Convert to JSON-serializable format
        result_data = self._convert_to_json_format(processed_result, task_result)

        # Write to file
        output_path.write_text(
            json.dumps(result_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        return output_path

    def _convert_to_json_format(
        self, result: ProcessedTaskResult, task_result: TaskResult | None = None
    ) -> Dict[str, Any]:
        """
        Convert ProcessedTaskResult to JSON-serializable format.

        Args:
            result: ProcessedTaskResult to convert
            task_result: Optional TaskResult for resource usage information

        Returns:
            Dictionary ready for JSON serialization
        """
        # Categorize lemmas by status
        verified_lemmas: Dict[str, Dict[str, Any]] = {}
        falsified_lemmas: Dict[str, Dict[str, Any]] = {}
        analysis_incomplete_lemmas: list[str] = []

        for lemma_name, lemma in result.lemma_results.items():
            lemma_data: Dict[str, Any] = {
                "name": lemma.name,
                "analysis_type": lemma.analysis_type,
                "steps": lemma.steps,
                "time_ms": lemma.time_ms,
                "proof_method": lemma.proof_method,
                "proof_details": lemma.proof_details,
                "attributes": lemma.attributes,
                "formula": lemma.formula,
                "line_number": lemma.line_number,
            }

            if lemma.status == "verified":
                verified_lemmas[lemma_name] = lemma_data
            elif lemma.status == "falsified":
                falsified_lemmas[lemma_name] = lemma_data
            elif lemma.status == "analysis_incomplete":
                analysis_incomplete_lemmas.append(lemma_name)

        # Calculate resource usage if available
        wrapper_resource_usage: Dict[str, Any] = {
            "peak_memory_mb": None,
            "average_memory_mb": None,
            "execution_time_s": result.processing_time,
        }

        # Fill resource usage from task_result if available
        if (
            task_result
            and hasattr(task_result, "memory_stats")
            and task_result.memory_stats
        ):
            wrapper_resource_usage["peak_memory_mb"] = (
                task_result.memory_stats.peak_memory_mb
            )
            wrapper_resource_usage["average_memory_mb"] = (
                task_result.memory_stats.avg_memory_mb
            )

        if task_result and hasattr(task_result, "duration"):
            wrapper_resource_usage["execution_time_s"] = task_result.duration

        return {
            "task_id": result.task_id,
            "wrapper_reported_ressource_usage": wrapper_resource_usage,
            "processing_time": result.processing_time,
            "verified_lemmas": verified_lemmas,
            "falsified_lemmas": falsified_lemmas,
            "analysis_incomplete_lemmas": analysis_incomplete_lemmas,
            "warnings": result.warnings,
            "metadata": {
                "analyzed_file": result.metadata.analyzed_file,
                "output_file": result.metadata.output_file,
                "theory_name": result.metadata.theory_name,
                "total_lemmas_found": result.metadata.total_lemmas_found,
                "lemmas_with_proofs": result.metadata.lemmas_with_proofs,
                "parsing_errors": result.metadata.parsing_errors,
                "maude_version_warning": result.metadata.maude_version_warning,
            },
            "timestamp": result.timestamp.isoformat(),
        }

    def generate_summary_file(
        self, results: list[ProcessedTaskResult], output_path: Path
    ) -> Path:
        """
        Generate a summary file for multiple processed results.

        Args:
            results: List of processed task results
            output_path: Path where to write the summary file

        Returns:
            Path to the generated summary file
        """
        if not results:
            summary_data: Dict[str, Any] = {
                "total_tasks": 0,
                "successful_tasks": 0,
                "total_lemmas": 0,
                "verified_lemmas": 0,
                "falsified_lemmas": 0,
                "incomplete_lemmas": 0,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            # Aggregate statistics
            total_lemmas = sum(len(r.lemma_results) for r in results)
            verified_count = sum(
                1
                for r in results
                for lemma in r.lemma_results.values()
                if lemma.status == "verified"
            )
            falsified_count = sum(
                1
                for r in results
                for lemma in r.lemma_results.values()
                if lemma.status == "falsified"
            )
            incomplete_count = sum(
                1
                for r in results
                for lemma in r.lemma_results.values()
                if lemma.status == "analysis_incomplete"
            )

            summary_data: Dict[str, Any] = {
                "total_tasks": len(results),
                "successful_tasks": len(results),
                "total_lemmas": total_lemmas,
                "verified_lemmas": verified_count,
                "falsified_lemmas": falsified_count,
                "incomplete_lemmas": incomplete_count,
                "average_processing_time": sum(r.processing_time for r in results)
                / len(results),
                "task_summaries": [
                    {
                        "task_id": r.task_id,
                        "theory_name": r.metadata.theory_name,
                        "lemma_count": len(r.lemma_results),
                        "processing_time": r.processing_time,
                        "verified": sum(
                            1
                            for l in r.lemma_results.values()
                            if l.status == "verified"
                        ),
                        "falsified": sum(
                            1
                            for l in r.lemma_results.values()
                            if l.status == "falsified"
                        ),
                        "incomplete": sum(
                            1
                            for l in r.lemma_results.values()
                            if l.status == "analysis_incomplete"
                        ),
                    }
                    for r in results
                ],
                "timestamp": datetime.now().isoformat(),
            }

        # Write summary to file
        output_path.write_text(
            json.dumps(summary_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        return output_path
