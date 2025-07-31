"""
Run command for batch-tamarin.

This module handles the execution of tasks from configuration files.
"""

import asyncio
from pathlib import Path

from ..model.tamarin_recipe import SchedulingStrategy
from ..modules.batch_manager import BatchManager
from ..modules.config_manager import ConfigManager
from ..runner import TaskRunner
from ..utils.notifications import notification_manager


async def process_config_file(
    config_path: Path, scheduler: SchedulingStrategy = SchedulingStrategy.FIFO
) -> None:
    """Process configuration file and execute tasks using unified direct path."""
    try:
        # Load recipe from configuration file
        config_manager = ConfigManager()
        recipe = await config_manager.load_json_recipe(config_path)

        # Initialize TaskRunner - this validates and potentially corrects resource limits
        runner = TaskRunner(recipe, scheduler)

        # Convert recipe to executable tasks directly (unified path like check.py)
        executable_tasks = config_manager.recipe_to_executable_tasks(recipe)

        # Execute tasks using the direct execution path
        await runner.execute_all_tasks(executable_tasks)

        # Create BatchManager to handle batch operations and generate report
        batch_manager = BatchManager(recipe, config_path.name)
        await batch_manager.generate_execution_report(runner, executable_tasks)

    except Exception as e:
        notification_manager.error(f"Execution failed: {e}")
        raise


class RunCommand:
    """Command class for running batch-tamarin tasks."""

    @staticmethod
    def run(
        config_file: str,
        debug: bool = False,
        scheduler: SchedulingStrategy = SchedulingStrategy.FIFO,
    ) -> None:
        """
        Execute tasks from the specified configuration file.

        Args:
            config_file: Path to JSON recipe file to execute
            debug: Enable debug output
            scheduler: Task scheduling strategy
        """
        # Set debug mode if enabled
        if debug:
            notification_manager.set_debug(True)
            notification_manager.debug("[NotificationUtil] DEBUG Enabled")

        # Execute config file tasks
        config_path = Path(config_file)
        try:
            asyncio.run(process_config_file(config_path, scheduler))
        except Exception as e:
            notification_manager.error(f"Failed to process JSON recipe : {e}")
            raise
