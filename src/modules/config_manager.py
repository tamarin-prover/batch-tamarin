import json
import shutil
from pathlib import Path
from typing import List

import typer
from pydantic import ValidationError

from model.executable_task import ExecutableTask
from model.tamarin_recipe import TamarinRecipe
from modules.tamarin_test_cmd import check_tamarin_integrity
from utils.notifications import notification_manager


class ConfigError(Exception):
    """Exception raised for configuration-related errors."""


class ConfigManager:
    """Manages wrapper configuration serialization and deserialization."""

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
                raise ConfigError(
                    f"[ConfigManager] Configuration file not found: {config_path}"
                )

            if not config_path.is_file():
                raise ConfigError(
                    f"[ConfigManager] Configuration path is not a file: {config_path}"
                )

            with open(config_path, "r", encoding="utf-8") as f:
                json_data = f.read()

            recipe = TamarinRecipe.model_validate_json(json_data)

            # Handle revalidation if requested
            if revalidate:
                await check_tamarin_integrity(recipe.tamarin_versions)

            notification_manager.info(
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
            # Validate that output directory exists or can be created
            output_dir = Path(recipe.config.output_directory)
            if not output_dir.exists():
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
                    notification_manager.debug(
                        f"[ConfigManager] Created output directory: {output_dir}"
                    )
                except Exception as e:
                    error_msg = f"[ConfigManager] Failed to create output directory {output_dir}: {e}"
                    raise ConfigError(error_msg) from e
            else:
                # Directory exists, check if it's a directory
                if not output_dir.is_dir():
                    error_msg = (
                        f"[ConfigManager] Output path is not a directory: {output_dir}"
                    )
                    raise ConfigError(error_msg)

                # Check if directory is empty
                if any(output_dir.iterdir()):
                    # Directory is not empty, prompt user
                    should_wipe = typer.confirm(
                        f"Output directory '{output_dir}' is not empty. Do you want to DELETE its contents?",
                        default=False,
                    )

                    if should_wipe:
                        try:
                            # Remove all contents of the directory
                            for item in output_dir.iterdir():
                                if item.is_dir():
                                    shutil.rmtree(item)
                                else:
                                    item.unlink()
                            notification_manager.info(
                                f"[ConfigManager] Wiped contents of output directory: {output_dir}"
                            )
                        except Exception as e:
                            error_msg = f"[ConfigManager] Failed to wipe output directory {output_dir}: {e}"
                            raise ConfigError(error_msg) from e
                    else:
                        notification_manager.info(
                            f"[ConfigManager] Continuing with non-empty output directory: {output_dir}"
                        )

            for task_name, task in recipe.tasks.items():
                # Validate theory file exists
                theory_file = Path(task.theory_file)
                if not theory_file.exists():
                    error_msg = f"[ConfigManager] Theory file not found for task '{task_name}': {theory_file}"
                    raise ConfigError(error_msg)
                if not theory_file.is_file():
                    error_msg = f"[ConfigManager] Theory file path is not a file for task '{task_name}': {theory_file}"
                    raise ConfigError(error_msg)

                # Get effective resources for this task
                resources = recipe.get_task_resources(task_name)

                # Ensure we have concrete values (get_task_resources should handle defaults)
                max_cores = resources.max_cores or 4
                max_memory = resources.max_memory or 8
                task_timeout = resources.task_timeout or recipe.config.default_timeout

                # Validate resource constraints against global limits
                if max_cores > recipe.config.global_max_cores:
                    error_msg = f"Task '{task_name}' max_cores ({max_cores}) exceeds global_max_cores ({recipe.config.global_max_cores})"
                    raise ConfigError(error_msg)

                if max_memory > recipe.config.global_max_memory:
                    error_msg = f"Task '{task_name}' max_memory ({max_memory}) exceeds global_max_memory ({recipe.config.global_max_memory})"
                    raise ConfigError(error_msg)

                # Expand task for each specified tamarin version
                for version_name in task.tamarin_versions:
                    if version_name not in recipe.tamarin_versions:
                        raise ConfigError(
                            f"[ConfigManager] Task '{task_name}' references undefined tamarin alias: '{version_name}'"
                        )

                    tamarin_version = recipe.tamarin_versions[version_name]
                    tamarin_executable = Path(tamarin_version.path)

                    # Validate tamarin executable exists
                    if not tamarin_executable.exists():
                        raise ConfigError(
                            f"[ConfigManager] Tamarin executable not found for alias '{version_name}': {tamarin_executable}"
                        )

                    if not tamarin_executable.is_file():
                        raise ConfigError(
                            f"[ConfigManager] Tamarin executable path is not a file for alias '{version_name}': {tamarin_executable}"
                        )

                    # Generate output filename with version suffix
                    output_base = Path(task.output_file)
                    if output_base.suffix:
                        # Has extension: "results.txt" -> "results_stable.txt"
                        output_filename = (
                            f"{output_base.stem}_{version_name}{output_base.suffix}"
                        )
                    else:
                        # No extension: "results" -> "results_stable"
                        output_filename = f"{output_base.name}_{version_name}"

                    output_file_path = output_dir / output_filename

                    # Handle lemmas - create separate task for each lemma or one task for all
                    if task.lemmas:
                        # Create separate ExecutableTask for each lemma
                        for lemma in task.lemmas:
                            output_file_path_lemma = output_file_path.with_name(
                                f"{output_file_path.stem}_{lemma.name}{output_file_path.suffix}"
                            )
                            executable_task = ExecutableTask(
                                task_name=task_name + lemma.name,
                                tamarin_version_name=version_name,
                                tamarin_executable=tamarin_executable,
                                theory_file=theory_file,
                                output_file=output_file_path_lemma,
                                lemma=lemma.name,
                                tamarin_options=task.tamarin_options,
                                preprocess_flags=task.preprocess_flags,
                                max_cores=max_cores,
                                max_memory=max_memory,
                                task_timeout=lemma.timeout or task_timeout,
                            )
                            executable_tasks.append(executable_task)
                    else:
                        # Create single ExecutableTask for all lemmas
                        executable_task = ExecutableTask(
                            task_name=task_name,
                            tamarin_version_name=version_name,
                            tamarin_executable=tamarin_executable,
                            theory_file=theory_file,
                            output_file=output_file_path,
                            lemma=None,  # None means prove all lemmas
                            tamarin_options=task.tamarin_options,
                            preprocess_flags=task.preprocess_flags,
                            max_cores=max_cores,
                            max_memory=max_memory,
                            task_timeout=task_timeout,
                        )
                        executable_tasks.append(executable_task)

            notification_manager.info(
                f"[ConfigManager] Generated {len(executable_tasks)} executable task(s) from recipe"
            )

            return executable_tasks

        except Exception as e:
            error_msg = (
                f"[ConfigManager] Failed to convert recipe to executable tasks: {e}"
            )
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
