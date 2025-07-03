"""
Integration tests for batch-tamarin.

These tests verify the complete workflow from JSON recipe loading
to ExecutableTask generation, ensuring all components work together correctly.
"""

from pathlib import Path
from typing import Any, Callable, Dict

import pytest

from batch_tamarin.model.executable_task import ExecutableTask
from batch_tamarin.modules.config_manager import ConfigManager


@pytest.mark.asyncio
async def test_minimal_recipe_end_to_end(
    minimal_recipe_data: Dict[str, Any],
    create_json_file: Callable[..., Path],
    mock_notifications: Any,
    setup_output_manager: Any,
) -> None:
    """Test complete workflow with minimal recipe configuration."""
    # Create JSON config file
    config_file = create_json_file(minimal_recipe_data)

    # Load recipe
    recipe = await ConfigManager.load_json_recipe(config_file)

    # Verify recipe structure
    assert recipe.config.global_max_cores == 8
    assert recipe.config.global_max_memory == 16
    assert recipe.config.default_timeout == 3600
    assert "stable" in recipe.tamarin_versions
    assert "test_task" in recipe.tasks

    # Convert to executable tasks
    executable_tasks = ConfigManager.recipe_to_executable_tasks(recipe)

    # Verify executable tasks were generated
    assert len(executable_tasks) == 4  # 4 lemmas from the theory file

    # Verify all tasks are properly configured
    for task in executable_tasks:
        assert isinstance(task, ExecutableTask)
        assert task.tamarin_version_name == "stable"
        assert task.theory_file.name == "test_theory.spthy"
        assert task.task_name.startswith("test_task--")
        assert task.max_cores == 4  # default from Resources
        assert task.max_memory == 16  # default from Resources
        assert task.task_timeout == 3600  # from global config
        assert task.lemma in [
            "test_lemma_1",
            "test_lemma_2",
            "different_lemma",
            "success_lemma",
        ]

        # Verify command generation
        command = task.to_command()
        assert len(command) > 0
        assert "+RTS" in command
        assert "-N4" in command
        assert "-RTS" in command
        assert f"--prove={task.lemma}" in command
        assert "--output=" in " ".join(command)


@pytest.mark.asyncio
async def test_complex_recipe_end_to_end(
    complex_recipe_data: Dict[str, Any],
    create_json_file: Callable[..., Path],
    mock_notifications: Any,
    setup_output_manager: Any,
) -> None:
    """Test complete workflow with complex recipe configuration."""
    # Create JSON config file
    config_file = create_json_file(complex_recipe_data)

    # Load recipe
    recipe = await ConfigManager.load_json_recipe(config_file)

    # Convert to executable tasks
    executable_tasks = ConfigManager.recipe_to_executable_tasks(recipe)

    # Count expected tasks:
    # full_task: 4 lemmas × 2 tamarin versions = 8 tasks
    # lemma_specific_task: 2 lemmas (test_lemma matches 2, different_lemma matches 1) = 3 tasks
    # Total: 11 tasks
    assert len(executable_tasks) == 11

    # Verify full_task configurations
    full_tasks = [t for t in executable_tasks if t.task_name.startswith("full_task--")]
    assert len(full_tasks) == 8  # 4 lemmas × 2 versions

    for task in full_tasks:
        assert task.tamarin_version_name in ["stable", "dev"]
        assert task.max_cores == 8  # from task resources
        assert task.max_memory == 16  # from task resources
        assert task.task_timeout == 1800  # from task resources
        assert task.tamarin_options == ["--heuristic=S"]
        assert task.preprocess_flags == ["FLAG1", "FLAG2"]

    # Verify lemma_specific_task configurations
    lemma_tasks = [
        t for t in executable_tasks if t.task_name.startswith("lemma_task--")
    ]
    assert len(lemma_tasks) == 3

    # Find the test_lemma task (should use dev version and specific resources)
    test_lemma_tasks = [t for t in lemma_tasks if t.lemma and "test_lemma" in t.lemma]
    assert len(test_lemma_tasks) == 2  # matches test_lemma_1 and test_lemma_2

    for task in test_lemma_tasks:
        assert task.tamarin_version_name == "dev"  # overridden by lemma config
        assert task.max_cores == 4  # from lemma resources
        assert task.max_memory == 8  # from lemma resources
        assert task.task_timeout == 900  # from lemma resources

    # Find the different_lemma task (should use stable version and task defaults)
    different_lemma_tasks = [t for t in lemma_tasks if t.lemma == "different_lemma"]
    assert len(different_lemma_tasks) == 1

    different_task = different_lemma_tasks[0]
    assert different_task.tamarin_version_name == "stable"  # from task config
    assert different_task.max_cores == 4  # default from Resources
    assert different_task.max_memory == 16  # default from Resources
    assert different_task.task_timeout == 7200  # from global config
    assert different_task.tamarin_options == ["--diff"]
    assert different_task.preprocess_flags == ["FLAG3"]


@pytest.mark.asyncio
async def test_resource_inheritance_and_capping(
    complex_recipe_data: Dict[str, Any],
    create_json_file: Callable[..., Path],
    mock_notifications: Any,
    setup_output_manager: Any,
) -> None:
    """Test that resource inheritance and global capping work correctly."""
    # Modify recipe to test resource capping
    complex_recipe_data["tasks"]["resource_test"] = {
        "theory_file": str(complex_recipe_data["tasks"]["full_task"]["theory_file"]),
        "tamarin_versions": ["stable"],
        "output_file_prefix": "resource_test",
        "resources": {
            "max_cores": 32,  # Exceeds global max of 16
            "max_memory": 64,  # Exceeds global max of 32
            "timeout": 900,
        },
    }

    config_file = create_json_file(complex_recipe_data)
    recipe = await ConfigManager.load_json_recipe(config_file)
    executable_tasks = ConfigManager.recipe_to_executable_tasks(recipe)

    # Find resource_test tasks
    resource_test_tasks = [
        t for t in executable_tasks if t.task_name.startswith("resource_test--")
    ]
    assert len(resource_test_tasks) == 4  # 4 lemmas

    # Verify resources are capped at global limits
    for task in resource_test_tasks:
        assert task.max_cores == 16  # Capped at global_max_cores
        assert task.max_memory == 32  # Capped at global_max_memory
        assert task.task_timeout == 900  # Timeout not capped

    # Verify warning messages were logged
    warning_messages = [
        msg for level, msg in mock_notifications.messages if level == "warning"
    ]
    assert any(
        "max_cores" in msg and "exceeds global_max_cores" in msg
        for msg in warning_messages
    )
    assert any(
        "max_memory" in msg and "exceeds global_max_memory" in msg
        for msg in warning_messages
    )


@pytest.mark.asyncio
async def test_unique_task_id_generation(
    minimal_recipe_data: Dict[str, Any],
    create_json_file: Callable[..., Path],
    mock_notifications: Any,
    setup_output_manager: Any,
) -> None:
    """Test that task IDs are unique when there are duplicates."""
    # Create recipe that would generate duplicate task IDs
    minimal_recipe_data["tasks"]["duplicate_task"] = {
        "theory_file": str(minimal_recipe_data["tasks"]["test_task"]["theory_file"]),
        "tamarin_versions": ["stable"],
        "output_file_prefix": "test_task",  # Same prefix as test_task
    }

    config_file = create_json_file(minimal_recipe_data)
    recipe = await ConfigManager.load_json_recipe(config_file)

    # Clear the task ID counter to test uniqueness
    ConfigManager.task_id_counter.clear()

    executable_tasks = ConfigManager.recipe_to_executable_tasks(recipe)

    # Verify all task names are unique
    task_names = [task.task_name for task in executable_tasks]
    assert len(task_names) == len(set(task_names))  # All unique

    # Verify some tasks have numbered suffixes
    numbered_tasks = [name for name in task_names if name.endswith("_2")]
    assert len(numbered_tasks) > 0  # Some tasks should have _2 suffix


@pytest.mark.asyncio
async def test_lemma_prefix_matching(
    complex_recipe_data: Dict[str, Any],
    create_json_file: Callable[..., Path],
    mock_notifications: Any,
    setup_output_manager: Any,
) -> None:
    """Test that lemma prefix matching works correctly."""
    # Modify recipe to test prefix matching
    complex_recipe_data["tasks"]["prefix_test"] = {
        "theory_file": str(complex_recipe_data["tasks"]["full_task"]["theory_file"]),
        "tamarin_versions": ["stable"],
        "output_file_prefix": "prefix_test",
        "lemmas": [
            {
                "name": "test_lemma",  # Should match test_lemma_1 and test_lemma_2
            },
            {
                "name": "success",  # Should match success_lemma
            },
            {
                "name": "nonexistent",  # Should match nothing
            },
        ],
    }

    config_file = create_json_file(complex_recipe_data)
    recipe = await ConfigManager.load_json_recipe(config_file)
    executable_tasks = ConfigManager.recipe_to_executable_tasks(recipe)

    # Find prefix_test tasks
    prefix_test_tasks = [
        t for t in executable_tasks if t.task_name.startswith("prefix_test--")
    ]

    # Should have 3 tasks: test_lemma_1, test_lemma_2, success_lemma
    assert len(prefix_test_tasks) == 3

    matched_lemmas = {task.lemma for task in prefix_test_tasks}
    assert matched_lemmas == {"test_lemma_1", "test_lemma_2", "success_lemma"}

    # Verify warning about nonexistent lemma
    warning_messages = [
        msg for level, msg in mock_notifications.messages if level == "warning"
    ]
    assert any(
        "nonexistent" in msg and "No lemmas found matching prefix" in msg
        for msg in warning_messages
    )
