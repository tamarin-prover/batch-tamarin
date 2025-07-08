"""
Pytest configuration and shared fixtures for batch-tamarin tests.

This module provides common test fixtures and configuration for testing
the batch-tamarin package, including mock data and helper utilities.
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Tuple

import pytest
from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture
def tmp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def sample_theory_file(tmp_dir: Path) -> Path:
    """Create a sample .spthy theory file with lemmas."""
    theory_content = """
theory TestTheory
begin

// Sample lemma definitions
lemma test_lemma_1:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

lemma test_lemma_2:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

lemma different_lemma:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

lemma success_lemma:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

end
"""
    theory_file = tmp_dir / "test_theory.spthy"
    theory_file.write_text(theory_content)
    return theory_file


@pytest.fixture
def sample_tamarin_executable(tmp_dir: Path) -> Path:
    """Create a mock tamarin executable file."""
    tamarin_exe = tmp_dir / "tamarin-prover"
    tamarin_exe.write_text("#!/bin/bash\necho 'mock tamarin'")
    tamarin_exe.chmod(0o755)
    return tamarin_exe


@pytest.fixture
def minimal_recipe_data(
    sample_theory_file: Path, sample_tamarin_executable: Path
) -> Dict[str, Any]:
    """Create minimal valid recipe data."""
    return {
        "config": {
            "global_max_cores": 8,
            "global_max_memory": 16,
            "default_timeout": 3600,
            "output_directory": "./test-results",
        },
        "tamarin_versions": {"stable": {"path": str(sample_tamarin_executable)}},
        "tasks": {
            "test_task": {
                "theory_file": str(sample_theory_file),
                "tamarin_versions": ["stable"],
                "output_file_prefix": "test_task",
            }
        },
    }


@pytest.fixture
def complex_recipe_data(
    sample_theory_file: Path, sample_tamarin_executable: Path
) -> Dict[str, Any]:
    """Create complex recipe data with multiple configurations."""
    return {
        "config": {
            "global_max_cores": 16,
            "global_max_memory": 32,
            "default_timeout": 7200,
            "output_directory": "./complex-results",
        },
        "tamarin_versions": {
            "stable": {"path": str(sample_tamarin_executable), "version": "1.10.0"},
            "dev": {"path": str(sample_tamarin_executable), "version": "1.11.0"},
        },
        "tasks": {
            "full_task": {
                "theory_file": str(sample_theory_file),
                "tamarin_versions": ["stable", "dev"],
                "output_file_prefix": "full_task",
                "tamarin_options": ["--heuristic=S"],
                "preprocess_flags": ["FLAG1", "FLAG2"],
                "resources": {"max_cores": 8, "max_memory": 16, "timeout": 1800},
            },
            "lemma_specific_task": {
                "theory_file": str(sample_theory_file),
                "tamarin_versions": ["stable"],
                "output_file_prefix": "lemma_task",
                "lemmas": [
                    {
                        "name": "test_lemma",
                        "tamarin_versions": ["dev"],
                        "resources": {"max_cores": 4, "max_memory": 8, "timeout": 900},
                    },
                    {
                        "name": "different_lemma",
                        "tamarin_options": ["--diff"],
                        "preprocess_flags": ["FLAG3"],
                    },
                ],
            },
        },
    }


@pytest.fixture
def inheritance_recipe_data(
    sample_theory_file: Path, sample_tamarin_executable: Path
) -> Dict[str, Any]:
    """Create recipe data with inheritance."""
    return {
        "config": {
            "global_max_cores": 8,
            "global_max_memory": 16,
            "default_timeout": 3600,
            "output_directory": "./inherited-results",
        },
        "tamarin_versions": {"stable": {"path": str(sample_tamarin_executable)}},
        "tasks": {
            "base_task": {
                "theory_file": str(sample_theory_file),
                "tamarin_versions": ["stable"],
                "output_file_prefix": "base_task",
                "resources": {"max_cores": 3},
                "lemmas": [
                    {
                        "name": "test_lemma",
                        "tamarin_versions": ["stable"],
                        "resources": {"max_memory": 4, "timeout": 1200},
                    }
                ],
            },
        },
    }


@pytest.fixture
def invalid_recipe_data() -> Dict[str, Any]:
    """Create invalid recipe data for testing error handling."""
    return {
        "config": {
            "global_max_cores": 8,
            "global_max_memory": 16,
            "default_timeout": 3600,
            "output_directory": "./test-results",
        },
        "tamarin_versions": {"stable": {"path": "/nonexistent/tamarin-prover"}},
        "tasks": {
            "test_task": {
                "theory_file": "/nonexistent/theory.spthy",
                "tamarin_versions": ["stable"],
                "output_file_prefix": "test_task",
            }
        },
    }


@pytest.fixture
def create_json_file(tmp_dir: Path) -> Callable[..., Path]:
    """Helper function to create JSON config files."""

    def _create_json_file(data: Dict[str, Any], filename: str = "config.json") -> Path:
        file_path = tmp_dir / filename
        file_path.write_text(json.dumps(data, indent=2))
        return file_path

    return _create_json_file


@pytest.fixture
def mock_notifications(monkeypatch: MonkeyPatch):
    """Mock the notification manager to capture notifications during tests."""

    class MockNotificationManager:
        def __init__(self) -> None:
            self.messages: List[Tuple[str, str]] = []

        def debug(self, message: str) -> None:
            self.messages.append(("debug", message))

        def info(self, message: str) -> None:
            self.messages.append(("info", message))

        def success(self, message: str) -> None:
            self.messages.append(("success", message))

        def warning(self, message: str) -> None:
            self.messages.append(("warning", message))

        def error(self, message: str) -> None:
            self.messages.append(("error", message))

        def critical(self, message: str) -> None:
            self.messages.append(("critical", message))

        def phase_separator(self, message: str) -> None:
            self.messages.append(("phase_separator", message))

    mock_manager = MockNotificationManager()
    monkeypatch.setattr(
        "batch_tamarin.modules.config_manager.notification_manager", mock_manager
    )
    return mock_manager


@pytest.fixture
def setup_output_manager(tmp_dir: Path, monkeypatch: MonkeyPatch) -> Any:
    """Setup output manager with temporary directory."""
    # Create temporary output directories
    output_dir = tmp_dir / "test-results"
    output_dir.mkdir(exist_ok=True)

    # Mock the output manager's get_output_paths to use our temp directory
    from batch_tamarin.modules.output_manager import output_manager

    def mock_get_output_paths() -> Dict[str, Path]:
        models_dir = output_dir / "models"
        success_dir = output_dir / "success"
        failed_dir = output_dir / "failed"
        traces_dir = output_dir / "traces"

        # Create directories
        models_dir.mkdir(exist_ok=True)
        success_dir.mkdir(exist_ok=True)
        failed_dir.mkdir(exist_ok=True)
        traces_dir.mkdir(exist_ok=True)

        return {
            "models": models_dir,
            "success": success_dir,
            "failed": failed_dir,
            "traces": traces_dir,
        }

    monkeypatch.setattr(output_manager, "get_output_paths", mock_get_output_paths)
    return output_manager
