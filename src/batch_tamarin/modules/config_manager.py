import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
from ..utils.system_resources import resolve_executable_path, resolve_resource_value
from .lemma_parser import LemmaParser, LemmaParsingError
from .output_manager import output_manager


@dataclass
class LemmaConfig:
    """Configuration for a single lemma after filtering and parameter application."""

    lemma_name: str
    effective_tamarin_versions: List[str]
    tamarin_options: Optional[List[str]]
    preprocess_flags: Optional[List[str]]
    max_cores: int
    max_memory: int
    timeout: int


class ConfigError(Exception):
    """Exception raised for configuration-related errors."""


class ConfigManager:
    """Manages wrapper configuration serialization and deserialization."""

    task_id_counter: Dict[str, int] = {}

    @staticmethod
    async def load_json_recipe(config_path: Path) -> TamarinRecipe:
        """
        Load TamarinRecipe configuration from a JSON file.

        Args:
            config_path: Path to the configuration file

        Returns:
            Configured TamarinRecipe instance

        Raises:
            ConfigError: If loading or validation fails
        """
        json_data = ""  # Initialize to avoid unbound variable warning
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

            notification_manager.phase_separator("Configuration")
            notification_manager.success(
                f"[ConfigManager] JSON recipe loaded from {config_path} with "
                f"({len(recipe.tamarin_versions)} tamarin version(s), {len(recipe.tasks)} task(s))"
            )

            return recipe

        except ValidationError as e:
            # Check if this is an extra_forbidden error and show context
            ConfigManager._handle_validation_error(e, config_path, json_data)
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
            output_paths = output_manager.get_output_paths()
            models_dir = output_paths["models"]

            for task_name, task in recipe.tasks.items():
                theory_file = ConfigManager.validate_theory_file(
                    task.theory_file, task_name
                )

                ConfigManager._handle_config(
                    task_name, task, recipe, models_dir, theory_file, executable_tasks
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
    def _handle_config(
        task_name: str,
        task: Task,
        recipe: TamarinRecipe,
        models_dir: Path,
        theory_file: Path,
        executable_tasks: List[ExecutableTask],
    ) -> None:
        """
        Create executable tasks by parsing lemmas from theory file and applying filters.

        This function:
        1. Parses all lemmas from the theory file
        2. Eventually, filters lemmas based on task configuration (if task.lemmas is set) and extracts config for each lemma with inheritance rule
        3. Creates one ExecutableTask per kept lemma per tamarin version

        Args:
            task_name: Name of the original task
            task: Task configuration
            recipe: Full recipe configuration
            models_dir: Directory for output models
            theory_file: Path to the theory file
            executable_tasks: List to append new ExecutableTask instances
        """
        try:
            # Step 1: Parse all lemmas from the theory file with task-level preprocessor flags
            parser = LemmaParser(task.preprocess_flags)
            all_lemmas = parser.parse_lemmas_from_file(theory_file)

            if not all_lemmas:
                notification_manager.warning(
                    f"[ConfigManager] No lemmas found in theory file {theory_file} for task '{task_name}'"
                )
                return

            notification_manager.debug(
                f"[ConfigManager] Found {len(all_lemmas)} lemmas in {theory_file} for task '{task_name}': {all_lemmas}"
            )
        except LemmaParsingError as e:
            error_msg = f"[ConfigManager] Failed to parse lemmas from theory file {theory_file} for task '{task_name}':\n{e}"
            raise ConfigError(error_msg) from e
        except Exception as e:
            error_msg = f"[ConfigManager] Unexpected error parsing lemmas from {theory_file} for task '{task_name}': \n{e}"
            raise ConfigError(error_msg) from e

        # Step 2: Filter lemmas based on task configuration and Extract effective configurations for each lemma
        lemma_configs = ConfigManager._filter_and_configure_lemmas(
            task_name, task, recipe, all_lemmas
        )

        if not lemma_configs:
            notification_manager.warning(
                f"[ConfigManager] No lemma configurations generated for task '{task_name}'"
            )
            return

        # Step 3: Create ExecutableTask instances for each lemma
        ConfigManager._create_executable_tasks(
            task_name,
            task,
            recipe,
            models_dir,
            theory_file,
            lemma_configs,
            executable_tasks,
        )

    @staticmethod
    def validate_theory_file(theory_file_path: str, task_name: str) -> Path:
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
    def _filter_and_configure_lemmas(
        task_name: str, task: Task, recipe: TamarinRecipe, all_lemmas: List[str]
    ) -> List[LemmaConfig]:
        """
        Filter lemmas based on task configuration and create lemma configurations.

        Args:
            task_name: Name of the original task
            task: Task configuration
            recipe: Full recipe configuration
            all_lemmas: List of all lemmas parsed from theory file

        Returns:
            List of LemmaConfig objects with effective configurations
        """
        lemma_configs: List[LemmaConfig] = []

        if not task.lemmas:
            # Scenario A: No lemmas specified - use all lemmas with task config
            notification_manager.debug(
                f"[ConfigManager] No lemmas specified for task '{task_name}', using all {len(all_lemmas)} lemmas"
            )

            for lemma_name in all_lemmas:
                lemma_config = ConfigManager._create_lemma_config(
                    lemma_name, task, recipe, None, task_name
                )
                lemma_configs.append(lemma_config)
        else:
            # Scenario B: Lemmas specified - filter by prefix matching and apply per-lemma config
            notification_manager.debug(
                f"[ConfigManager] Filtering lemmas for task '{task_name}' using {len(task.lemmas)} lemma specifications"
            )

            for lemma_spec in task.lemmas:
                # Find matching lemmas using prefix matching
                matching_lemmas = [
                    parsed_lemma
                    for parsed_lemma in all_lemmas
                    if lemma_spec.name in parsed_lemma
                ]

                if not matching_lemmas:
                    notification_manager.warning(
                        f"[ConfigManager] No lemmas found matching prefix '{lemma_spec.name}' in task '{task_name}'"
                    )
                    continue

                notification_manager.debug(
                    f"[ConfigManager] Lemma spec '{lemma_spec.name}' matched {len(matching_lemmas)} lemmas: {matching_lemmas}"
                )

                # Create LemmaConfig for each matching lemma
                for matched_lemma_name in matching_lemmas:
                    lemma_config = ConfigManager._create_lemma_config(
                        matched_lemma_name, task, recipe, lemma_spec, task_name
                    )
                    lemma_configs.append(lemma_config)

        return lemma_configs

    @staticmethod
    def _create_lemma_config(
        lemma_name: str,
        task: Task,
        recipe: TamarinRecipe,
        lemma_spec: Optional[Lemma],
        task_name: str,
    ) -> LemmaConfig:
        """
        Create a LemmaConfig with proper inheritance from task and global settings.

        Args:
            lemma_name: Name of the lemma
            task: Task configuration
            recipe: Full recipe configuration
            lemma_spec: Optional lemma specification (None means inherit from task)
            task_name: Name of the task (for error reporting)

        Returns:
            LemmaConfig with resolved settings
        """
        # Resolve resources following: lemma → task → global defaults
        cores, memory, timeout = ConfigManager._resolve_resources(
            lemma_spec, task, recipe, task_name
        )

        # Resolve other settings with complete override (no merging)
        if lemma_spec is not None:
            effective_tamarin_versions: List[str] = (
                lemma_spec.tamarin_versions
                if lemma_spec.tamarin_versions is not None
                else task.tamarin_versions
            )
            tamarin_options: Optional[List[str]] = (
                lemma_spec.tamarin_options
                if lemma_spec.tamarin_options is not None
                else task.tamarin_options
            )
            preprocess_flags: Optional[List[str]] = (
                lemma_spec.preprocess_flags
                if lemma_spec.preprocess_flags is not None
                else task.preprocess_flags
            )
        else:
            effective_tamarin_versions = task.tamarin_versions
            tamarin_options = task.tamarin_options
            preprocess_flags = task.preprocess_flags

        return LemmaConfig(
            lemma_name=lemma_name,
            effective_tamarin_versions=effective_tamarin_versions,
            tamarin_options=tamarin_options,
            preprocess_flags=preprocess_flags,
            max_cores=cores,
            max_memory=memory,
            timeout=timeout,
        )

    @staticmethod
    def _resolve_resources(
        lemma_spec: Optional[Lemma], task: Task, recipe: TamarinRecipe, task_name: str
    ) -> Tuple[int, int, int]:
        """
        Resolve resources following inheritance chain: lemma → task → global defaults.

        Args:
            lemma_spec: Optional lemma specification
            task: Task configuration
            recipe: Full recipe configuration
            task_name: Name of the task (for error reporting)

        Returns:
            Tuple of (cores, memory, timeout)
        """
        global_config = recipe.config

        # Start with global defaults
        default_cores = 4
        default_memory = 16  # in GB
        default_timeout = global_config.default_timeout

        # Apply task-level overrides
        if task.resources is not None:
            cores: int = (
                task.resources.max_cores
                if task.resources.max_cores is not None
                else default_cores
            )
            memory: int = (
                task.resources.max_memory
                if task.resources.max_memory is not None
                else default_memory
            )
            timeout: int = (
                task.resources.timeout
                if task.resources.timeout is not None
                else default_timeout
            )
        else:
            cores, memory, timeout = default_cores, default_memory, default_timeout

        # Validate against global limits after task-level overrides
        cores, memory = ConfigManager.validate_and_cap_resources(
            cores, memory, global_config, f"Task '{task_name}'"
        )

        # Apply lemma-level overrides (if lemma specified), bypassing global caps
        if lemma_spec is not None and lemma_spec.resources is not None:
            cores = (
                lemma_spec.resources.max_cores
                if lemma_spec.resources.max_cores is not None
                else cores
            )
            memory = (
                lemma_spec.resources.max_memory
                if lemma_spec.resources.max_memory is not None
                else memory
            )
            timeout = (
                lemma_spec.resources.timeout
                if lemma_spec.resources.timeout is not None
                else timeout
            )
        return cores, memory, timeout

    @staticmethod
    def _create_executable_tasks(
        task_name: str,
        task: Task,
        recipe: TamarinRecipe,
        models_dir: Path,
        theory_file: Path,
        lemma_configs: List[LemmaConfig],
        executable_tasks: List[ExecutableTask],
    ) -> None:
        """
        Create ExecutableTask instances for each lemma configuration × tamarin version.

        Args:
            task_name: Name of the original task
            task: Task configuration
            recipe: Full recipe configuration
            models_dir: Directory for output models
            theory_file: Path to the theory file
            lemma_configs: List of lemma configurations
            executable_tasks: List to append new ExecutableTask instances
        """
        notification_manager.debug(
            f"[ConfigManager] Creating ExecutableTasks for task '{task_name}':\n{lemma_configs}"
        )
        for lemma_config in lemma_configs:
            for tamarin_version in lemma_config.effective_tamarin_versions:
                # Validate tamarin executable exists
                if tamarin_version not in recipe.tamarin_versions:
                    raise ConfigError(
                        f"[ConfigManager] Tamarin version '{tamarin_version}' not found in recipe for task '{task_name}'"
                    )

                tamarin_executable = ConfigManager.validate_tamarin_executable(
                    tamarin_version, recipe.tamarin_versions[tamarin_version], recipe
                )

                # Generate unique task ID
                task_suffix = f"{lemma_config.lemma_name}--{tamarin_version}"
                base_task_id = f"{task.output_file_prefix}--{task_suffix}"
                unique_task_id = ConfigManager.get_unique_task_id(base_task_id)

                # Create ExecutableTask
                executable_task = ExecutableTask(
                    task_name=unique_task_id,
                    tamarin_version_name=tamarin_version,
                    tamarin_executable=tamarin_executable,
                    theory_file=theory_file,
                    output_file=models_dir / f"{unique_task_id}.spthy",
                    lemma=lemma_config.lemma_name,
                    tamarin_options=lemma_config.tamarin_options,
                    preprocess_flags=lemma_config.preprocess_flags,
                    max_cores=lemma_config.max_cores,
                    max_memory=lemma_config.max_memory,
                    task_timeout=lemma_config.timeout,
                )

                executable_tasks.append(executable_task)

                notification_manager.debug(
                    f"[ConfigManager] Created ExecutableTask '{unique_task_id}' for lemma '{lemma_config.lemma_name}' with Tamarin '{tamarin_version}'"
                )

    @staticmethod
    def validate_and_cap_resources(
        max_cores: int, max_memory: int, global_config: GlobalConfig, context_name: str
    ) -> Tuple[int, int]:
        """Validate and cap resources against global limits."""
        glob_max_cores = resolve_resource_value(global_config.global_max_cores, "cores")
        glob_max_memory = resolve_resource_value(
            global_config.global_max_memory, "memory"
        )

        if max_cores > glob_max_cores:
            notification_manager.warning(
                f"{context_name} max_cores ({max_cores}c) exceeds global_max_cores, falling back to this value : {glob_max_cores}c"
            )
            max_cores = glob_max_cores

        if max_memory > glob_max_memory:
            notification_manager.warning(
                f"{context_name} max_memory ({max_memory}GB) exceeds global_max_memory, falling back to this value : {glob_max_memory}GB"
            )
            max_memory = glob_max_memory

        return max_cores, max_memory

    @staticmethod
    def validate_tamarin_executable(
        version_name: str, tamarin_version: TamarinVersion, recipe: TamarinRecipe
    ) -> Path:
        """Validate that tamarin executable exists and is a file."""
        try:
            tamarin_executable = resolve_executable_path(tamarin_version.path)
            return tamarin_executable
        except FileNotFoundError as e:
            raise ConfigError(
                f"[ConfigManager] Tamarin executable not found for alias '{version_name}': {e}"
            ) from e
        except ValueError as e:
            raise ConfigError(
                f"[ConfigManager] Tamarin executable path is not a file for alias '{version_name}': {e}"
            ) from e

    @staticmethod
    def _handle_validation_error(
        error: ValidationError, config_path: Path, json_data: str
    ) -> None:
        """
        Handle ValidationError and show JSON context for better user understanding.

        Args:
            error: The ValidationError that occurred
            config_path: Path to the configuration file
            json_data: The raw JSON data that was being validated
        """
        for err in error.errors():
            location = err.get("loc", ())
            error_type = err.get("type", "unknown")

            if error_type == "extra_forbidden" and location:
                # Show context for unrecognized parameters
                extra_field_name = str(location[-1])
                ConfigManager._show_json_context_with_highlighting(
                    json_data,
                    extra_field_name,
                    f"Unrecognized parameter '{extra_field_name}'",
                    config_path,
                )
                break  # Show only the first extra field error

    @staticmethod
    def _show_json_context_with_highlighting(
        json_data: str, search_term: str, error_msg: str, config_path: Path
    ) -> None:
        """
        Show JSON context around a problematic field with Rich syntax highlighting.

        Args:
            json_data: The raw JSON data
            search_term: Term to search for in the JSON (field name)
            error_msg: Error message to display
            config_path: Path to the configuration file
        """
        json_lines = json_data.split("\n")

        # Find the line containing the search term
        target_line_idx = None
        for i, line in enumerate(json_lines):
            if search_term and f'"{search_term}"' in line:
                target_line_idx = i
                break

        if target_line_idx is None:
            notification_manager.critical(
                f"[ConfigManager] {error_msg} in {config_path}"
            )
            return

        # Show 7 context lines (3 before, line itself, 3 after)
        context_start = max(0, target_line_idx - 3)
        context_end = min(len(json_lines), target_line_idx + 4)

        # Build the formatted message with line numbers and highlighting
        lines = [f"[ConfigManager] {error_msg} in {config_path}:"]

        for i in range(context_start, context_end):
            line_number = i + 1
            line_content = json_lines[i]

            if i == target_line_idx:
                # Highlight the problematic line
                lines.append(
                    f"  [bold red]>>>[/bold red] [dim]{line_number:3d}:[/dim] {line_content}"
                )
            else:
                lines.append(f"      [dim]{line_number:3d}:[/dim] {line_content}")

        # Send the formatted message through the notification system
        formatted_message = "\n".join(lines)
        notification_manager.critical(formatted_message)

    @staticmethod
    def get_unique_task_id(base_task_id: str) -> str:
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
