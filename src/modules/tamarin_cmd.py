import re
from pathlib import Path

from modules.process_manager import process_manager
from utils.notifications import notification_manager


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
        return_code, stdout, stderr = await process_manager.run_command(
            path, ["--version"], timeout=30.0
        )

        # Check if command executed successfully
        if return_code != 0:
            notification_manager.error(
                f"Version command failed with return code {return_code}"
            )
            if stderr:
                notification_manager.error(f"Error output: {stderr}")
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
                notification_manager.info(
                    f"Extracted Tamarin version: {formatted_version}"
                )
                return formatted_version
            else:
                notification_manager.error("Could not parse version from output")
                return ""
        else:
            notification_manager.error("No output received from version command")
            return ""

    except Exception as e:
        notification_manager.error(f"Unexpected error during version extraction: {e}")
        return ""


async def launch_tamarin_test(path: Path) -> bool:
    """
    Launches a Tamarin test command and returns whether it was successful.

    Args:
        path: Path to the Tamarin executable
    """
    try:
        # Execute the tamarin-prover test command
        return_code, stdout, stderr = await process_manager.run_command(
            path, ["test"], timeout=60.0
        )

        # Check if command executed successfully
        if return_code != 0:
            notification_manager.error(
                f"Test command failed with return code {return_code}"
            )
            if stderr:
                notification_manager.error(f"Error output: {stderr}")
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
                notification_manager.error(f"Missing success indicator: {indicator}")
                return False

        notification_manager.info("Tamarin test completed successfully")
        return True

    except Exception as e:
        notification_manager.error(f"Unexpected error during tamarin test: {e}")
        return False
