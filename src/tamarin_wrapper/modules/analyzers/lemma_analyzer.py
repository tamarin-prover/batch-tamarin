"""
Lemma analyzer for combining and enhancing lemma results.

This module combines lemma information from stdout parsing and spthy analysis
to create enhanced lemma results with complete information.
"""

from typing import Dict, List, Optional

from ...model.output_models import (
    EnhancedLemmaResult,
    LemmaResult,
    SpthyAnalysis,
    SpthyLemmaInfo,
    StdoutAnalysis,
)


class LemmaAnalyzer:
    """
    Combines lemma results from different sources to create enhanced results.
    """

    def combine_analyses(
        self,
        stdout_analysis: StdoutAnalysis,
        spthy_analysis: Optional[SpthyAnalysis] = None,
    ) -> Dict[str, EnhancedLemmaResult]:
        """
        Combine stdout and spthy analyses to create enhanced lemma results.

        Args:
            stdout_analysis: Results from stdout parsing
            spthy_analysis: Optional results from spthy file analysis

        Returns:
            Dictionary mapping lemma names to enhanced results
        """
        enhanced_results: Dict[str, EnhancedLemmaResult] = {}

        # Start with lemmas from stdout (these have execution results)
        for lemma_name, stdout_lemma in stdout_analysis.lemma_results.items():
            enhanced_results[lemma_name] = self._create_enhanced_lemma(
                stdout_lemma,
                spthy_analysis.lemmas.get(lemma_name) if spthy_analysis else None,
            )

        # Add lemmas that are only in spthy analysis (not executed)
        if spthy_analysis:
            for lemma_name, spthy_lemma in spthy_analysis.lemmas.items():
                if lemma_name not in enhanced_results:
                    # Create enhanced lemma from spthy info only
                    enhanced_results[lemma_name] = (
                        self._create_enhanced_lemma_from_spthy(spthy_lemma)
                    )

        return enhanced_results

    def categorize_lemmas(
        self, lemma_results: Dict[str, EnhancedLemmaResult]
    ) -> Dict[str, Dict[str, EnhancedLemmaResult]]:
        """
        Categorize lemmas by their status.

        Args:
            lemma_results: Dictionary of enhanced lemma results

        Returns:
            Dictionary with categories as keys and lemma dictionaries as values
        """
        categorized: Dict[str, Dict[str, EnhancedLemmaResult]] = {
            "verified": {},
            "falsified": {},
            "analysis_incomplete": {},
            "not_executed": {},
        }

        for lemma_name, lemma in lemma_results.items():
            status = lemma.status
            if status in categorized:
                categorized[status][lemma_name] = lemma
            else:
                # Handle any unexpected status
                categorized["not_executed"][lemma_name] = lemma

        return categorized

    def generate_lemma_summary(
        self, lemma_results: Dict[str, EnhancedLemmaResult]
    ) -> Dict[str, int]:
        """
        Generate summary statistics for lemmas.

        Args:
            lemma_results: Dictionary of enhanced lemma results

        Returns:
            Dictionary with summary statistics
        """
        summary = {
            "total_lemmas": len(lemma_results),
            "verified": 0,
            "falsified": 0,
            "analysis_incomplete": 0,
            "with_proofs": 0,
            "with_timing": 0,
            "all_traces": 0,
            "exists_trace": 0,
        }

        for lemma in lemma_results.values():
            # Count by status
            if lemma.status == "verified":
                summary["verified"] += 1
            elif lemma.status == "falsified":
                summary["falsified"] += 1
            elif lemma.status == "analysis_incomplete":
                summary["analysis_incomplete"] += 1

            # Count by analysis type
            if lemma.analysis_type == "all-traces":
                summary["all_traces"] += 1
            elif lemma.analysis_type == "exists-trace":
                summary["exists_trace"] += 1

            # Count features
            if lemma.proof_method or lemma.proof_details:
                summary["with_proofs"] += 1

            if lemma.time_ms is not None:
                summary["with_timing"] += 1

        return summary

    def _create_enhanced_lemma(
        self, stdout_lemma: LemmaResult, spthy_lemma: Optional[SpthyLemmaInfo] = None
    ) -> EnhancedLemmaResult:
        """
        Create enhanced lemma result from stdout and optional spthy info.

        Args:
            stdout_lemma: Lemma result from stdout parsing
            spthy_lemma: Optional lemma info from spthy analysis

        Returns:
            Enhanced lemma result combining both sources
        """
        enhanced = EnhancedLemmaResult(
            name=stdout_lemma.name,
            status=stdout_lemma.status,
            analysis_type=stdout_lemma.analysis_type,
            steps=stdout_lemma.steps,
            time_ms=stdout_lemma.time_ms,
        )

        # Add information from spthy analysis if available
        if spthy_lemma:
            enhanced.proof_method = spthy_lemma.proof_method
            enhanced.proof_details = spthy_lemma.proof_steps
            enhanced.attributes = spthy_lemma.attributes
            enhanced.formula = spthy_lemma.formula
            enhanced.line_number = spthy_lemma.line_number

            # Prefer spthy analysis_type if available (more accurate)
            if spthy_lemma.analysis_type:
                enhanced.analysis_type = spthy_lemma.analysis_type

        return enhanced

    def _create_enhanced_lemma_from_spthy(
        self, spthy_lemma: SpthyLemmaInfo
    ) -> EnhancedLemmaResult:
        """
        Create enhanced lemma result from spthy info only (not executed).

        Args:
            spthy_lemma: Lemma info from spthy analysis

        Returns:
            Enhanced lemma result with spthy information
        """
        # Map spthy proof status to execution status
        status = "not_executed"
        if spthy_lemma.proof_status == "proven":
            status = "verified"
        elif spthy_lemma.proof_status == "failed":
            status = "falsified"

        return EnhancedLemmaResult(
            name=spthy_lemma.name,
            status=status,
            analysis_type=spthy_lemma.analysis_type,
            steps=None,  # No execution info
            time_ms=None,  # No execution info
            proof_method=spthy_lemma.proof_method,
            proof_details=spthy_lemma.proof_steps,
            attributes=spthy_lemma.attributes,
            formula=spthy_lemma.formula,
            line_number=spthy_lemma.line_number,
        )

    def find_problematic_lemmas(
        self, lemma_results: Dict[str, EnhancedLemmaResult]
    ) -> List[str]:
        """
        Identify lemmas that might need attention.

        Args:
            lemma_results: Dictionary of enhanced lemma results

        Returns:
            List of lemma names that might be problematic
        """
        problematic: List[str] = []

        for lemma_name, lemma in lemma_results.items():
            # Lemmas that failed analysis
            if lemma.status == "analysis_incomplete":
                problematic.append(lemma_name)

            # Lemmas that were falsified (might need review)
            elif lemma.status == "falsified":
                problematic.append(lemma_name)

            # Lemmas that took unusually long (potential efficiency issues)
            elif lemma.time_ms and lemma.time_ms > 30000:  # More than 30 seconds
                problematic.append(lemma_name)

            # Lemmas with many steps (potential complexity issues)
            elif lemma.steps and lemma.steps > 100:
                problematic.append(lemma_name)

        return problematic

    def get_execution_insights(
        self, lemma_results: Dict[str, EnhancedLemmaResult]
    ) -> Dict[str, str]:
        """
        Generate insights about lemma execution patterns.

        Args:
            lemma_results: Dictionary of enhanced lemma results

        Returns:
            Dictionary with insight descriptions
        """
        insights: Dict[str, str] = {}

        # Analyze timing patterns
        times = [lemma.time_ms for lemma in lemma_results.values() if lemma.time_ms]
        if times:
            avg_time = sum(times) / len(times)
            max_time = max(times)

            insights["timing"] = (
                f"Average verification time: {avg_time:.0f}ms, "
                f"Maximum: {max_time}ms"
            )

            if max_time > 10 * avg_time:
                insights["timing_warning"] = (
                    "Some lemmas took significantly longer than average. "
                    "Consider optimization or splitting complex lemmas."
                )

        # Analyze step patterns
        steps = [lemma.steps for lemma in lemma_results.values() if lemma.steps]
        if steps:
            avg_steps = sum(steps) / len(steps)
            max_steps = max(steps)

            insights["complexity"] = (
                f"Average proof steps: {avg_steps:.0f}, " f"Maximum: {max_steps}"
            )

            if max_steps > 5 * avg_steps:
                insights["complexity_warning"] = (
                    "Some lemmas required significantly more proof steps. "
                    "Review complex lemmas for potential simplification."
                )

        # Analyze failure patterns
        categorized = self.categorize_lemmas(lemma_results)
        if categorized["analysis_incomplete"]:
            incomplete_count = len(categorized["analysis_incomplete"])
            insights["incomplete"] = (
                f"{incomplete_count} lemmas had incomplete analysis. "
                f"Consider increasing timeout or memory limits."
            )

        return insights
