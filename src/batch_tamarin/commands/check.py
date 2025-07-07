"""
Check command for batch-tamarin.

This module handles the validation and preview of configuration files.
"""

import asyncio
from pathlib import Path

from ..modules.config_manager import ConfigManager
from ..modules.output_manager import output_manager
from ..modules.tamarin_test_cmd import check_tamarin_integrity
from ..utils.model_checking import validate_with_tamarin
from ..utils.notifications import notification_manager


async def check_command_logic(config_path: Path, report: bool) -> None:
    """Check configuration and show executable tasks that would be run."""
    try:
        # Load recipe from configuration file
        config_manager = ConfigManager()
        recipe = await config_manager.load_json_recipe(config_path)

        # Check tamarin integrity
        await check_tamarin_integrity(recipe.tamarin_versions)

        # Initialize output manager (bypass directory creation)
        output_manager.initialize(Path(recipe.config.output_directory), bypass=True)

        # Convert recipe to executable tasks
        executable_tasks = config_manager.recipe_to_executable_tasks(recipe)

        # Collect tamarin validation errors
        tamarin_errors = await validate_with_tamarin(executable_tasks, report)

        # Display the check report
        notification_manager.check_report(recipe, executable_tasks, tamarin_errors)

    except Exception as e:
        notification_manager.error(f"Check failed: {e}")
        raise


class CheckCommand:
    """Command class for checking batch-tamarin configurations."""

    @staticmethod
    def run(config_file: str, report: bool = False, debug: bool = False) -> None:
        """
        Check configuration and show executable tasks that would be run.

        Args:
            config_file: Path to JSON recipe file to check
            report: Give Tamarin output report
            debug: Enable debug output
        """
        # Set debug mode if enabled
        if debug:
            notification_manager.set_debug(True)
            notification_manager.debug("[NotificationUtil] DEBUG Enabled")

        config_path = Path(config_file)
        try:
            asyncio.run(check_command_logic(config_path, report))
        except Exception as e:
            notification_manager.error(f"Failed to check configuration: {e}")
            raise
