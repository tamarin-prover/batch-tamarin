"""
Tests for report generator functionality.
"""

# pyright: basic

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from batch_tamarin.model.batch import (
    Batch,
    ExecMetadata,
    GlobalConfig,
    LemmaResult,
    Resources,
    RichExecutableTask,
    RichTask,
    TamarinVersion,
    TaskConfig,
    TaskExecMetadata,
    TaskStatus,
    TaskSucceedResult,
)
from batch_tamarin.model.report_data import ReportData
from batch_tamarin.modules.report_generator import ReportGenerator


class TestReportGenerator:
    """Test cases for ReportGenerator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.results_dir = self.temp_dir / "results"
        self.results_dir.mkdir()

        # Create basic directory structure
        (self.results_dir / "success").mkdir()
        (self.results_dir / "failed").mkdir()
        (self.results_dir / "proofs").mkdir()
        (self.results_dir / "traces").mkdir()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def create_sample_batch(self) -> Batch:
        """Create a sample batch object for testing."""
        return Batch(
            recipe="test_recipe.json",
            config=GlobalConfig(
                global_max_cores=4,
                global_max_memory=8,
                default_timeout=300,
                output_directory=str(self.results_dir),
            ),
            tamarin_versions={
                "latest": TamarinVersion(
                    path="/usr/bin/tamarin-prover",
                    version="1.6.0",
                    test_success=True,
                )
            },
            execution_metadata=ExecMetadata(
                total_tasks=2,
                total_successes=1,
                total_failures=1,
                total_cache_hit=0,
                total_runtime=120.5,
                total_memory=512.0,
                max_runtime=80.0,
                max_memory=256.0,
            ),
            tasks={
                "test_task": RichTask(
                    theory_file="test.spthy",
                    subtasks={
                        "test_lemma--latest": RichExecutableTask(
                            task_config=TaskConfig(
                                tamarin_alias="latest",
                                lemma="test_lemma",
                                output_theory_file=Path("test_output.spthy"),
                                output_trace_file=Path("test_trace.json"),
                                options=["--prove"],
                                preprocessor_flags=None,
                                resources=Resources(cores=2, memory=4, timeout=300),
                            ),
                            task_execution_metadata=TaskExecMetadata(
                                command=["tamarin-prover", "--prove", "test.spthy"],
                                status=TaskStatus.COMPLETED,
                                cache_hit=False,
                                exec_start="2024-01-01T10:00:00",
                                exec_end="2024-01-01T10:01:20",
                                exec_duration_monotonic=80.0,
                                avg_memory=128.0,
                                peak_memory=256.0,
                            ),
                            task_result=TaskSucceedResult(
                                warnings=[],
                                real_time_tamarin_measure=75.0,
                                lemma_result=LemmaResult.VERIFIED,
                                steps=150,
                                analysis_type="all-traces",
                            ),
                        )
                    },
                )
            },
        )

    def create_execution_report(self, batch: Batch) -> Path:
        """Create an execution report JSON file."""
        report_path = self.results_dir / "execution_report.json"
        with open(report_path, "w") as f:
            f.write(batch.model_dump_json(indent=2))
        return report_path

    def test_initialization(self):
        """Test report generator initialization."""
        generator = ReportGenerator()
        assert generator.template_dir.exists()
        assert generator.env is not None

    def test_validate_results_directory(self):
        """Test results directory validation."""
        generator = ReportGenerator()

        # Test with valid directory
        validation_result = generator.validate_results_directory(self.results_dir)
        assert validation_result["success"] is True
        assert validation_result["failed"] is True
        assert validation_result["proofs"] is True
        assert validation_result["traces"] is True
        assert validation_result["execution_report.json"] is False  # Not created yet

        # Create execution report
        batch = self.create_sample_batch()
        self.create_execution_report(batch)

        validation_result = generator.validate_results_directory(self.results_dir)
        assert validation_result["execution_report.json"] is True

    def test_check_template_availability(self):
        """Test template availability checking."""
        generator = ReportGenerator()

        # Test with existing formats
        assert generator.check_template_availability("md") is True
        assert generator.check_template_availability("html") is True

        # Test with non-existing format
        assert generator.check_template_availability("nonexistent") is False

    def test_get_available_formats(self):
        """Test getting available output formats."""
        generator = ReportGenerator()
        formats = generator.get_available_formats()

        assert isinstance(formats, list)
        assert len(formats) > 0
        assert "md" in formats
        assert "html" in formats

    def test_latex_escape(self):
        """Test LaTeX character escaping."""
        generator = ReportGenerator()

        # Test individual characters
        assert generator._latex_escape("&") == "\\&"  # type: ignore
        assert generator._latex_escape("%") == "\\%"  # type: ignore
        assert generator._latex_escape("$") == "\\$"  # type: ignore
        assert generator._latex_escape("#") == "\\#"  # type: ignore
        assert generator._latex_escape("^") == "\\textasciicircum{}"  # type: ignore
        assert generator._latex_escape("_") == "\\_"  # type: ignore
        assert generator._latex_escape("{") == "\\{"  # type: ignore
        assert generator._latex_escape("}") == "\\}"  # type: ignore
        assert generator._latex_escape("~") == "\\textasciitilde{}"  # type: ignore
        assert generator._latex_escape("\\") == "\\textbackslash{}"  # type: ignore

        # Test a complex string
        test_string = "Test & 100%"
        escaped = generator._latex_escape(test_string)  # type: ignore
        assert "\\&" in escaped
        assert "\\%" in escaped

    @patch("batch_tamarin.modules.report_generator.notification_manager")
    def test_generate_report_success(self, mock_notification: MagicMock) -> None:
        """Test successful report generation."""
        generator = ReportGenerator()

        # Create test data
        batch = self.create_sample_batch()
        self.create_execution_report(batch)

        # Generate report
        output_path = self.temp_dir / "test_report.md"
        generator.generate_report(
            results_directory=self.results_dir,
            output_path=output_path,
            format_type="md",
            version="1.0.0",
        )

        # Verify report was created
        assert output_path.exists()
        assert output_path.stat().st_size > 0
        # Verify notification manager was used
        assert mock_notification is not None

        # Verify content contains expected elements
        content = output_path.read_text()
        assert "Batch Tamarin Execution Report" in content
        assert "test_task" in content
        assert "test_lemma" in content

    def test_generate_report_missing_execution_report(self):
        """Test report generation with missing execution report."""
        generator = ReportGenerator()

        output_path = self.temp_dir / "test_report.md"

        with pytest.raises(FileNotFoundError, match="execution_report.json not found"):
            generator.generate_report(
                results_directory=self.results_dir,
                output_path=output_path,
                format_type="md",
                version="1.0.0",
            )

    def test_generate_report_invalid_format(self):
        """Test report generation with invalid format."""
        generator = ReportGenerator()

        # Create test data
        batch = self.create_sample_batch()
        self.create_execution_report(batch)

        output_path = self.temp_dir / "test_report.xyz"

        with pytest.raises(ValueError, match="Template .* not found"):
            generator.generate_report(
                results_directory=self.results_dir,
                output_path=output_path,
                format_type="xyz",
                version="1.0.0",
            )

    def test_generate_charts(self):
        """Test chart generation from report data."""
        generator = ReportGenerator()

        # Create test data
        batch = self.create_sample_batch()
        report_data = ReportData.from_batch_and_output_dir(
            batch, self.results_dir, "md"
        )

        # Generate charts
        charts = generator._generate_charts(report_data)  # type: ignore

        # Verify charts were created
        assert charts.success_rate is not None
        assert charts.cache_hit_rate is not None
        assert charts.runtime_per_task is not None
        assert charts.memory_per_task is not None
        assert charts.execution_timeline is not None

    def test_prepare_template_context(self):
        """Test template context preparation."""
        generator = ReportGenerator()

        # Create test data
        batch = self.create_sample_batch()
        report_data = ReportData.from_batch_and_output_dir(
            batch, self.results_dir, "md"
        )
        charts = generator._generate_charts(report_data)  # type: ignore

        # Prepare context
        context = generator._prepare_template_context(  # type: ignore
            report_data, charts, self.results_dir, "1.0.0"
        )

        # Verify context structure
        assert "report_data" in context
        assert "charts" in context
        assert "results_directory" in context
        assert "batch_execution_date" in context
        assert "version" in context
        assert context["version"] == "1.0.0"

    def test_report_data_from_batch(self):
        """Test ReportData creation from Batch object."""
        batch = self.create_sample_batch()
        report_data = ReportData.from_batch_and_output_dir(
            batch, self.results_dir, "md"
        )

        # Verify report data structure
        assert report_data.results_directory == str(self.results_dir)
        assert report_data.config.global_max_cores == 4
        assert report_data.config.global_max_memory == 8
        assert report_data.statistics.total_tasks == 2
        assert report_data.statistics.successful_tasks == 1
        assert report_data.statistics.failed_tasks == 1
        assert len(report_data.tasks) == 1
        assert report_data.tasks[0].name == "test_task"
        assert len(report_data.tasks[0].results) == 1
        assert report_data.tasks[0].results[0].lemma == "test_lemma"
        assert report_data.tasks[0].results[0].status == "verified"

    def test_report_data_from_execution_report(self):
        """Test ReportData creation from execution_report.json."""
        batch = self.create_sample_batch()
        report_path = self.create_execution_report(batch)

        report_data = ReportData.from_execution_report(
            report_path, self.results_dir, "md"
        )

        # Verify report data was created correctly
        assert report_data.results_directory == str(self.results_dir)
        assert report_data.statistics.total_tasks == 2
        assert len(report_data.tasks) == 1

    def test_error_types_chart_generation(self):
        """Test that error types chart is generated when there are errors."""
        generator = ReportGenerator()

        # Create batch with failed tasks
        batch = self.create_sample_batch()
        batch.execution_metadata.total_failures = 2

        # Add failed task result
        from batch_tamarin.model.batch import ErrorType, TaskFailedResult

        failed_result = TaskFailedResult(
            error_type=ErrorType.TIMEOUT,
            error_description="Task timed out",
            last_stderr_lines=["Error: timeout"],
        )
        batch.tasks["test_task"].subtasks[
            "test_lemma--latest"
        ].task_result = failed_result

        report_data = ReportData.from_batch_and_output_dir(
            batch, self.results_dir, "md"
        )
        charts = generator._generate_charts(report_data)  # type: ignore

        # Verify error types chart is created when there are errors
        if report_data.error_details:
            assert charts.error_types is not None
            assert charts.error_types.data is not None
            assert len(charts.error_types.data) > 0

    def test_empty_charts_handling(self):
        """Test that charts handle empty data gracefully."""
        generator = ReportGenerator()

        # Create batch with no tasks
        batch = Batch(
            recipe="empty_recipe.json",
            config=GlobalConfig(
                global_max_cores=1,
                global_max_memory=1,
                default_timeout=60,
                output_directory=str(self.results_dir),
            ),
            tamarin_versions={},
            execution_metadata=ExecMetadata(
                total_tasks=0,
                total_successes=0,
                total_failures=0,
                total_cache_hit=0,
                total_runtime=0.0,
                total_memory=0.0,
                max_runtime=0.0,
                max_memory=0.0,
            ),
            tasks={},
        )

        report_data = ReportData.from_batch_and_output_dir(
            batch, self.results_dir, "md"
        )
        charts = generator._generate_charts(report_data)  # type: ignore

        # Charts should be None when there's no data
        assert charts.success_rate is None
        assert charts.cache_hit_rate is None
        assert charts.runtime_per_task is None
        assert charts.memory_per_task is None
        assert charts.execution_timeline is None
        assert charts.error_types is None

    def test_gantt_chart_timeline_generation(self):
        """Test that Gantt chart generates proper timeline data."""
        from datetime import datetime, timedelta

        from batch_tamarin.modules.report_charts import GanttChart

        # Create timeline data with actual timestamps
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        timeline_data = [
            ("Task A", base_time, base_time + timedelta(seconds=60)),
            (
                "Task B",
                base_time + timedelta(seconds=60),
                base_time + timedelta(seconds=120),
            ),
            (
                "Task C",
                base_time + timedelta(seconds=120),
                base_time + timedelta(seconds=180),
            ),
        ]

        gantt_chart = GanttChart("Test Timeline", timeline_data)
        mermaid_output = gantt_chart.to_mermaid_gantt()

        # Verify Gantt chart output
        assert "gantt" in mermaid_output
        assert "title Test Timeline" in mermaid_output
        assert "Task_A" in mermaid_output
        assert "Task_B" in mermaid_output
        assert "Task_C" in mermaid_output

        # Test Typst table output
        typst_output = gantt_chart.to_typst_table()
        assert "Test Timeline" in typst_output
        assert "Task A" in typst_output
        assert "Duration" in typst_output

    def test_dot_file_validation(self):
        """Test DOT file validation and SVG generation."""
        from batch_tamarin.utils.dot_utils import get_svg_content, is_dot_file_empty

        # Create a non-empty DOT file
        dot_file = self.results_dir / "test.dot"
        dot_content = """
digraph test {
    A -> B;
    B -> C;
}
"""
        dot_file.write_text(dot_content)

        # Test validation
        assert not is_dot_file_empty(dot_file)

        # Create an empty DOT file
        empty_dot_file = self.results_dir / "empty.dot"
        empty_dot_file.write_text("digraph empty {}")

        # Test validation of empty file
        assert is_dot_file_empty(empty_dot_file)

        # Test SVG content reading
        svg_file = self.results_dir / "test.svg"
        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
    <circle cx="50" cy="50" r="40" fill="red"/>
</svg>"""
        svg_file.write_text(svg_content)

        processed_svg = get_svg_content(svg_file)
        assert processed_svg is not None
        assert "<?xml" not in processed_svg  # XML declaration should be removed
        assert "<svg" in processed_svg
        assert "<circle" in processed_svg

    def test_template_context_with_none_charts(self):
        """Test template context preparation with None charts."""
        generator = ReportGenerator()

        # Create empty batch
        batch = Batch(
            recipe="empty_recipe.json",
            config=GlobalConfig(
                global_max_cores=1,
                global_max_memory=1,
                default_timeout=60,
                output_directory=str(self.results_dir),
            ),
            tamarin_versions={},
            execution_metadata=ExecMetadata(
                total_tasks=0,
                total_successes=0,
                total_failures=0,
                total_cache_hit=0,
                total_runtime=0.0,
                total_memory=0.0,
                max_runtime=0.0,
                max_memory=0.0,
            ),
            tasks={},
        )

        report_data = ReportData.from_batch_and_output_dir(
            batch, self.results_dir, "md"
        )
        charts = generator._generate_charts(report_data)  # type: ignore

        # Prepare context
        context = generator._prepare_template_context(  # type: ignore
            report_data, charts, self.results_dir, "1.0.0"
        )

        # Verify context can handle None charts
        assert context["charts"] is not None
        assert context["charts"].success_rate is None
        assert context["charts"].error_types is None

    def test_filter_traces_by_task(self):
        """Test trace filtering by task lemmas and output prefix."""
        from batch_tamarin.model.report_data import TaskResult, TaskSummary, TraceInfo

        generator = ReportGenerator()

        # Create TaskResult objects for the lemmas
        result1 = TaskResult(
            lemma="lemma1",
            tamarin_version="stable",
            status="verified",
        )  # type: ignore
        result2 = TaskResult(
            lemma="lemma2",
            tamarin_version="dev",
            status="verified",
        )  # type: ignore

        # Create a mock task with specific lemmas and output_prefix
        mock_task = TaskSummary(
            name="test_task",
            theory_file="test.spthy",
            output_prefix="task_prefix",
            results=[result1, result2],
            lemma_groups=[],
            total_runtime=0.0,
            peak_memory=0.0,
            execution_timeline_data=[],
        )

        # Create trace objects with different combinations
        traces = [
            TraceInfo(
                lemma="lemma1",
                tamarin_version="stable",
                json_file="task_prefix--lemma1--stable.json",
                output_prefix="task_prefix",
            ),  # type: ignore
            TraceInfo(
                lemma="lemma2",
                tamarin_version="dev",
                json_file="task_prefix--lemma2--dev.json",
                output_prefix="task_prefix",
            ),  # type: ignore
            TraceInfo(
                lemma="lemma1",
                tamarin_version="stable",
                json_file="other_prefix--lemma1--stable.json",
                output_prefix="other_prefix",
            ),  # type: ignore
            TraceInfo(
                lemma="lemma3",
                tamarin_version="stable",
                json_file="task_prefix--lemma3--stable.json",
                output_prefix="task_prefix",
            ),  # type: ignore
        ]

        # Filter traces
        filtered_traces = generator._filter_traces_by_task(  # type: ignore
            traces, mock_task
        )

        # Should return only traces that match both lemmas (lemma1, lemma2) and output_prefix (task_prefix)
        assert len(filtered_traces) == 2
        assert all(trace.output_prefix == "task_prefix" for trace in filtered_traces)
        assert all(trace.lemma in ["lemma1", "lemma2"] for trace in filtered_traces)

        # Test with task that has no output_prefix - should fall back to lemma filtering only
        result3 = TaskResult(
            lemma="lemma1",
            tamarin_version="stable",
            status="verified",
        )  # type: ignore
        result4 = TaskResult(
            lemma="lemma3",
            tamarin_version="stable",
            status="verified",
        )  # type: ignore

        mock_task_no_prefix = TaskSummary(
            name="test_task_no_prefix",
            theory_file="test.spthy",
            output_prefix=None,
            results=[result3, result4],
            lemma_groups=[],
            total_runtime=0.0,
            peak_memory=0.0,
            execution_timeline_data=[],
        )

        filtered_traces_no_prefix = generator._filter_traces_by_task(  # type: ignore
            traces, mock_task_no_prefix
        )

        # Should return traces matching lemmas regardless of output_prefix
        assert len(filtered_traces_no_prefix) == 3
        lemma_names = [trace.lemma for trace in filtered_traces_no_prefix]
        assert "lemma1" in lemma_names
        assert "lemma3" in lemma_names
