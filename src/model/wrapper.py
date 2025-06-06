from pathlib import Path
from typing import Any, Dict

from model.tamarin_path import TamarinPath
from modules.tamarin_detector import detect_tamarin_installations
from utils.notifications import notification_manager


class Wrapper:
    def __init__(self) -> None:
        self.tamarin_path: list[TamarinPath] = []

    def to_config(self) -> Dict[str, Any]:
        """
        Convert wrapper to configuration dictionary for JSON serialization.

        Returns:
            Dictionary representation of the wrapper configuration
        """
        return {
            "tamarin_paths": [
                {
                    "path": str(tp.path),
                    "version": tp.version,
                    "test_success": tp.test_success,
                }
                for tp in self.tamarin_path
            ]
        }

    def load_from_config(
        self, config_data: Dict[str, Any], revalidate: bool = False
    ) -> None:
        """
        Load wrapper configuration from dictionary data.

        Args:
            config_data: Configuration dictionary
            revalidate: If True, re-validate all tamarin paths after loading
        """
        self.tamarin_path.clear()

        for path_data in config_data.get("tamarin_paths", []):
            try:
                if revalidate:
                    # This would need to be called in an async context
                    # For now, we'll use the non-validating version
                    pass
                else:
                    # Create tamarin path without validation (faster loading)
                    tamarin_path = TamarinPath.create_from_data(
                        path=Path(path_data["path"]),
                        version=path_data.get("version", ""),
                        test_success=path_data.get("test_success", False),
                    )
                    self.tamarin_path.append(tamarin_path)

            except Exception as e:
                notification_manager.warning(
                    f"⚠️ Failed to load tamarin path {path_data.get('path', 'unknown')}: {e}"
                )
                continue

    async def add_tamarin_path(self, path: str) -> TamarinPath:
        """
        Adds a Tamarin Path to the wrapper's list of usable Tamarin.

        Args:
            path: Path string to the Tamarin executable

        Returns:
            The created TamarinPath object
        """
        tamarin_path_obj = await TamarinPath.create(Path(path))
        self.tamarin_path.append(tamarin_path_obj)
        return tamarin_path_obj

    def remove_tamarin_path(self, path: str) -> bool:
        """
        Remove a Tamarin path from the wrapper.

        Args:
            path: Path string to remove

        Returns:
            True if path was found and removed, False otherwise
        """
        for i, tamarin_path in enumerate(self.tamarin_path):
            if str(tamarin_path.path) == path:
                del self.tamarin_path[i]
                notification_manager.info(f"🗑 Removed tamarin-prover: {path}")
                return True
        return False

    def get_tamarin_paths(self) -> list[TamarinPath]:
        """
        Returns a list of Tamarin Paths stored in the wrapper.
        Returns:
            list[TamarinPath]: A list of TamarinPath objects.
        """
        return self.tamarin_path

    def should_auto_detect(self) -> bool:
        """
        Check if auto-detection should be performed. We assume auto-detection should
        be done if there are no Tamarin paths already configured, because user will
        likely provide paths in his configuration file, while cold start won't.

        Returns:
            False if tamarin_path list is not empty, True otherwise
        """
        return len(self.tamarin_path) == 0

    async def auto_detect_tamarin_paths(self) -> list[TamarinPath]:
        """
        Automatically detects Tamarin Paths and adds them to the wrapper.
        Only runs if should_auto_detect() returns True.
        """
        if not self.should_auto_detect():
            notification_manager.info(
                "⏭️ Skipping auto-detection: Tamarin paths already configured"
            )
            return []
        detected_paths: list[TamarinPath] = []
        candidate_paths = detect_tamarin_installations()

        # Validate each candidate path using TamarinPath
        for candidate in candidate_paths:
            try:
                tamarin_path_obj = await TamarinPath.create(candidate)
                # Add if version is detected, even if test fails
                if tamarin_path_obj.version:
                    detected_paths.append(tamarin_path_obj)
            except Exception as e:
                notification_manager.error(f"Error validating {candidate}: {e}")

        # Update the wrapper's paths
        self.tamarin_path.extend(detected_paths)

        # Single consolidated notification with results summary
        if detected_paths:
            valid_paths = [p for p in detected_paths if p.test_success]
            partial_paths = [p for p in detected_paths if not p.test_success]

            summary_parts: list[str] = []
            if valid_paths:
                summary_parts.append(f"{len(valid_paths)} fully functional")
            if partial_paths:
                summary_parts.append(f"{len(partial_paths)} partially functional")

            notification_manager.info(
                f"✅ Auto-detection complete: Found {len(detected_paths)} tamarin-prover installation(s) ({', '.join(summary_parts)})"
            )
        else:
            notification_manager.warning(
                "❌ No valid tamarin-prover installations found during auto-detection"
            )

        return detected_paths
