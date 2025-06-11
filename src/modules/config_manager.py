import json
from pathlib import Path
from typing import Dict, List

from pydantic import ValidationError

from model.executable_task import ExecutableTask
from model.tamarin_recipe import TamarinRecipe, TamarinVersion
from model.wrapper import Wrapper
from modules.tamarin_test_cmd import extract_tamarin_version, launch_tamarin_test
from utils.notifications import notification_manager


class ConfigError(Exception):
    """Exception raised for configuration-related errors."""


class ConfigManager:
    """Manages wrapper configuration serialization and deserialization."""

    @staticmethod
    def save_wrapper_config(wrapper: Wrapper, config_path: Path) -> None:
        """
        Save wrapper configuration to a JSON file.

        Args:
            wrapper: The Wrapper instance to serialize
            config_path: Path to the configuration file

        Raises:
            ConfigError: If saving fails
        """
        try:
            # Ensure parent directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(config_path, "w", encoding="utf-8") as f:
                f.write(wrapper.model_dump_json(indent=4))

            notification_manager.info(f"✅ Configuration saved to {config_path}")

        except Exception as e:
            error_msg = f"Failed to save configuration to {config_path}: {e}"
            notification_manager.error(error_msg)
            raise ConfigError(error_msg) from e

    @staticmethod
    async def load_wrapper_config(
        config_path: Path, revalidate: bool = False
    ) -> Wrapper:
        """
        Load wrapper configuration from a JSON file.

        Args:
            config_path: Path to the configuration file
            revalidate: If True, re-validate all tamarin paths after loading

        Returns:
            Configured Wrapper instance

        Raises:
            ConfigError: If loading or validation fails
        """
        try:
            if not config_path.exists():
                raise ConfigError(f"Configuration file not found: {config_path}")

            if not config_path.is_file():
                raise ConfigError(f"Configuration path is not a file: {config_path}")

            with open(config_path, "r", encoding="utf-8") as f:
                json_data = f.read()

            wrapper = Wrapper.model_validate_json(json_data)

            # Handle revalidation if requested
            if revalidate:
                await ConfigManager._revalidate_tamarin_paths(wrapper)

            notification_manager.info(
                f"✅ Configuration loaded from {config_path} "
                f"({len(wrapper.tamarin_path)} tamarin path(s))"
            )

            return wrapper

        except ValidationError as e:
            error_msg = f"Invalid configuration structure in {config_path}: {e}"
            notification_manager.error(error_msg)
            raise ConfigError(error_msg) from e
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in configuration file {config_path}: {e}"
            notification_manager.error(error_msg)
            raise ConfigError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to load configuration from {config_path}: {e}"
            notification_manager.error(error_msg)
            raise ConfigError(error_msg) from e

    @staticmethod
    async def _revalidate_tamarin_paths(wrapper: Wrapper) -> None:
        """
        Re-validate all tamarin paths in the wrapper.

        Args:
            wrapper: The Wrapper instance to revalidate
        """
        for tamarin_path in wrapper.tamarin_path:
            try:
                await tamarin_path.test_tamarin()
            except Exception as e:
                notification_manager.error(
                    f"⚠️ Failed to revalidate tamarin path {tamarin_path.path}: {e}"
                )

    @staticmethod
    def validate_config_file(config_path: Path) -> bool:
        """
        Validate a configuration file without loading it.

        Args:
            config_path: Path to the configuration file

        Returns:
            True if the file is valid, False otherwise
        """
        try:
            if not config_path.exists() or not config_path.is_file():
                return False

            with open(config_path, "r", encoding="utf-8") as f:
                json_data = f.read()

            # Use Pydantic validation without loading the wrapper
            Wrapper.model_validate_json(json_data)
            return True

        except Exception:
            return False

    @staticmethod
    async def load_recipe(config_path: Path, revalidate: bool = False) -> TamarinRecipe:
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
                raise ConfigError(f"Configuration file not found: {config_path}")

            if not config_path.is_file():
                raise ConfigError(f"Configuration path is not a file: {config_path}")

            with open(config_path, "r", encoding="utf-8") as f:
                json_data = f.read()

            recipe = TamarinRecipe.model_validate_json(json_data)

            # Handle revalidation if requested
            if revalidate:
                await ConfigManager.revalidate_tamarin_versions(recipe.tamarin_versions)

            notification_manager.info(
                f"✅ Recipe loaded from {config_path} "
                f"({len(recipe.tamarin_versions)} tamarin version(s), {len(recipe.tasks)} task(s))"
            )

            return recipe

        except ValidationError as e:
            error_msg = f"Invalid recipe configuration structure in {config_path}: {e}"
            notification_manager.error(error_msg)
            raise ConfigError(error_msg) from e
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in recipe configuration file {config_path}: {e}"
            notification_manager.error(error_msg)
            raise ConfigError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to load recipe configuration from {config_path}: {e}"
            notification_manager.error(error_msg)
            raise ConfigError(error_msg) from e

    @staticmethod
    async def revalidate_tamarin_versions(versions: Dict[str, TamarinVersion]) -> None:
        """
        Test tamarin executables for functionality and update TamarinVersion objects.

        Args:
            versions: Dictionary of tamarin versions to revalidate
        """
        for version_name, tamarin_version in versions.items():
            try:
                tamarin_path = Path(tamarin_version.path)

                # Check if executable exists
                if not tamarin_path.exists():
                    notification_manager.error(
                        f"⚠️ Tamarin executable not found: {tamarin_path}"
                    )
                    tamarin_version.test_success = False
                    continue

                if not tamarin_path.is_file():
                    notification_manager.error(
                        f"⚠️ Tamarin path is not a file: {tamarin_path}"
                    )
                    tamarin_version.test_success = False
                    continue

                # Extract version information
                extracted_version = await extract_tamarin_version(tamarin_path)
                if extracted_version:
                    tamarin_version.version = extracted_version
                else:
                    notification_manager.warning(
                        f"⚠️ Could not extract version for {version_name}"
                    )

                # Test tamarin functionality
                test_result = await launch_tamarin_test(tamarin_path)
                tamarin_version.test_success = test_result

                if test_result:
                    notification_manager.info(
                        f"✅ Tamarin version '{version_name}' validated successfully "
                        f"(version: {tamarin_version.version})"
                    )
                else:
                    notification_manager.error(
                        f"❌ Tamarin version '{version_name}' failed validation test"
                    )

            except Exception as e:
                notification_manager.error(
                    f"⚠️ Failed to revalidate tamarin version '{version_name}': {e}"
                )
                tamarin_version.test_success = False

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
                    notification_manager.info(f"Created output directory: {output_dir}")
                except Exception as e:
                    raise ConfigError(
                        f"Cannot create output directory {output_dir}: {e}"
                    )

            if not output_dir.is_dir():
                raise ConfigError(
                    f"Output directory path is not a directory: {output_dir}"
                )

            for task_name, task in recipe.tasks.items():
                # Validate theory file exists
                theory_file = Path(task.theory_file)
                if not theory_file.exists():
                    raise ConfigError(
                        f"Theory file not found for task '{task_name}': {theory_file}"
                    )
                if not theory_file.is_file():
                    raise ConfigError(
                        f"Theory file path is not a file for task '{task_name}': {theory_file}"
                    )

                # Get effective resources for this task
                resources = recipe.get_task_resources(task_name)

                # Ensure we have concrete values (get_task_resources should handle defaults)
                max_cores = resources.max_cores or 4
                max_memory = resources.max_memory or 8
                task_timeout = resources.task_timeout or recipe.config.default_timeout

                # Validate resource constraints against global limits
                if max_cores > recipe.config.global_max_cores:
                    raise ConfigError(
                        f"Task '{task_name}' max_cores ({max_cores}) exceeds "
                        f"global_max_cores ({recipe.config.global_max_cores})"
                    )

                if max_memory > recipe.config.global_max_memory:
                    raise ConfigError(
                        f"Task '{task_name}' max_memory ({max_memory}) exceeds "
                        f"global_max_memory ({recipe.config.global_max_memory})"
                    )

                # Expand task for each specified tamarin version
                for version_name in task.tamarin_versions:
                    if version_name not in recipe.tamarin_versions:
                        raise ConfigError(
                            f"Task '{task_name}' references undefined tamarin version: '{version_name}'"
                        )

                    tamarin_version = recipe.tamarin_versions[version_name]
                    tamarin_executable = Path(tamarin_version.path)

                    # Validate tamarin executable exists
                    if not tamarin_executable.exists():
                        raise ConfigError(
                            f"Tamarin executable not found for version '{version_name}': {tamarin_executable}"
                        )

                    if not tamarin_executable.is_file():
                        raise ConfigError(
                            f"Tamarin executable path is not a file for version '{version_name}': {tamarin_executable}"
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
                            executable_task = ExecutableTask(
                                task_name=task_name,
                                tamarin_version_name=version_name,
                                tamarin_executable=tamarin_executable,
                                theory_file=theory_file,
                                output_file=output_file_path,
                                lemma=lemma.name,
                                tamarin_options=task.tamarin_options,
                                preprocess_flags=task.preprocess_flags,
                                max_cores=max_cores,
                                max_memory=max_memory,
                                task_timeout=task_timeout,
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
                f"✅ Generated {len(executable_tasks)} executable task(s) from recipe"
            )

            return executable_tasks

        except Exception as e:
            error_msg = f"Failed to convert recipe to executable tasks: {e}"
            notification_manager.error(error_msg)
            raise ConfigError(error_msg) from e
