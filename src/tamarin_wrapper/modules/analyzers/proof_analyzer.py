"""
Proof analyzer for analyzing proof methods and structures.

This module analyzes proof information from spthy files to understand
proof techniques and provide insights about proof complexity.
"""

from typing import Any, Dict, List

from ...model.output_models import SpthyAnalysis


class ProofAnalyzer:
    """
    Analyzes proof structures and methods from spthy files.
    """

    def analyze_proof_methods(self, spthy_analysis: SpthyAnalysis) -> Dict[str, int]:
        """
        Analyze the distribution of proof methods used.

        Args:
            spthy_analysis: Analysis results from spthy file

        Returns:
            Dictionary mapping proof methods to their usage counts
        """
        method_counts: Dict[str, int] = {}

        for lemma in spthy_analysis.lemmas.values():
            method = lemma.proof_method or "automatic"
            method_counts[method] = method_counts.get(method, 0) + 1

        return method_counts

    def analyze_proof_completeness(
        self, spthy_analysis: SpthyAnalysis
    ) -> Dict[str, int]:
        """
        Analyze proof completeness across all lemmas.

        Args:
            spthy_analysis: Analysis results from spthy file

        Returns:
            Dictionary with completeness statistics
        """
        completeness = {"proven": 0, "unproven": 0, "sorry": 0, "failed": 0}

        for lemma in spthy_analysis.lemmas.values():
            status = lemma.proof_status
            if status in completeness:
                completeness[status] += 1
            else:
                completeness["unproven"] += 1

        return completeness

    def identify_proof_patterns(self, spthy_analysis: SpthyAnalysis) -> List[str]:
        """
        Identify common proof patterns and techniques.

        Args:
            spthy_analysis: Analysis results from spthy file

        Returns:
            List of identified proof patterns
        """
        patterns: List[str] = []

        # Analyze proof methods
        method_counts = self.analyze_proof_methods(spthy_analysis)

        if method_counts.get("automatic", 0) > len(spthy_analysis.lemmas) * 0.5:
            patterns.append("Heavy reliance on automatic proof search")

        if method_counts.get("induction", 0) > 0:
            patterns.append("Uses inductive proof techniques")

        if method_counts.get("cases", 0) > 0:
            patterns.append("Uses case-based proof analysis")

        if method_counts.get("sorry", 0) > 0:
            patterns.append(f"Contains {method_counts['sorry']} incomplete proofs")

        # Analyze lemma attributes
        attribute_counts = self._analyze_lemma_attributes(spthy_analysis)

        if attribute_counts.get("sources", 0) > 0:
            patterns.append("Uses source lemmas for composition")

        if attribute_counts.get("reuse", 0) > 0:
            patterns.append("Reuses existing proof results")

        return patterns

    def assess_proof_complexity(self, spthy_analysis: SpthyAnalysis) -> Dict[str, Any]:
        """
        Assess the overall complexity of proofs in the theory.

        Args:
            spthy_analysis: Analysis results from spthy file

        Returns:
            Dictionary with complexity assessment
        """
        complexity_assessment: Dict[str, Any] = {
            "total_lemmas": len(spthy_analysis.lemmas),
            "complexity_score": 0.0,
            "complexity_factors": [],
            "recommendations": [],
        }

        if not spthy_analysis.lemmas:
            return complexity_assessment

        # Calculate complexity factors
        proven_count = sum(
            1
            for lemma in spthy_analysis.lemmas.values()
            if lemma.proof_status == "proven"
        )
        sorry_count = sum(
            1
            for lemma in spthy_analysis.lemmas.values()
            if lemma.proof_method == "sorry"
        )

        # Base complexity score
        complexity_score = 0.0

        # Factor 1: Proof completeness (lower is more complex)
        completeness_ratio = proven_count / len(spthy_analysis.lemmas)
        if completeness_ratio < 0.5:
            complexity_score += 3.0
            complexity_assessment["complexity_factors"].append(
                f"Low proof completeness ({completeness_ratio:.1%})"
            )
        elif completeness_ratio < 0.8:
            complexity_score += 1.0
            complexity_assessment["complexity_factors"].append(
                f"Moderate proof completeness ({completeness_ratio:.1%})"
            )

        # Factor 2: Sorry count (indicates difficult proofs)
        if sorry_count > 0:
            sorry_ratio = sorry_count / len(spthy_analysis.lemmas)
            complexity_score += sorry_ratio * 2.0
            complexity_assessment["complexity_factors"].append(
                f"Contains {sorry_count} incomplete proofs"
            )

        # Factor 3: Proof method diversity
        method_counts = self.analyze_proof_methods(spthy_analysis)
        if len(method_counts) > 3:
            complexity_score += 1.0
            complexity_assessment["complexity_factors"].append(
                "Uses diverse proof methods"
            )

        # Factor 4: Theory size
        if len(spthy_analysis.lemmas) > 20:
            complexity_score += 1.0
            complexity_assessment["complexity_factors"].append(
                f"Large theory with {len(spthy_analysis.lemmas)} lemmas"
            )

        complexity_assessment["complexity_score"] = min(complexity_score, 10.0)

        # Generate recommendations
        complexity_assessment["recommendations"] = (
            self._generate_complexity_recommendations(
                complexity_assessment, method_counts, sorry_count
            )
        )

        return complexity_assessment

    def find_proof_dependencies(
        self, spthy_analysis: SpthyAnalysis
    ) -> Dict[str, List[str]]:
        """
        Identify potential dependencies between lemmas.

        Args:
            spthy_analysis: Analysis results from spthy file

        Returns:
            Dictionary mapping lemma names to their potential dependencies
        """
        dependencies: Dict[str, List[str]] = {}

        # Look for lemmas with "sources" attribute
        for lemma_name, lemma in spthy_analysis.lemmas.items():
            deps: List[str] = []

            if "sources" in lemma.attributes:
                # This lemma might depend on other "source" lemmas
                for other_name, other_lemma in spthy_analysis.lemmas.items():
                    if (
                        other_name != lemma_name
                        and other_lemma.proof_status == "proven"
                        and other_lemma.analysis_type == "all-traces"
                    ):
                        deps.append(other_name)

            if deps:
                dependencies[lemma_name] = deps

        return dependencies

    def _analyze_lemma_attributes(
        self, spthy_analysis: SpthyAnalysis
    ) -> Dict[str, int]:
        """Analyze the distribution of lemma attributes."""
        attribute_counts: Dict[str, int] = {}

        for lemma in spthy_analysis.lemmas.values():
            for attr in lemma.attributes:
                # Clean attribute (remove brackets)
                clean_attr = attr.strip("[]")
                attribute_counts[clean_attr] = attribute_counts.get(clean_attr, 0) + 1

        return attribute_counts

    def _generate_complexity_recommendations(
        self,
        assessment: Dict[str, Any],
        method_counts: Dict[str, int],
        sorry_count: int,
    ) -> List[str]:
        """Generate recommendations based on complexity assessment."""
        recommendations: List[str] = []

        complexity_score = assessment["complexity_score"]

        if complexity_score > 5.0:
            recommendations.append(
                "High complexity detected. Consider breaking down complex lemmas."
            )

        if sorry_count > 0:
            recommendations.append(
                f"Complete {sorry_count} unfinished proofs for better verification."
            )

        if method_counts.get("automatic", 0) == len(assessment.get("total_lemmas", 0)):
            recommendations.append(
                "All proofs use automatic search. Consider manual proof guidance for complex lemmas."
            )

        if complexity_score > 3.0:
            recommendations.append(
                "Consider using helper lemmas to simplify complex proofs."
            )

        return recommendations

    def generate_proof_report(self, spthy_analysis: SpthyAnalysis) -> Dict[str, Any]:
        """
        Generate comprehensive proof analysis report.

        Args:
            spthy_analysis: Analysis results from spthy file

        Returns:
            Comprehensive proof analysis report
        """
        if not spthy_analysis.lemmas:
            return {"error": "No lemmas found in spthy analysis"}

        return {
            "theory_name": spthy_analysis.theory_name,
            "total_lemmas": len(spthy_analysis.lemmas),
            "proof_methods": self.analyze_proof_methods(spthy_analysis),
            "proof_completeness": self.analyze_proof_completeness(spthy_analysis),
            "proof_patterns": self.identify_proof_patterns(spthy_analysis),
            "complexity_assessment": self.assess_proof_complexity(spthy_analysis),
            "proof_dependencies": self.find_proof_dependencies(spthy_analysis),
            "recommendations": self._generate_overall_recommendations(spthy_analysis),
        }

    def _generate_overall_recommendations(
        self, spthy_analysis: SpthyAnalysis
    ) -> List[str]:
        """Generate overall recommendations for the theory."""
        recommendations: List[str] = []

        completeness = self.analyze_proof_completeness(spthy_analysis)
        total_lemmas = len(spthy_analysis.lemmas)

        # Completeness recommendations
        if completeness["unproven"] > total_lemmas * 0.3:
            recommendations.append(
                "Consider completing more proofs to increase confidence in results."
            )

        if completeness["sorry"] > 0:
            recommendations.append(
                "Replace 'sorry' placeholders with actual proofs for production use."
            )

        # Method diversity recommendations
        methods = self.analyze_proof_methods(spthy_analysis)
        if len(methods) == 1 and "automatic" in methods:
            recommendations.append(
                "Consider using manual proof techniques for better control over complex lemmas."
            )

        return recommendations
