import json
from pathlib import Path
from typing import Any, Dict

from model.tamarin_path import TamarinPath
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
            config_data = ConfigManager._wrapper_to_dict(wrapper)

            # Ensure parent directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

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
                config_data = json.load(f)

            ConfigManager._validate_config_structure(config_data)
            wrapper = await ConfigManager._dict_to_wrapper(config_data, revalidate)

            notification_manager.info(
                f"✅ Configuration loaded from {config_path} "
                f"({len(wrapper.tamarin_path)} tamarin path(s))"
            )

            return wrapper

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in configuration file {config_path}: {e}"
            notification_manager.error(error_msg)
            raise ConfigError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to load configuration from {config_path}: {e}"
            notification_manager.error(error_msg)
            raise ConfigError(error_msg) from e

    @staticmethod
    def _wrapper_to_dict(wrapper: Wrapper) -> Dict[str, Any]:
        """Convert a Wrapper instance to a dictionary."""
        return {
            "tamarin_paths": [
                ConfigManager._tamarin_path_to_dict(tp) for tp in wrapper.tamarin_path
            ]
        }

    @staticmethod
    def _tamarin_path_to_dict(tamarin_path: TamarinPath) -> Dict[str, Any]:
        """Convert a TamarinPath instance to a dictionary."""
        return {
            "path": str(tamarin_path.path),
            "version": tamarin_path.version,
            "test_success": tamarin_path.test_success,
        }

    @staticmethod
    async def _dict_to_wrapper(
        config_data: Dict[str, Any], revalidate: bool = False
    ) -> Wrapper:
        """
        Convert a dictionary to a Wrapper instance.

        Args:
            config_data: Dictionary containing configuration data
            revalidate: If True, re-validate all tamarin paths

        Returns:
            Configured Wrapper instance
        """
        wrapper = Wrapper()

        for path_data in config_data.get("tamarin_paths", []):
            try:
                if revalidate:
                    # Create and validate tamarin path
                    tamarin_path = await TamarinPath.create(Path(path_data["path"]))
                else:
                    # Create tamarin path without validation (faster loading)
                    tamarin_path = TamarinPath.create_from_data(
                        path=Path(path_data["path"]),
                        version=path_data.get("version", ""),
                        test_success=path_data.get("test_success", False),
                    )

                wrapper.tamarin_path.append(tamarin_path)

            except Exception as e:
                notification_manager.warning(
                    f"⚠️ Failed to load tamarin path {path_data.get('path', 'unknown')}: {e}"
                )
                continue

        return wrapper

    @staticmethod
    def _validate_config_structure(config_data: Any) -> None:
        """
        Validate the structure of configuration data.

        Args:
            config_data: Data to validate

        Raises:
            ConfigError: If validation fails
        """
        if not isinstance(config_data, dict):
            raise ConfigError("Configuration must be a JSON object")

        if "tamarin_paths" not in config_data:
            raise ConfigError("Configuration must contain 'tamarin_paths' field")

        tamarin_paths = config_data["tamarin_paths"]  # type: ignore
        if not isinstance(tamarin_paths, list):
            raise ConfigError("'tamarin_paths' must be an array")

        for i, path_data in enumerate(tamarin_paths):  # type: ignore
            if not isinstance(path_data, dict):
                raise ConfigError(f"tamarin_paths[{i}] must be an object")

            if "path" not in path_data:
                raise ConfigError(f"tamarin_paths[{i}] must contain 'path' field")

            if not isinstance(path_data["path"], str):
                raise ConfigError(f"tamarin_paths[{i}].path must be a string")

            # Optional fields validation
            if "version" in path_data and not isinstance(path_data["version"], str):
                raise ConfigError(f"tamarin_paths[{i}].version must be a string")

            if "test_success" in path_data and not isinstance(
                path_data["test_success"], bool
            ):
                raise ConfigError(f"tamarin_paths[{i}].test_success must be a boolean")

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
                config_data = json.load(f)

            ConfigManager._validate_config_structure(config_data)
            return True

        except Exception:
            return False
