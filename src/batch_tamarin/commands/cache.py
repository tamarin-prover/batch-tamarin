"""
Cache command for batch-tamarin.

This module handles cache interaction commands.
"""

import typer

from ..modules.cache_manager import CacheManager
from ..utils.system_resources import get_human_readable_volume_size

cache_command = typer.Typer(name="cache", help="Interaction with the cache")


@cache_command.command()
def clear(
    errors_only: bool = typer.Option(
        False, "--errors-only", "-e", help="Only clear failed/error tasks"
    )
) -> None:
    """Clear the cache.

    Args:
        errors_only (bool, optional): Clear only error/failed tasks. Defaults to False.
    """

    CacheCommand.clear(errors_only=errors_only)


class CacheCommand:
    """Command class for interacting with the batch-tamarin cache."""

    @staticmethod
    def clear(errors_only: bool = False) -> None:
        """
        Clears the cache using the given options.

        Args:
            errors_only (bool, optional): Only clear errors. Defaults to False.
        """

        try:
            cache_manager = CacheManager()
            stats_before = cache_manager.get_stats()
            cache_manager.clear_cache(errors_only=errors_only)
            stats_after = cache_manager.get_stats()
            entries = stats_before["size"] - stats_after["size"]
            volume = get_human_readable_volume_size(
                stats_before["volume"] - stats_after["volume"]
            )

            print(f"Cleared cache: {entries} entries, {volume}")
        except Exception as e:
            print(f"Failed to clear cache: {e}")
            raise typer.Exit(1)
        return
