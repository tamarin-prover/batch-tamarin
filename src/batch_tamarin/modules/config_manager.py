import json
from pathlib import Path
from typing import Dict, List, Tuple

from pydantic import ValidationError

from ..model.executable_task import ExecutableTask
from ..model.tamarin_recipe import (
    GlobalConfig,
    Lemma,
    TamarinRecipe,
    TamarinVersion,
    Task,
)
from ..utils.notifications import notification_manager
from .output_manager import output_manager
from .tamarin_test_cmd import check_tamarin_integrity


class ConfigError(Exception):
    """Exception raised for configuration-related errors."""


class ConfigManager:
    """Manages wrapper configuration serialization and deserialization."""

    task_id_counter: Dict[str, int] = {}

    @staticmethod
    async def load_json_recipe(
        config_path: Path, revalidate: bool = False
    ) -> TamarinRecipe:
        """
        Load TamarinRecipe configuration from a JSON file.

        Args:
            config_path: Path to the configuration file
            revalidate: If True, re-validate all tamarin versions after loading

        Returns:
            Configured TamarinRecipe instance

        Raises:
            ConfigError: If loading or validation fails
        """
        try:
            if not config_path.exists():
                notification_manager.critical(
                    f"[ConfigManager] Configuration file not found: {config_path}"
                )

            if not config_path.is_file():
                notification_manager.critical(
                    f"[ConfigManager] Configuration path is not a file: {config_path}"
                )

            with open(config_path, "r", encoding="utf-8") as f:
                json_data = f.read()

            recipe = TamarinRecipe.model_validate_json(json_data)

            # Handle revalidation if requested
            if revalidate:
                notification_manager.phase_separator("Tamarin Integrity Testing")
                await check_tamarin_integrity(recipe.tamarin_versions)

            notification_manager.phase_separator("Configuration")
            notification_manager.success(
                f"[ConfigManager] JSON recipe loaded from {config_path} with "
                f"({len(recipe.tamarin_versions)} tamarin version(s), {len(recipe.tasks)} task(s))"
            )

            return recipe

        except ValidationError as e:
            error_msg = f"[ConfigManager] Invalid JSON structure in {config_path}: {e}"
            raise ConfigError(error_msg) from e
        except json.JSONDecodeError as e:
            error_msg = (
                f"[ConfigManager] Invalid JSON in configuration file {config_path}: {e}"
            )
            raise ConfigError(error_msg) from e
        except Exception as e:
            error_msg = f"[ConfigManager] Failed to load JSON configuration from {config_path}: {e}"
            raise ConfigError(error_msg) from e

    @staticmethod
    def save_json_recipe(recipe: TamarinRecipe, config_path: Path) -> None:
        """
        Save TamarinRecipe configuration to a JSON file.

        Args:
            recipe: The TamarinRecipe to save
            config_path: Path to the configuration file

        Raises:
            ConfigError: If saving fails
        """
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json_data = recipe.model_dump_json(
                    indent=4,
                    exclude_none=True,
                    exclude_unset=True,
                    exclude_defaults=True,
                )
                f.write(json_data)

            notification_manager.info(
                f"[ConfigManager] JSON recipe saved to {config_path}"
            )

        except Exception as e:
            error_msg = f"[ConfigManager] Failed to save JSON configuration to {config_path}: {e}"
            raise ConfigError(error_msg) from e

    @staticmethod
    def recipe_to_executable_tasks(recipe: TamarinRecipe) -> List[ExecutableTask]:
        """
        Convert TamarinRecipe to list of ExecutableTask objects.

        Args:
            recipe: The TamarinRecipe to convert

        Returns:
            List of ExecutableTask objects ready for execution

        Raises:
            ConfigError: If conversion fails due to validation errors
        """
        executable_tasks: List[ExecutableTask] = []

        try:
            output_paths = output_manager.get_output_paths()
            models_dir = output_paths["models"]

            for task_name, task in recipe.tasks.items():
                theory_file = ConfigManager._validate_theory_file(
                    task.theory_file, task_name
                )

                if task.lemmas:
                    ConfigManager._create_executable_tasks_for_lemmas(
                        task_name, task, recipe, models_dir, executable_tasks
                    )
                else:
                    ConfigManager._create_executable_tasks_for_task(
                        task_name,
                        task,
                        recipe,
                        models_dir,
                        theory_file,
                        executable_tasks,
                    )

            notification_manager.success(
                f"[ConfigManager] Generated {len(executable_tasks)} executable task{'s' if len(executable_tasks) > 1 else ''} from recipe"
            )

            return executable_tasks

        except Exception as e:
            error_msg = (
                f"[ConfigManager] Failed to convert recipe to executable tasks: {e}"
            )
            raise ConfigError(error_msg) from e

    @staticmethod
    def _validate_theory_file(theory_file_path: str, task_name: str) -> Path:
        """Validate that theory file exists and is a file."""
        theory_file = Path(theory_file_path)
        if not theory_file.exists():
            error_msg = f"[ConfigManager] Theory file {theory_file} not found for recipe's task '{task_name}'"
            raise ConfigError(error_msg)
        if not theory_file.is_file():
            error_msg = f"[ConfigManager] Theory file path {theory_file} is not a file for recipe's task '{task_name}'"
            raise ConfigError(error_msg)
        return theory_file

    @staticmethod
    def _validate_and_cap_resources(
        max_cores: int, max_memory: int, global_config: GlobalConfig, context_name: str
    ) -> Tuple[int, int]:
        """Validate and cap resources against global limits."""
        if max_cores > global_config.global_max_cores:
            notification_manager.warning(
                f"{context_name} max_cores ({max_cores}) exceeds global_max_cores, falling back to this value : ({global_config.global_max_cores})"
            )
            max_cores = global_config.global_max_cores

        if max_memory > global_config.global_max_memory:
            notification_manager.warning(
                f"{context_name} max_memory ({max_memory}) exceeds global_max_memory, falling back to this value : ({global_config.global_max_memory})"
            )
            max_memory = global_config.global_max_memory

        return max_cores, max_memory

    @staticmethod
    def _validate_tamarin_executable(
        version_name: str, tamarin_version: TamarinVersion, recipe: TamarinRecipe
    ) -> Path:
        """Validate that tamarin executable exists and is a file."""
        tamarin_executable = Path(tamarin_version.path)
        if not tamarin_executable.exists():
            raise ConfigError(
                f"[ConfigManager] Tamarin executable not found for alias '{version_name}': {tamarin_executable}"
            )
        if not tamarin_executable.is_file():
            raise ConfigError(
                f"[ConfigManager] Tamarin executable path is not a file for alias '{version_name}': {tamarin_executable}"
            )
        return tamarin_executable

    @staticmethod
    def _create_executable_tasks_for_lemmas(
        task_name: str,
        task: Task,
        recipe: TamarinRecipe,
        models_dir: Path,
        executable_tasks: List[ExecutableTask],
    ) -> None:
        """Create executable tasks for each lemma with inheritance."""
        theory_file = ConfigManager._validate_theory_file(task.theory_file, task_name)

        # Assert that lemmas is not None since we check this before calling
        assert (
            task.lemmas is not None
        ), "task.lemmas should not be None when this method is called"

        for lemma in task.lemmas:
            # Get effective configuration for this lemma (with inheritance)
            effective_tamarin_versions = (
                lemma.tamarin_versions
                if lemma.tamarin_versions is not None
                else task.tamarin_versions
            )

            effective_tamarin_options = lemma.tamarin_options or task.tamarin_options
            effective_preprocess_flags = lemma.preprocess_flags or task.preprocess_flags

            # Get effective resources with inheritance
            max_cores, max_memory, timeout = (
                ConfigManager._get_lemma_effective_resources(lemma, task, recipe.config)
            )

            # Validate lemma tamarin_versions reference valid global versions
            for version_name in effective_tamarin_versions:
                if version_name not in recipe.tamarin_versions:
                    raise ConfigError(
                        f"[ConfigManager] Lemma '{lemma.name}' in task '{task_name}' references undefined tamarin alias: '{version_name}'"
                    )

            # Validate and cap resources
            context_name = f"Lemma '{lemma.name}' in task '{task_name}'"
            max_cores, max_memory = ConfigManager._validate_and_cap_resources(
                max_cores, max_memory, recipe.config, context_name
            )

            for version_name in effective_tamarin_versions:
                tamarin_version = recipe.tamarin_versions[version_name]
                tamarin_executable = ConfigManager._validate_tamarin_executable(
                    version_name, tamarin_version, recipe
                )

                # Generate executable task name / ID
                task_id = f"{task_name}_{lemma.name}_{version_name}"
                safe_task_id = ConfigManager._get_unique_task_id(task_id)

                output_filename = Path(f"{safe_task_id}.spthy")
                output_file_path = models_dir / output_filename

                executable_task = ExecutableTask(
                    task_name=safe_task_id,
                    tamarin_version_name=version_name,
                    tamarin_executable=tamarin_executable,
                    theory_file=theory_file,
                    output_file=output_file_path,
                    lemma=lemma.name,
                    tamarin_options=effective_tamarin_options,
                    preprocess_flags=effective_preprocess_flags,
                    max_cores=max_cores,
                    max_memory=max_memory,
                    task_timeout=timeout,
                )
                executable_tasks.append(executable_task)
                notification_manager.debug(
                    f"[ConfigManager] Created ExecutableTask : {executable_task}"
                )

    @staticmethod
    def _create_executable_tasks_for_task(
        task_name: str,
        task: Task,
        recipe: TamarinRecipe,
        models_dir: Path,
        theory_file: Path,
        executable_tasks: List[ExecutableTask],
    ) -> None:
        """Create executable tasks for task without specific lemmas."""
        # Get effective resources for this task
        task_max_cores, task_max_memory, task_timeout = (
            ConfigManager._get_task_effective_resources(task, recipe.config)
        )

        # Validate and cap resources
        context_name = f"Task '{task_name}'"
        task_max_cores, task_max_memory = ConfigManager._validate_and_cap_resources(
            task_max_cores, task_max_memory, recipe.config, context_name
        )

        # Expand task for each specified tamarin version
        for version_name in task.tamarin_versions:
            if version_name not in recipe.tamarin_versions:
                raise ConfigError(
                    f"[ConfigManager] Task '{task_name}' references undefined tamarin alias: '{version_name}'"
                )

            tamarin_version = recipe.tamarin_versions[version_name]
            tamarin_executable = ConfigManager._validate_tamarin_executable(
                version_name, tamarin_version, recipe
            )

            # Generate task name / id
            task_id = f"{task_name}_{version_name}"
            safe_task_id = ConfigManager._get_unique_task_id(task_id)

            output_filename = f"{safe_task_id}.spthy"
            output_file_path = models_dir / output_filename

            # Create single ExecutableTask for all lemmas
            executable_task = ExecutableTask(
                task_name=safe_task_id,
                tamarin_version_name=version_name,
                tamarin_executable=tamarin_executable,
                theory_file=theory_file,
                output_file=output_file_path,
                lemma=None,  # None means prove all lemmas
                tamarin_options=task.tamarin_options,
                preprocess_flags=task.preprocess_flags,
                max_cores=task_max_cores,
                max_memory=task_max_memory,
                task_timeout=task_timeout,
            )
            executable_tasks.append(executable_task)
            notification_manager.debug(
                f"[ConfigManager] Created ExecutableTask : {executable_task}"
            )

    @staticmethod
    def _get_unique_task_id(base_task_id: str) -> str:
        """
        Generate a unique task ID, adding a counter if duplicates exist.

        Args:
            base_task_id: The base task ID to make unique
            task_id_counter: Dictionary tracking task ID usage counts

        Returns:
            Unique task ID (with counter suffix if needed)
        """
        if base_task_id not in ConfigManager.task_id_counter:
            ConfigManager.task_id_counter[base_task_id] = 1
            return base_task_id
        else:
            ConfigManager.task_id_counter[base_task_id] += 1
            return f"{base_task_id}_{ConfigManager.task_id_counter[base_task_id]}"

    @staticmethod
    def _get_lemma_effective_resources(
        lemma: Lemma, task: Task, global_config: GlobalConfig
    ) -> Tuple[int, int, int]:
        """
        Get effective resources for a lemma with proper inheritance.

        Args:
            lemma: The lemma object
            task: The parent task object
            global_config: Global configuration

        Returns:
            Tuple of (max_cores, max_memory, timeout) with all values resolved (no None values)
        """
        # Start with global defaults
        max_cores = global_config.global_max_cores
        max_memory = global_config.global_max_memory
        timeout = global_config.default_timeout

        # Apply task-level overrides if task has resources
        if task.ressources:
            if task.ressources.max_cores is not None:
                max_cores = task.ressources.max_cores
            if task.ressources.max_memory is not None:
                max_memory = task.ressources.max_memory
            if task.ressources.timeout is not None:
                timeout = task.ressources.timeout

        # Apply lemma-level overrides if lemma has resources
        if lemma.ressources:
            if lemma.ressources.max_cores is not None:
                max_cores = lemma.ressources.max_cores
            if lemma.ressources.max_memory is not None:
                max_memory = lemma.ressources.max_memory
            if lemma.ressources.timeout is not None:
                timeout = lemma.ressources.timeout

        return max_cores, max_memory, timeout

    @staticmethod
    def _get_task_effective_resources(
        task: Task, global_config: GlobalConfig
    ) -> Tuple[int, int, int]:
        """
        Get effective resources for a task with defaults applied.

        Args:
            task: The task object
            global_config: Global configuration

        Returns:
            Tuple of (max_cores, max_memory, timeout) with all values resolved (no None values)
        """
        # Start with global defaults
        max_cores = global_config.global_max_cores
        max_memory = global_config.global_max_memory
        timeout = global_config.default_timeout

        # Apply task-level overrides if task has resources
        if task.ressources:
            if task.ressources.max_cores is not None:
                max_cores = task.ressources.max_cores
            if task.ressources.max_memory is not None:
                max_memory = task.ressources.max_memory
            if task.ressources.timeout is not None:
                timeout = task.ressources.timeout

        return max_cores, max_memory, timeout
