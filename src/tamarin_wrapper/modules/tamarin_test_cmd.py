import re
from pathlib import Path
from typing import Dict

from ..model.tamarin_recipe import TamarinVersion
from ..utils.notifications import notification_manager
from .process_manager import process_manager


async def extract_tamarin_version(path: Path) -> str:
    """
    Extracts the Tamarin version from the given path using async process manager.

    Args:
        path: Path to the Tamarin executable

    Returns:
        Version string in format "vX.X.X" or empty string if extraction fails
    """
    try:
        # Execute the tamarin-prover --version command
        return_code, stdout, stderr, _ = await process_manager.run_command(
            path, ["--version"], timeout=30.0
        )

        # Check if command executed successfully
        if return_code != 0:
            notification_manager.error(
                f"[TamarinTest] Version command failed with return code {return_code}"
            )
            if stderr:
                notification_manager.error(f"[TamarinTest] Error output: {stderr}")
            return ""

        # Parse the output to extract version
        output = stdout

        # Look for version pattern in first line: "tamarin-prover X.X.X"
        lines = output.split("\n")
        if lines:
            first_line = lines[0]
            # Use regex to find version pattern
            version_match = re.search(r"tamarin-prover\s+(\d+\.\d+\.\d+)", first_line)
            if version_match:
                version = version_match.group(1)
                formatted_version = f"v{version}"
                return formatted_version
            else:
                notification_manager.error(
                    "[TamarinTest] Could not parse version from output"
                )
                return ""
        else:
            notification_manager.error(
                "[TamarinTest] No output received from version command"
            )
            return ""

    except Exception as e:
        notification_manager.error(
            f"[TamarinTest] Unexpected error during version extraction: {e}"
        )
        return ""


async def launch_tamarin_test(path: Path) -> bool:
    """
    Launches a Tamarin test command and returns whether it was successful.

    Args:
        path: Path to the Tamarin executable
    """
    try:
        # Execute the tamarin-prover test command
        return_code, stdout, _, _ = await process_manager.run_command(
            path, ["test"], timeout=60.0
        )

        # Check if command executed successfully
        if return_code != 0:
            notification_manager.error(
                f"[TamarinTest] Test command failed, tamarin {path} might not work as intended."
            )
            if stdout:
                notification_manager.debug(
                    f"[#ff0000][ERROR][/#ff0000][TamarinTest] Error output:\n {chr(10).join(stdout.strip().splitlines()[-4:])}"
                )
            return False

        # Parse the output to verify test success
        output = stdout

        # Check for key success indicators in the output
        success_indicators = [
            "All tests successful",
            "The tamarin-prover should work as intended",
        ]

        # Verify all success indicators are present
        for indicator in success_indicators:
            if indicator not in output:
                notification_manager.error(
                    f"[TamarinTest] Missing success indicator: '{indicator}'"
                )
                return False

        return True

    except Exception as e:
        notification_manager.error(
            f"[TamarinTest] Unexpected error during tamarin test: {e}"
        )
        return False


async def check_tamarin_integrity(tamarin_versions: Dict[str, TamarinVersion]) -> None:
    """
    Test tamarin executables for functionality and update TamarinVersion objects.

    Args:
        versions: Dictionary of tamarin versions to revalidate
    """
    for version_name, tamarin_version in tamarin_versions.items():
        try:
            tamarin_path = Path(tamarin_version.path)

            # Check if executable exists
            if not tamarin_path.exists():
                notification_manager.critical(
                    f"[TamarinTest] Tamarin executable not found: {tamarin_path}"
                )
                tamarin_version.version = ""
                tamarin_version.test_success = False
                continue

            if not tamarin_path.is_file():
                notification_manager.critical(
                    f"[TamarinTest] Tamarin path is not a file: {tamarin_path}"
                )
                tamarin_version.version = ""
                tamarin_version.test_success = False
                continue

            # Extract version information
            extracted_version = await extract_tamarin_version(tamarin_path)
            if extracted_version:
                tamarin_version.version = extracted_version
            else:
                notification_manager.warning(
                    f"[TamarinTest] Could not extract version for {version_name}"
                )

            # Test tamarin functionality
            test_result = await launch_tamarin_test(tamarin_path)
            tamarin_version.test_success = test_result

            if test_result:
                notification_manager.success(
                    f"[TamarinTest] Tamarin alias '{version_name}' passed integrity test "
                    f"(reported {tamarin_version.version})"
                )
            else:
                # Use interactive prompt for integrity test failures
                notification_manager.warning(
                    f"Tamarin integrity test failed for alias '{version_name}'"
                )
                should_continue = notification_manager.prompt_user(
                    "Would you like to continue anyway ?", default=True
                )

                if not should_continue:
                    notification_manager.critical(
                        f"[TamarinTest] User chose to stop execution due to integrity test failure for '{version_name}'"
                    )

        except Exception as e:
            notification_manager.error(
                f"[TamarinTest] Failed to revalidate tamarin alias '{version_name}': {e}"
            )
            tamarin_version.test_success = False
