import json
from pathlib import Path

from pydantic import ValidationError

from model.wrapper import Wrapper
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
