"""
Run command for batch-tamarin.

This module handles the execution of tasks from configuration files.
"""

import asyncio
from pathlib import Path

from ..modules.config_manager import ConfigManager
from ..runner import TaskRunner
from ..utils.notifications import notification_manager


async def process_config_file(config_path: Path) -> None:
    """Process configuration file and execute tasks."""
    try:
        # Load recipe from configuration file
        config_manager = ConfigManager()
        recipe = await config_manager.load_json_recipe(config_path)

        # Initialize TaskRunner - this validates and potentially corrects resource limits
        # The ResourceManager within TaskRunner may update recipe.config with corrected values
        runner = TaskRunner(recipe)

        # Convert recipe to executable tasks using the recipe
        executable_tasks = config_manager.recipe_to_executable_tasks(recipe)

        # Execute all tasks using runner
        await runner.execute_all_tasks(executable_tasks)

    except Exception as e:
        notification_manager.error(f"Execution failed: {e}")
        raise


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
