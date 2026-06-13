"""
Tests for the run command.

This module tests task filtering and execution orchestration in the run command.
External dependencies are mocked for CI compatibility.
"""

# pyright: basic

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from batch_tamarin.commands.run import process_config_file
from batch_tamarin.model.executable_task import ExecutableTask
from batch_tamarin.model.tamarin_recipe import TamarinRecipe


@pytest.fixture
def mock_executable_tasks() -> list[ExecutableTask]:
    """Create mock executable tasks with predictable generated task names."""
    return [
        ExecutableTask(
            task_name="alpha--lemma_a--stable",
            original_task_name="alpha",
            tamarin_version_name="stable",
            tamarin_executable=Path("/mock/tamarin-prover"),
            theory_file=Path("/mock/theory.spthy"),
            output_file=Path("/mock/output1.txt"),
            lemma="lemma_a",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=2,
            max_memory=4,
            task_timeout=1800,
            traces_dir=Path("/mock/traces"),
        ),
        ExecutableTask(
            task_name="alpha--lemma_b--dev",
            original_task_name="alpha",
            tamarin_version_name="dev",
            tamarin_executable=Path("/mock/tamarin-prover"),
            theory_file=Path("/mock/theory.spthy"),
            output_file=Path("/mock/output2.txt"),
            lemma="lemma_b",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=2,
            max_memory=4,
            task_timeout=1800,
            traces_dir=Path("/mock/traces"),
        ),
        ExecutableTask(
            task_name="beta--lemma_a--stable",
            original_task_name="beta",
            tamarin_version_name="stable",
            tamarin_executable=Path("/mock/tamarin-prover"),
            theory_file=Path("/mock/theory.spthy"),
            output_file=Path("/mock/output3.txt"),
            lemma="lemma_a",
            tamarin_options=None,
            preprocess_flags=None,
            max_cores=2,
            max_memory=4,
            task_timeout=1800,
            traces_dir=Path("/mock/traces"),
        ),
    ]


@pytest.fixture
def mock_recipe() -> TamarinRecipe:
    """Create a minimal mock recipe."""
    return TamarinRecipe.model_validate(
        {
            "config": {
                "global_max_cores": 8,
                "global_max_memory": 16,
                "default_timeout": 3600,
                "output_directory": "./test-results",
            },
            "tamarin_versions": {
                "stable": {"path": "/mock/tamarin-prover", "version": "1.10.0"}
            },
            "tasks": {
                "alpha": {
                    "theory_file": "/mock/theory.spthy",
                    "tamarin_versions": ["stable"],
                    "output_file_prefix": "alpha",
                }
            },
        }
    )


@pytest.mark.asyncio
async def test_process_config_file_without_filter(
    mock_recipe: TamarinRecipe,
    mock_executable_tasks: list[ExecutableTask],
    tmp_path: Path,
) -> None:
    """Test that all tasks are executed when no task prefix is provided."""
    config_path = tmp_path / "recipe.json"
    config_path.write_text("{}")

    with patch("batch_tamarin.commands.run.ConfigManager") as mock_config_manager_cls:
        config_manager = MagicMock()
        config_manager.load_json_recipe = AsyncMock(return_value=mock_recipe)
        config_manager.recipe_to_executable_tasks.return_value = mock_executable_tasks
        mock_config_manager_cls.return_value = config_manager

        with patch("batch_tamarin.commands.run.TaskRunner") as mock_runner_cls:
            runner = MagicMock()
            runner.execute_all_tasks = AsyncMock()
            mock_runner_cls.return_value = runner

            with patch(
                "batch_tamarin.commands.run.BatchManager"
            ) as mock_batch_manager_cls:
                batch_manager = MagicMock()
                batch_manager.generate_execution_report = AsyncMock()
                mock_batch_manager_cls.return_value = batch_manager

                await process_config_file(config_path)

    runner.execute_all_tasks.assert_awaited_once()
    executed_tasks = runner.execute_all_tasks.await_args[0][0]
    assert len(executed_tasks) == 3


@pytest.mark.asyncio
async def test_process_config_file_with_prefix_filter(
    mock_recipe: TamarinRecipe,
    mock_executable_tasks: list[ExecutableTask],
    tmp_path: Path,
) -> None:
    """Test that only tasks matching the prefix are executed."""
    config_path = tmp_path / "recipe.json"
    config_path.write_text("{}")

    with patch("batch_tamarin.commands.run.ConfigManager") as mock_config_manager_cls:
        config_manager = MagicMock()
        config_manager.load_json_recipe = AsyncMock(return_value=mock_recipe)
        config_manager.recipe_to_executable_tasks.return_value = mock_executable_tasks
        mock_config_manager_cls.return_value = config_manager

        with patch("batch_tamarin.commands.run.TaskRunner") as mock_runner_cls:
            runner = MagicMock()
            runner.execute_all_tasks = AsyncMock()
            mock_runner_cls.return_value = runner

            with patch(
                "batch_tamarin.commands.run.BatchManager"
            ) as mock_batch_manager_cls:
                batch_manager = MagicMock()
                batch_manager.generate_execution_report = AsyncMock()
                mock_batch_manager_cls.return_value = batch_manager

                await process_config_file(config_path, task_name="alpha")

    executed_tasks = runner.execute_all_tasks.await_args[0][0]
    assert len(executed_tasks) == 2
    assert all(task.task_name.startswith("alpha") for task in executed_tasks)


@pytest.mark.asyncio
async def test_process_config_file_with_no_matching_prefix(
    mock_recipe: TamarinRecipe,
    mock_executable_tasks: list[ExecutableTask],
    tmp_path: Path,
) -> None:
    """Test that an unmatched prefix results in an empty task list."""
    config_path = tmp_path / "recipe.json"
    config_path.write_text("{}")

    with patch("batch_tamarin.commands.run.ConfigManager") as mock_config_manager_cls:
        config_manager = MagicMock()
        config_manager.load_json_recipe = AsyncMock(return_value=mock_recipe)
        config_manager.recipe_to_executable_tasks.return_value = mock_executable_tasks
        mock_config_manager_cls.return_value = config_manager

        with patch("batch_tamarin.commands.run.TaskRunner") as mock_runner_cls:
            runner = MagicMock()
            runner.execute_all_tasks = AsyncMock()
            mock_runner_cls.return_value = runner

            with patch(
                "batch_tamarin.commands.run.BatchManager"
            ) as mock_batch_manager_cls:
                batch_manager = MagicMock()
                batch_manager.generate_execution_report = AsyncMock()
                mock_batch_manager_cls.return_value = batch_manager

                await process_config_file(config_path, task_name="gamma")

    executed_tasks = runner.execute_all_tasks.await_args[0][0]
    assert len(executed_tasks) == 0
