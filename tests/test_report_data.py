"""Test module for report data functionality."""

# pyright: basic

import json
from pathlib import Path

import pytest

from batch_tamarin.model.batch import Batch
from batch_tamarin.model.report_data import ReportData


class TestReportData:
    """Test cases for ReportData class."""

    @pytest.fixture
    def example_report_path(self) -> Path:
        """Fixture for example execution report path."""
        return Path("tests/fixtures/complete-example-results/execution_report.json")

    @pytest.fixture
    def example_output_dir(self) -> Path:
        """Fixture for example output directory."""
        return Path("tests/fixtures/complete-example-results")

    def test_from_execution_report_success(
        self, example_report_path: Path, example_output_dir: Path
    ) -> None:
        """Test successful creation of ReportData from execution report."""
        if not example_report_path.exists():
            pytest.skip("Example file not found")

        report_data = ReportData.from_execution_report(
            example_report_path, example_output_dir, format_type="md"
        )

        assert report_data is not None
        assert report_data.statistics.total_tasks == 17
        assert report_data.statistics.successful_tasks == 14
        assert report_data.statistics.failed_tasks == 3
        assert len(report_data.tasks) == 8

    def test_from_batch_and_output_dir_success(
        self, example_report_path: Path, example_output_dir: Path
    ) -> None:
        """Test successful creation of ReportData from Batch object."""
        if not example_report_path.exists():
            pytest.skip("Example file not found")

        # Load batch from JSON
        with open(example_report_path, "r", encoding="utf-8") as f:
            batch_data = json.load(f)
        batch = Batch.model_validate(batch_data)

        report_data = ReportData.from_batch_and_output_dir(
            batch, example_output_dir, format_type="md"
        )

        assert report_data is not None
        assert report_data.statistics.total_tasks == 17
        assert report_data.statistics.successful_tasks == 14
        assert report_data.statistics.failed_tasks == 3
        assert len(report_data.tasks) == 8

    def test_report_data_attributes(
        self, example_report_path: Path, example_output_dir: Path
    ) -> None:
        """Test that ReportData has all expected attributes."""
        if not example_report_path.exists():
            pytest.skip("Example file not found")

        report_data = ReportData.from_execution_report(
            example_report_path, example_output_dir, format_type="md"
        )

        # Check all expected attributes exist
        assert hasattr(report_data, "config")
        assert hasattr(report_data, "statistics")
        assert hasattr(report_data, "tasks")
        assert hasattr(report_data, "traces")
        assert hasattr(report_data, "error_details")

        # Check statistics have expected computed fields
        assert hasattr(report_data.statistics, "successful_tasks_percentage")
        assert 0 <= report_data.statistics.successful_tasks_percentage <= 100

    def test_task_data_extraction(
        self, example_report_path: Path, example_output_dir: Path
    ) -> None:
        """Test that task data is correctly extracted."""
        if not example_report_path.exists():
            pytest.skip("Example file not found")

        report_data = ReportData.from_execution_report(
            example_report_path, example_output_dir, format_type="md"
        )

        # Check that tasks have expected structure
        for task in report_data.tasks:
            assert task.name is not None
            assert task.theory_file is not None
            assert isinstance(task.lemmas, list)
            assert isinstance(task.tamarin_versions, list)
            assert isinstance(task.results, list)

            # Check each result
            for result in task.results:
                assert result.lemma is not None
                assert result.tamarin_version is not None
                assert result.status is not None
