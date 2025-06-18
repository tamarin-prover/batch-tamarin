"""
Stdout parser for Tamarin output using regex patterns.

This module implements regex-based parsing of Tamarin stdout to extract
lemma results, processing information, and warnings.
"""

import re
from typing import Dict, List, Optional

from ...model.output_models import LemmaResult, StdoutAnalysis


class StdoutParser:
    """
    Enhanced stdout parser with comprehensive pattern matching.
    """

    # Enhanced regex patterns based on Tamarin output specifications
    PATTERNS = {
        "summary_section": re.compile(
            r"==============================================================================\n"
            r"summary of summaries:(.*?)"
            r"(?:==============================================================================|$)",
            re.DOTALL,
        ),
        "tool_version_warning": re.compile(
            r"(.*maude tool version.*behind.*tamarin binary.*)", re.IGNORECASE
        ),
        "analyzed_file": re.compile(r"analyzed:\s+(.+)"),
        "output_file": re.compile(r"output:\s+(.+)"),
        "processing_time": re.compile(r"processing time:\s+([\d.]+)s"),
        "warnings": re.compile(r"WARNING:\s+(.+?)(?=\n|$)", re.MULTILINE),
        "wellformedness_warning": re.compile(
            r"WARNING:\s+(\d+)\s+wellformedness check.*failed.*analysis results.*wrong",
            re.IGNORECASE | re.DOTALL,
        ),
        "lemma_result": re.compile(
            r"(\w+)\s+\((all-traces|exists-trace)\):\s+"
            r"(verified|falsified|analysis incomplete)\s+"
            r"\((\d+)\s+steps?\)"
        ),
        "lemma_result_with_time": re.compile(
            r"(\w+)\s+\((all-traces|exists-trace)\):\s+"
            r"(verified|falsified|analysis incomplete)\s+"
            r"\((\d+)\s+steps?,\s+(\d+)ms\)"
        ),
    }

    def parse(self, stdout: str) -> StdoutAnalysis:
        """
        Parse stdout and extract structured information.

        Args:
            stdout: Raw stdout string from Tamarin execution

        Returns:
            StdoutAnalysis containing parsed information
        """
        # Extract basic file information
        analyzed_file = self._extract_analyzed_file(stdout)
        output_file = self._extract_output_file(stdout)
        processing_time = self._extract_processing_time(stdout)

        # Extract warnings
        warnings = self._extract_warnings(stdout)

        # Extract version warnings
        maude_version_warning = self._detect_version_warnings(stdout)

        # Extract lemma results
        lemma_results = self._parse_lemma_results(stdout)

        return StdoutAnalysis(
            analyzed_file=analyzed_file or "unknown",
            output_file=output_file or "unknown",
            processing_time=processing_time or 0.0,
            warnings=warnings,
            lemma_results=lemma_results,
            maude_version_warning=maude_version_warning,
            tool_version_info=None,  # Can be enhanced later
        )

    def _extract_summary_section(self, stdout: str) -> Optional[str]:
        """Extract the summary of summaries section."""
        match = self.PATTERNS["summary_section"].search(stdout)
        return match.group(1).strip() if match else None

    def _extract_analyzed_file(self, stdout: str) -> Optional[str]:
        """Extract the analyzed file path."""
        match = self.PATTERNS["analyzed_file"].search(stdout)
        return match.group(1).strip() if match else None

    def _extract_output_file(self, stdout: str) -> Optional[str]:
        """Extract the output file path."""
        match = self.PATTERNS["output_file"].search(stdout)
        return match.group(1).strip() if match else None

    def _extract_processing_time(self, stdout: str) -> Optional[float]:
        """Extract the processing time in seconds."""
        match = self.PATTERNS["processing_time"].search(stdout)
        return float(match.group(1)) if match else None

    def _extract_warnings(self, stdout: str) -> List[str]:
        """Extract all warning messages."""
        warnings: List[str] = []

        # Extract general warnings
        for match in self.PATTERNS["warnings"].finditer(stdout):
            warning = match.group(1).strip()
            if warning:
                warnings.append(warning)

        # Check for wellformedness warnings specifically
        wellformedness_match = self.PATTERNS["wellformedness_warning"].search(stdout)
        if wellformedness_match:
            count = wellformedness_match.group(1)
            warning = f"{count} wellformedness check failed! The analysis results might be wrong!"
            if warning not in warnings:
                warnings.append(warning)

        return warnings

    def _parse_lemma_results(self, stdout: str) -> Dict[str, LemmaResult]:
        """
        Parse lemma results from stdout.

        Handles both formats:
        - lemma_name (all-traces): verified (8 steps)
        - lemma_name (exists-trace): falsified (3 steps, 1500ms)
        """
        lemma_results: Dict[str, LemmaResult] = {}

        # Try pattern with timing information first
        for match in self.PATTERNS["lemma_result_with_time"].finditer(stdout):
            name = match.group(1)
            analysis_type = match.group(2)
            status = match.group(3)
            steps = int(match.group(4))
            time_ms = int(match.group(5))

            # Normalize status
            normalized_status = self._normalize_status(status)

            lemma_results[name] = LemmaResult(
                name=name,
                status=normalized_status,
                analysis_type=analysis_type,
                steps=steps,
                time_ms=time_ms,
            )

        # Then try pattern without timing information
        for match in self.PATTERNS["lemma_result"].finditer(stdout):
            name = match.group(1)
            # Skip if already found with timing info
            if name in lemma_results:
                continue

            analysis_type = match.group(2)
            status = match.group(3)
            steps = int(match.group(4))

            # Normalize status
            normalized_status = self._normalize_status(status)

            lemma_results[name] = LemmaResult(
                name=name,
                status=normalized_status,
                analysis_type=analysis_type,
                steps=steps,
                time_ms=None,
            )

        return lemma_results

    def _normalize_status(self, status: str) -> str:
        """Normalize lemma status strings."""
        status_lower = status.lower()
        if status_lower == "verified":
            return "verified"
        elif status_lower == "falsified":
            return "falsified"
        elif "incomplete" in status_lower:
            return "analysis_incomplete"
        else:
            return status_lower

    def _detect_version_warnings(self, stdout: str) -> Optional[str]:
        """Detect and categorize version-related warnings."""
        match = self.PATTERNS["tool_version_warning"].search(stdout)
        return match.group(1).strip() if match else None
