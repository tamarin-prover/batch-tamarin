"""Report command for generating execution reports."""

from pathlib import Path

from ..utils.notifications import notification_manager


class ReportCommand:
    """Report command for generating execution reports."""

    @staticmethod
    def run(
        results_directory: Path,
        output: Path,
        format_type: str,
    ) -> None:
        """Execute the report generation command."""
        # Input directory validation
        if not results_directory.is_dir():
            raise ValueError(
                f"Results directory '{results_directory}' does not exist or is not a directory."
            )
        expected_items = {
            "success": (results_directory / "success").is_dir(),
            "failed": (results_directory / "failed").is_dir(),
            "proofs": (results_directory / "proofs").is_dir(),
            "traces": (results_directory / "traces").is_dir(),
            "execution_report.json": (
                results_directory / "execution_report.json"
            ).is_file(),
        }
        missing = [name for name, exists in expected_items.items() if not exists]
        if len(missing) == len(expected_items):
            raise ValueError(
                f"Results directory '{results_directory}' is missing all expected items: "
                f"{', '.join(expected_items.keys())}."
            )
        if missing:
            notification_manager.warning(
                f"Results directory '{results_directory}' is missing expected items: "
                f"{', '.join(missing)}. The report may be incomplete."
            )

        # Format type validation
        if format_type not in ["md", "html", "tex", "typ"]:
            raise ValueError(
                f"Unsupported format type '{format_type}'. Supported formats are: md, html, tex, typ."
            )

        # Output file validation
        if not output.suffix:
            output = output.with_suffix(f".{format_type}")
        if (
            output.suffix not in [".md", ".html", ".tex", ".typ"]
            or output.suffix != f".{format_type}"
        ):
            notification_manager.warning(
                f"Output file {output} have a different suffix ({output.suffix}) than the specified format type '{format_type}'."
            )
        output.parent.mkdir(parents=True, exist_ok=True)

        print(
            f"Generating report from {results_directory} to {output.absolute()} in {format_type} format"
        )
        raise Exception("Report generation not implemented yet")
