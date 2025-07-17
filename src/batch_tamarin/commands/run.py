"""
Run command for batch-tamarin.

This module handles the execution of tasks from configuration files.
"""

import asyncio
from pathlib import Path
from typing import Dict

from ..model.batch import Batch
from ..model.tamarin_recipe import TamarinRecipe, TamarinVersion
from ..modules.config_manager import ConfigManager
from ..modules.output_manager import output_manager
from ..runner import TaskRunner
from ..utils.notifications import notification_manager


async def process_config_file(config_path: Path) -> None:
    """Process configuration file and execute tasks using the new Batch model."""
    try:
        # Load recipe from configuration file
        config_manager = ConfigManager()
        recipe = await config_manager.load_json_recipe(config_path)

        # Create initial Batch object from recipe
        batch = config_manager.create_batch_from_recipe(recipe, config_path.name)

        # Initialize TaskRunner - this validates and potentially corrects resource limits
        # The ResourceManager within TaskRunner may update recipe.config with corrected values
        # The TaskRunner also initializes the OutputManager which is needed for creating RichExecutableTask objects
        runner = TaskRunner(recipe)

        # Update batch with resolved configuration after TaskRunner initialization
        batch = await _update_batch_with_resolved_config(batch, recipe, runner)

        # Populate batch with RichExecutableTask objects (after OutputManager is initialized)
        batch = config_manager.recipe_to_rich_executable_tasks(recipe, batch)

        # Execute batch using the new unified workflow
        completed_batch = await runner.execute_batch(batch)

        # Generate execution report (execution_report.json)
        await _generate_execution_report(completed_batch)

    except Exception as e:
        notification_manager.error(f"Execution failed: {e}")
        raise


async def _update_batch_with_resolved_config(
    batch: Batch, recipe: TamarinRecipe, runner: TaskRunner
) -> Batch:
    """Update batch with resolved configuration values from TaskRunner."""
    from ..modules.tamarin_test_cmd import extract_tamarin_version
    from ..utils.system_resources import resolve_executable_path, resolve_resource_value

    # Update config with resolved resource values
    resolved_config = recipe.config.model_copy()
    resolved_config.global_max_cores = resolve_resource_value(
        recipe.config.global_max_cores, "cores"
    )
    resolved_config.global_max_memory = resolve_resource_value(
        recipe.config.global_max_memory, "memory"
    )

    # Create a copy of tamarin_versions with only version parsing (no integrity test)
    resolved_tamarin_versions: Dict[str, TamarinVersion] = {}
    for version_name, version_info in recipe.tamarin_versions.items():
        # Create a copy of the TamarinVersion object
        resolved_version = version_info.model_copy()

        # Only extract version, skip integrity test for execution report
        try:
            tamarin_path = resolve_executable_path(version_info.path)
            extracted_version = await extract_tamarin_version(tamarin_path)
            if extracted_version:
                resolved_version.version = extracted_version
            else:
                resolved_version.version = None
        except Exception:
            resolved_version.version = None

        # Don't run integrity test, just leave test_success as None for execution report
        resolved_tamarin_versions[version_name] = resolved_version

    # Update batch with resolved values
    batch.config = resolved_config
    batch.tamarin_versions = resolved_tamarin_versions

    return batch


async def _generate_execution_report(batch: Batch) -> None:
    """Generate execution_report.json file at the root of the output directory."""
    try:
        # Get output directory paths
        output_paths = output_manager.get_output_paths()
        report_path = output_paths["base"] / "execution_report.json"

        # Write the batch object as JSON, excluding null fields
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(batch.model_dump_json(indent=2, exclude_none=True))

        notification_manager.success(
            f"[RunCommand] Generated execution report: {report_path}"
        )

    except Exception as e:
        notification_manager.error(
            f"[RunCommand] Failed to generate execution report: {e}"
        )
        # Don't raise - this is not a critical failure


class RunCommand:
    """Command class for running batch-tamarin tasks."""

    @staticmethod
    def run(config_file: str, debug: bool = False) -> None:
        """
        Execute tasks from the specified configuration file.

        Args:
            config_file: Path to JSON recipe file to execute
            debug: Enable debug output
        """
        # Set debug mode if enabled
        if debug:
            notification_manager.set_debug(True)
            notification_manager.debug("[NotificationUtil] DEBUG Enabled")

        # Execute config file tasks
        config_path = Path(config_file)
        try:
            asyncio.run(process_config_file(config_path))
        except Exception as e:
            notification_manager.error(f"Failed to process JSON recipe : {e}")
            raise
