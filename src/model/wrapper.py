from pathlib import Path

from model.tamarin_path import TamarinPath
from modules.tamarin_detector import detect_tamarin_installations
from utils.notifications import notification_manager


class Wrapper:
    def __init__(self) -> None:
        self.tamarin_path: list[TamarinPath] = []

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
                notification_manager.info(f"Removed Tamarin path: {path}")
                return True
        return False

    def get_tamarin_paths(self) -> list[TamarinPath]:
        """
        Returns a list of Tamarin Paths stored in the wrapper.
        Returns:
            list[TamarinPath]: A list of TamarinPath objects.
        """
        return self.tamarin_path

    async def auto_detect_tamarin_paths(self) -> list[TamarinPath]:
        """
        Automatically detects Tamarin Paths and adds them to the wrapper.
        """
        detected_paths: list[TamarinPath] = []
        candidate_paths = detect_tamarin_installations()

        # Validate each candidate path using TamarinPath
        for candidate in candidate_paths:
            try:
                tamarin_path_obj = await TamarinPath.create(candidate)
                # Add if version is detected, even if test fails
                if tamarin_path_obj.version:
                    detected_paths.append(tamarin_path_obj)
                    if tamarin_path_obj.test_success:
                        notification_manager.info(
                            f"Valid tamarin-prover found: {candidate} ({tamarin_path_obj.version})"
                        )
                    else:
                        notification_manager.warning(
                            f"Tamarin-prover found but test failed: {candidate} ({tamarin_path_obj.version}) - may work partially"
                        )
                else:
                    notification_manager.error(
                        f"Invalid tamarin-prover at: {candidate} - no version detected"
                    )
            except Exception as e:
                notification_manager.error(f"Error validating {candidate}: {e}")

        # Update the wrapper's paths
        self.tamarin_path.extend(detected_paths)

        if detected_paths:
            notification_manager.info(
                f"Auto-detection complete. Found {len(detected_paths)} tamarin-prover installation(s)."
            )
        else:
            notification_manager.warning(
                "No valid tamarin-prover installations found during auto-detection."
            )

        return detected_paths
