"""Configuration management for Tamarin Wrapper."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional


class ConfigManager:
    """Manages configuration for Tamarin Wrapper."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize configuration manager.

        Args:
            config_dir: Custom configuration directory. Defaults to ~/.tamarin-wrapper
        """
        self.config_dir = config_dir or Path.home() / ".tamarin-wrapper"
        self.config_file = self.config_dir / "config.json"
        self._config: Dict = {}

    def load_config(self) -> Dict:
        """Load configuration from file.

        Returns:
            Configuration dictionary
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    self._config = json.load(f)
            else:
                self._config = self._get_default_config()
        except (json.JSONDecodeError, FileNotFoundError):
            self._config = self._get_default_config()

        return self._config

    def save_config(self) -> None:
        """Save configuration to file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(self._config, f, indent=2)

    def _get_default_config(self) -> Dict:
        """Get default configuration.

        Returns:
            Default configuration dictionary
        """
        return {
            "tamarin_paths": [],
            "selected_path": None,
            "last_used_path": None,
            "auto_detect_paths": True,
        }

    def get_tamarin_paths(self) -> List[str]:
        """Get list of configured Tamarin paths.

        Returns:
            List of Tamarin executable paths
        """
        if not self._config:
            self.load_config()
        return self._config.get("tamarin_paths", [])

    def add_tamarin_path(self, path: str) -> bool:
        """Add a new Tamarin path.

        Args:
            path: Path to Tamarin executable

        Returns:
            True if path was added, False if it already exists
        """
        if not self._config:
            self.load_config()

        paths = self._config.get("tamarin_paths", [])
        if path not in paths:
            paths.append(path)
            self._config["tamarin_paths"] = paths
            self.save_config()
            return True
        return False

    def remove_tamarin_path(self, path: str) -> bool:
        """Remove a Tamarin path.

        Args:
            path: Path to remove

        Returns:
            True if path was removed, False if it wasn't found
        """
        if not self._config:
            self.load_config()

        paths = self._config.get("tamarin_paths", [])
        if path in paths:
            paths.remove(path)
            self._config["tamarin_paths"] = paths

            # Clear selected path if it was the one removed
            if self._config.get("selected_path") == path:
                self._config["selected_path"] = None
            if self._config.get("last_used_path") == path:
                self._config["last_used_path"] = None

            self.save_config()
            return True
        return False

    def set_selected_path(self, path: str) -> None:
        """Set the selected Tamarin path.

        Args:
            path: Path to set as selected
        """
        if not self._config:
            self.load_config()

        self._config["selected_path"] = path
        self._config["last_used_path"] = path
        self.save_config()

    def get_selected_path(self) -> Optional[str]:
        """Get the currently selected Tamarin path.

        Returns:
            Selected path or None if none is selected
        """
        if not self._config:
            self.load_config()
        return self._config.get("selected_path")

    def get_last_used_path(self) -> Optional[str]:
        """Get the last used Tamarin path.

        Returns:
            Last used path or None if none exists
        """
        if not self._config:
            self.load_config()
        return self._config.get("last_used_path")

    def auto_detect_tamarin_paths(self) -> List[str]:
        """Auto-detect Tamarin installations on the system.

        Returns:
            List of detected Tamarin paths
        """
        detected_paths = []

        # Common installation paths
        common_paths = [
            "/usr/local/bin/tamarin-prover",
            "/usr/bin/tamarin-prover",
            "/opt/tamarin-prover/bin/tamarin-prover",
            Path.home() / ".local/bin/tamarin-prover",
            Path.home() / "bin/tamarin-prover",
        ]

        # Check common paths
        for path in common_paths:
            path_obj = Path(path)
            if path_obj.exists() and path_obj.is_file():
                detected_paths.append(str(path_obj))

        # Check PATH environment variable
        path_env = os.environ.get("PATH", "")
        for path_dir in path_env.split(os.pathsep):
            if path_dir:
                tamarin_path = Path(path_dir) / "tamarin-prover"
                if tamarin_path.exists() and tamarin_path.is_file():
                    path_str = str(tamarin_path)
                    if path_str not in detected_paths:
                        detected_paths.append(path_str)

        return detected_paths

    def validate_path(self, path: str) -> bool:
        """Validate that a path points to a valid Tamarin executable.

        Args:
            path: Path to validate

        Returns:
            True if path is valid, False otherwise
        """
        path_obj = Path(path)
        return path_obj.exists() and path_obj.is_file() and os.access(path, os.X_OK)
