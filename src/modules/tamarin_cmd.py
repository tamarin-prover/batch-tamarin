import re
import subprocess
from pathlib import Path

from utils.notifications import notification_manager


def extract_tamarin_version(path: Path) -> str:
    """
    Extracts the Tamarin version from the given path.

    Args:
        path: Path to the Tamarin executable

    Returns:
        Version string in format "vX.X.X" or empty string if extraction fails
    """
    try:
        # Execute the tamarin-prover --version command
        result = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=30,  # 30 second timeout
        )

        # Check if command executed successfully
        if result.returncode != 0:
            notification_manager.error(
                f"Version command failed with return code {result.returncode}"
            )
            if result.stderr:
                notification_manager.error(f"Error output: {result.stderr}")
            return ""

        # Parse the output to extract version
        output = result.stdout

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

    except subprocess.TimeoutExpired:
        notification_manager.error("Version command timed out")
        return ""
    except subprocess.CalledProcessError as e:
        notification_manager.error(f"Version command execution failed: {e}")
        return ""
    except Exception as e:
        notification_manager.error(f"Unexpected error during version extraction: {e}")
        return ""


def launch_tamarin_test(path: Path) -> bool:
    """
    Launches a Tamarin test command and returns whether it was successful.

    Args:
        path: Path to the Tamarin executable
    """
    try:
        # Execute the tamarin-prover test command
        result = subprocess.run(
            [path, "test"],
            capture_output=True,
            text=True,
            timeout=60,  # 60 second timeout
        )

        # Check if command executed successfully
        if result.returncode != 0:
            notification_manager.error(
                f"Test command failed with return code {result.returncode}"
            )
            if result.stderr:
                notification_manager.error(f"Error output: {result.stderr}")
            return False

        # Parse the output to verify test success
        output = result.stdout

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

    except subprocess.TimeoutExpired:
        notification_manager.error("Tamarin test timed out")
        return False
    except subprocess.CalledProcessError as e:
        notification_manager.error(f"Command execution failed: {e}")
        return False
    except Exception as e:
        notification_manager.error(f"Unexpected error during tamarin test: {e}")
        return False
