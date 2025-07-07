"""
Tests for ConfigManager class.

These tests focus specifically on the ConfigManager functionality,
including JSON loading, validation, error handling, and configuration resolution.
"""

import json
from pathlib import Path
from typing import Any, Callable, Dict

import pytest

from batch_tamarin.model.tamarin_recipe import TamarinRecipe
from batch_tamarin.modules.config_manager import ConfigError, ConfigManager


class TestJSONLoading:
    """Test JSON recipe loading functionality."""

    @pytest.mark.asyncio
    async def test_load_valid_json_recipe(
        self,
        minimal_recipe_data: Dict[str, Any],
        create_json_file: Callable[[Dict[str, Any]], Path],
        mock_notifications: Any,
    ):
        """Test loading a valid JSON recipe."""
        config_file = create_json_file(minimal_recipe_data)

        recipe = await ConfigManager.load_json_recipe(config_file)

        assert isinstance(recipe, TamarinRecipe)
        assert recipe.config.global_max_cores == 8
        assert recipe.config.global_max_memory == 16
        assert "stable" in recipe.tamarin_versions
        assert "test_task" in recipe.tasks

        # Verify success message was logged
        success_messages = [
            msg for level, msg in mock_notifications.messages if level == "success"
        ]
        assert any("JSON recipe loaded" in msg for msg in success_messages)

    @pytest.mark.asyncio
    async def test_load_nonexistent_file(self, tmp_dir: Path, mock_notifications: Any):
        """Test loading a non-existent JSON file."""
        nonexistent_file = tmp_dir / "nonexistent.json"

        with pytest.raises(ConfigError, match="Failed to load JSON configuration from"):
            await ConfigManager.load_json_recipe(nonexistent_file)

    @pytest.mark.asyncio
    async def test_load_directory_instead_of_file(
        self, tmp_dir: Path, mock_notifications: Any
    ):
        """Test loading a directory instead of a file."""
        directory = tmp_dir / "config_dir"
        directory.mkdir()

        with pytest.raises(ConfigError, match="Failed to load JSON configuration from"):
            await ConfigManager.load_json_recipe(directory)

    @pytest.mark.asyncio
    async def test_load_invalid_json(self, tmp_dir: Path, mock_notifications: Any):
        """Test loading invalid JSON."""
        invalid_json_file = tmp_dir / "invalid.json"
        invalid_json_file.write_text("{ invalid json content")

        with pytest.raises(ConfigError, match="Invalid JSON structure in"):
            await ConfigManager.load_json_recipe(invalid_json_file)

    @pytest.mark.asyncio
    async def test_load_json_with_extra_fields(
        self, tmp_dir: Path, mock_notifications: Any
    ):
        """Test loading JSON with unexpected fields."""
        invalid_data: Dict[str, Any] = {
            "config": {
                "global_max_cores": 8,
                "global_max_memory": 16,
                "default_timeout": 3600,
                "output_directory": "./test-results",
                "unexpected_field": "unexpected_value",  # This should cause validation error
            },
            "tamarin_versions": {"stable": {"path": "/fake/path"}},
            "tasks": {
                "test_task": {
                    "theory_file": "/fake/theory.spthy",
                    "tamarin_versions": ["stable"],
                    "output_file_prefix": "test_task",
                }
            },
        }

        config_file = tmp_dir / "invalid.json"
        config_file.write_text(json.dumps(invalid_data))

        with pytest.raises(ConfigError, match="Invalid JSON structure"):
            await ConfigManager.load_json_recipe(config_file)

        # Verify critical message was logged with context
        critical_messages = [
            msg for level, msg in mock_notifications.messages if level == "critical"
        ]
        assert any("unexpected_field" in msg for msg in critical_messages)

    @pytest.mark.asyncio
    async def test_load_json_with_invalid_key_patterns(
        self, tmp_dir: Path, mock_notifications: Any
    ):
        """Test loading JSON with invalid key patterns."""
        invalid_data: Dict[str, Any] = {
            "config": {
                "global_max_cores": 8,
                "global_max_memory": 16,
                "default_timeout": 3600,
                "output_directory": "./test-results",
            },
            "tamarin_versions": {
                "1invalid_key": {
                    "path": "/fake/path"
                }  # Invalid key (starts with number)
            },
            "tasks": {
                "test_task": {
                    "theory_file": "/fake/theory.spthy",
                    "tamarin_versions": ["1invalid_key"],
                    "output_file_prefix": "test_task",
                }
            },
        }

        config_file = tmp_dir / "invalid.json"
        config_file.write_text(json.dumps(invalid_data))

        with pytest.raises(ConfigError, match="Invalid JSON structure"):
            await ConfigManager.load_json_recipe(config_file)


class TestTaskGeneration:
    """Test ExecutableTask generation from recipes."""

    def test_recipe_to_executable_tasks_minimal(
        self,
        minimal_recipe_data: Dict[str, Any],
        create_json_file: Callable[[Dict[str, Any]], Path],
        mock_notifications: Any,
        setup_output_manager: Any,
    ):
        """Test converting minimal recipe to executable tasks."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)

        executable_tasks = ConfigManager.recipe_to_executable_tasks(recipe)

        assert len(executable_tasks) == 4  # 4 lemmas from theory file

        for task in executable_tasks:
            assert task.task_name.startswith("test_task--")
            assert task.tamarin_version_name == "stable"
            assert task.max_cores == 4  # default
            assert task.max_memory == 16  # default
            assert task.task_timeout == 3600  # from global config

    def test_recipe_to_executable_tasks_with_nonexistent_theory(
        self,
        minimal_recipe_data: Dict[str, Any],
        mock_notifications: Any,
        setup_output_manager: Any,
    ):
        """Test handling of non-existent theory files."""
        # Set theory file to non-existent path
        minimal_recipe_data["tasks"]["test_task"][
            "theory_file"
        ] = "/nonexistent/theory.spthy"

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)

        with pytest.raises(ConfigError, match="Theory file .* not found"):
            ConfigManager.recipe_to_executable_tasks(recipe)

    def test_recipe_to_executable_tasks_with_nonexistent_tamarin(
        self,
        minimal_recipe_data: Dict[str, Any],
        mock_notifications: Any,
        setup_output_manager: Any,
    ):
        """Test handling of non-existent tamarin executables."""
        # Set tamarin executable to non-existent path
        minimal_recipe_data["tamarin_versions"]["stable"][
            "path"
        ] = "/nonexistent/tamarin-prover"

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)

        with pytest.raises(ConfigError, match="Tamarin executable not found"):
            ConfigManager.recipe_to_executable_tasks(recipe)

    def test_recipe_to_executable_tasks_with_invalid_tamarin_version(
        self,
        minimal_recipe_data: Dict[str, Any],
        create_json_file: Callable[[Dict[str, Any]], Path],
        mock_notifications: Any,
        setup_output_manager: Any,
    ):
        """Test handling of invalid tamarin version references."""
        # Reference a tamarin version that doesn't exist
        minimal_recipe_data["tasks"]["test_task"]["tamarin_versions"] = ["nonexistent"]

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)

        with pytest.raises(
            ConfigError, match="Tamarin version 'nonexistent' not found"
        ):
            ConfigManager.recipe_to_executable_tasks(recipe)

    def test_resource_inheritance_for_lemma_overrides_only_specified(
        self,
        minimal_recipe_data: Dict[str, Any],
        mock_notifications: Any,
        setup_output_manager: Any,
    ):
        """Test that lemma-level resource overrides only apply to specified fields."""
        from copy import deepcopy

        # Prepare recipe data with task-level and lemma-level resources
        recipe_data = deepcopy(minimal_recipe_data)
        task = recipe_data["tasks"]["test_task"]
        # Task-level resources override global defaults
        task["resources"] = {"max_cores": 2, "max_memory": 8, "timeout": 100}
        # Lemma spec only overrides max_memory
        task["lemmas"] = [{"name": "", "resources": {"max_memory": 32}}]
        recipe = TamarinRecipe.model_validate(recipe_data)
        tasks = ConfigManager.recipe_to_executable_tasks(recipe)
        # All lemmas matched, check resource values for each
        for ex_task in tasks:
            assert ex_task.max_cores == 2, "Expected cores from task-level override"
            assert ex_task.max_memory == 32, "Expected memory from lemma-level override"
            assert (
                ex_task.task_timeout == 100
            ), "Expected timeout from task-level override"


class TestResourceResolution:
    """Test resource inheritance and resolution."""

    def test_resource_inheritance_lemma_overrides_task(
        self,
        complex_recipe_data: Dict[str, Any],
        mock_notifications: Any,
        setup_output_manager: Any,
    ):
        """Test that lemma resources override task resources."""
        recipe = TamarinRecipe.model_validate(complex_recipe_data)
        executable_tasks = ConfigManager.recipe_to_executable_tasks(recipe)

        # Find test_lemma tasks (should have lemma-specific resources)
        test_lemma_tasks = [
            t
            for t in executable_tasks
            if t.lemma is not None and "test_lemma" in t.lemma
        ]

        for task in test_lemma_tasks:
            if task.task_name.startswith("full_task--"):
                assert task.max_cores == 8
                assert task.max_memory == 16
                assert task.task_timeout == 1800
            if task.task_name.startswith("test_lemma--"):
                assert task.max_cores == 4  # from lemma resources
                assert task.max_memory == 8  # from lemma resources
                assert task.task_timeout == 900  # from lemma resources

    def test_resource_inheritance_shared_parameters(
        self,
        inheritance_recipe_data: Dict[str, Any],
        mock_notifications: Any,
        setup_output_manager: Any,
    ):
        """Test that shared parameters are inherited correctly."""
        recipe = TamarinRecipe.model_validate(inheritance_recipe_data)
        executable_tasks = ConfigManager.recipe_to_executable_tasks(recipe)

        # Find base_task tasks (should have inherited resources)
        base_tasks = [
            t for t in executable_tasks if t.task_name.startswith("base_task--")
        ]

        for task in base_tasks:
            assert task.max_cores == 3
            assert task.max_memory == 4
            assert task.task_timeout == 1200

    def test_resource_inheritance_task_overrides_global(
        self,
        complex_recipe_data: Dict[str, Any],
        mock_notifications: Any,
        setup_output_manager: Any,
    ):
        """Test that task resources override global defaults."""
        recipe = TamarinRecipe.model_validate(complex_recipe_data)
        executable_tasks = ConfigManager.recipe_to_executable_tasks(recipe)

        # Find full_task tasks (should have task-specific resources)
        full_tasks = [
            t for t in executable_tasks if t.task_name.startswith("full_task--")
        ]

        for task in full_tasks:
            assert task.max_cores == 8  # from task resources
            assert task.max_memory == 16  # from task resources
            assert task.task_timeout == 1800  # from task resources

    def test_resource_capping_at_global_limits(
        self,
        minimal_recipe_data: Dict[str, Any],
        mock_notifications: Any,
        setup_output_manager: Any,
    ):
        """Test that resources are capped at global limits."""
        # Set task resources above global limits
        minimal_recipe_data["tasks"]["test_task"]["resources"] = {
            "max_cores": 32,  # Above global max of 8
            "max_memory": 64,  # Above global max of 16
            "timeout": 1800,
        }

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        executable_tasks = ConfigManager.recipe_to_executable_tasks(recipe)

        # Verify resources are capped
        for task in executable_tasks:
            assert task.max_cores == 8  # Capped at global max
            assert task.max_memory == 16  # Capped at global max
            assert task.task_timeout == 1800  # Timeout not capped

        # Verify warnings were logged
        warning_messages = [
            msg for level, msg in mock_notifications.messages if level == "warning"
        ]
        assert any("exceeds global_max_cores" in msg for msg in warning_messages)
        assert any("exceeds global_max_memory" in msg for msg in warning_messages)


class TestLemmaFiltering:
    """Test lemma filtering and configuration."""

    def test_no_lemmas_specified_uses_all(
        self,
        minimal_recipe_data: Dict[str, Any],
        mock_notifications: Any,
        setup_output_manager: Any,
    ):
        """Test that when no lemmas are specified, all lemmas are used."""
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        executable_tasks = ConfigManager.recipe_to_executable_tasks(recipe)

        # Should generate tasks for all lemmas
        lemma_names = {task.lemma for task in executable_tasks}
        assert lemma_names == {
            "test_lemma_1",
            "test_lemma_2",
            "different_lemma",
            "success_lemma",
        }

        # Verify debug message about using all lemmas
        debug_messages = [
            msg for level, msg in mock_notifications.messages if level == "debug"
        ]
        assert any(
            "No lemmas specified" in msg and "using all" in msg
            for msg in debug_messages
        )

    def test_lemma_prefix_matching(
        self,
        complex_recipe_data: Dict[str, Any],
        mock_notifications: Any,
        setup_output_manager: Any,
    ):
        """Test that lemma prefix matching works correctly."""
        recipe = TamarinRecipe.model_validate(complex_recipe_data)
        executable_tasks = ConfigManager.recipe_to_executable_tasks(recipe)

        # Find lemma_specific_task tasks
        lemma_tasks = [
            t for t in executable_tasks if t.task_name.startswith("lemma_task--")
        ]

        # Should match: test_lemma_1, test_lemma_2 (from "test_lemma"), different_lemma (from "different_lemma")
        lemma_names = {task.lemma for task in lemma_tasks}
        assert lemma_names == {"test_lemma_1", "test_lemma_2", "different_lemma"}

    def test_lemma_no_matches_warning(
        self,
        minimal_recipe_data: Dict[str, Any],
        mock_notifications: Any,
        setup_output_manager: Any,
    ):
        """Test warning when lemma prefix has no matches."""
        # Add a lemma that won't match anything
        minimal_recipe_data["tasks"]["test_task"]["lemmas"] = [
            {"name": "nonexistent_lemma"}
        ]

        recipe = TamarinRecipe.model_validate(minimal_recipe_data)
        executable_tasks = ConfigManager.recipe_to_executable_tasks(recipe)

        # Should generate no tasks for this task
        test_tasks = [
            t for t in executable_tasks if t.task_name.startswith("test_task--")
        ]
        assert len(test_tasks) == 0

        # Verify warning was logged
        warning_messages = [
            msg for level, msg in mock_notifications.messages if level == "warning"
        ]
        assert any(
            "No lemmas found matching prefix 'nonexistent_lemma'" in msg
            for msg in warning_messages
        )


class TestTaskIdGeneration:
    """Test unique task ID generation."""

    def test_unique_task_id_basic(self):
        """Test basic unique task ID generation."""
        ConfigManager.task_id_counter.clear()

        # First occurrence should return the base ID
        task_id1 = ConfigManager.get_unique_task_id("test_task")
        assert task_id1 == "test_task"

        # Second occurrence should get a suffix
        task_id2 = ConfigManager.get_unique_task_id("test_task")
        assert task_id2 == "test_task_2"

        # Third occurrence should increment
        task_id3 = ConfigManager.get_unique_task_id("test_task")
        assert task_id3 == "test_task_3"

    def test_unique_task_id_different_bases(self):
        """Test that different base IDs don't interfere."""
        ConfigManager.task_id_counter.clear()

        task_id1 = ConfigManager.get_unique_task_id("task_a")
        task_id2 = ConfigManager.get_unique_task_id("task_b")
        task_id3 = ConfigManager.get_unique_task_id("task_a")

        assert task_id1 == "task_a"
        assert task_id2 == "task_b"
        assert task_id3 == "task_a_2"


class TestValidationAndErrorHandling:
    """Test validation and error handling."""

    def test_theory_file_validation(self, tmp_dir: Path, mock_notifications: Any):
        """Test theory file validation."""
        nonexistent_file = "/nonexistent/theory.spthy"

        with pytest.raises(ConfigError, match="Theory file .* not found"):
            ConfigManager.validate_theory_file(nonexistent_file, "test_task")

    def test_tamarin_executable_validation(
        self,
        tmp_dir: Path,
        mock_notifications: Any,
        minimal_recipe_data: Dict[str, Any],
    ):
        """Test tamarin executable validation."""
        from batch_tamarin.model.tamarin_recipe import TamarinVersion

        # Test non-existent executable
        tamarin_version = TamarinVersion(
            path="/nonexistent/tamarin-prover", version="1.0.0", test_success=False
        )
        recipe = TamarinRecipe.model_validate(minimal_recipe_data)

        with pytest.raises(ConfigError, match="Tamarin executable not found"):
            ConfigManager.validate_tamarin_executable(
                "test_version", tamarin_version, recipe
            )

        # Test directory instead of file
        directory = tmp_dir / "tamarin_dir"
        directory.mkdir()
        tamarin_version = TamarinVersion(
            path=str(directory), version="1.0.0", test_success=False
        )

        with pytest.raises(ConfigError, match="Tamarin executable path is not a file"):
            ConfigManager.validate_tamarin_executable(
                "test_version", tamarin_version, recipe
            )

    def test_resource_validation_and_capping(self, mock_notifications: Any):
        """Test resource validation and capping."""
        from batch_tamarin.model.tamarin_recipe import GlobalConfig

        global_config = GlobalConfig(
            global_max_cores=8,
            global_max_memory=16,
            default_timeout=3600,
            output_directory="./test",
        )

        # Test normal resources (should not be capped)
        cores, memory = ConfigManager.validate_and_cap_resources(
            4, 8, global_config, "Test"
        )
        assert cores == 4
        assert memory == 8

        # Test resources that exceed limits (should be capped)
        cores, memory = ConfigManager.validate_and_cap_resources(
            16, 32, global_config, "Test"
        )
        assert cores == 8  # Capped at global max
        assert memory == 16  # Capped at global max

        # Verify warnings were logged
        warning_messages = [
            msg for level, msg in mock_notifications.messages if level == "warning"
        ]
        assert any("exceeds global_max_cores" in msg for msg in warning_messages)
        assert any("exceeds global_max_memory" in msg for msg in warning_messages)
