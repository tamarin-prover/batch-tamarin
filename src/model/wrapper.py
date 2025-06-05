from pathlib import Path

from model.tamarin_path import TamarinPath
from modules.tamarin_detector import detect_tamarin_installations
from utils.notifications import notification_manager


class Wrapper:
    def __init__(self) -> None:
        self.tamarin_path = self.auto_detect_tamarin_paths()

    def add_tamarin_path(self, path: str) -> None:
        """
        Adds a Tamarin Path to the wrapper's list of usable Tamarin.

        Args:
            path : The TamarinPath object to add.
        """
        self.tamarin_path.append(TamarinPath(Path(path)))

    def get_tamarin_paths(self) -> list[TamarinPath]:
        """
        Returns a list of Tamarin Paths stored in the wrapper.
        Returns:
            list[TamarinPath]: A list of TamarinPath objects.
        """
        return self.tamarin_path

    def auto_detect_tamarin_paths(self) -> list[TamarinPath]:
        """
        Automatically detects Tamarin Paths and adds them to the wrapper.
        """
        detected_paths = []
        candidate_paths = detect_tamarin_installations()

        # Validate each candidate path using TamarinPath
        for candidate in candidate_paths:
            try:
                tamarin_path_obj = TamarinPath(candidate)
                # Only add if both version extraction and test were successful
                if tamarin_path_obj.version and tamarin_path_obj.test_success:
                    detected_paths.append(tamarin_path_obj)
                    notification_manager.info(
                        f"Valid tamarin-prover found: {candidate} ({tamarin_path_obj.version})"
                    )
                else:
                    notification_manager.warning(
                        f"Invalid tamarin-prover at: {candidate}"
                    )
            except Exception as e:
                notification_manager.warning(f"Error validating {candidate}: {e}")

        if detected_paths:
            notification_manager.info(
                f"Auto-detection complete. Found {len(detected_paths)} valid tamarin-prover installation(s)."
            )
        else:
            notification_manager.warning(
                "No valid tamarin-prover installations found during auto-detection."
            )

        return detected_paths
