import re
from pathlib import Path
from typing import Dict

from ..model.tamarin_recipe import TamarinVersion
from ..utils.notifications import notification_manager
from ..utils.system_resources import resolve_executable_path
from .docker_manager import DockerManager
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
                notification_manager.error(
                    f"[TamarinTest] Error output:\n {chr(10).join(stdout.strip().splitlines()[-4:])}"
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


async def extract_tamarin_versions(tamarin_versions: Dict[str, TamarinVersion]) -> None:
    """
    Extract version information by running --version command for all tamarin configurations.

    Handles both local executables and Docker containers by actually executing
    the --version command to get accurate version information.

    Args:
        tamarin_versions: Dictionary of tamarin versions to extract versions for
    """
    docker_manager = DockerManager()

    for version_name, tamarin_version in tamarin_versions.items():
        try:
            # Handle local executable versions
            if tamarin_version.path:
                try:
                    tamarin_path = resolve_executable_path(tamarin_version.path)
                    extracted_version = await extract_tamarin_version(tamarin_path)
                    if extracted_version:
                        tamarin_version.version = extracted_version
                        notification_manager.debug(
                            f"[TamarinVersion] Extracted version {tamarin_version.version} from local executable for '{version_name}'"
                        )
                    else:
                        notification_manager.warning(
                            f"[TamarinVersion] Could not extract version from local executable for '{version_name}'"
                        )
                        tamarin_version.version = ""
                except (FileNotFoundError, ValueError) as e:
                    notification_manager.warning(
                        f"[TamarinVersion] Local executable resolution failed for '{version_name}': {e}"
                    )
                    tamarin_version.version = ""
                continue

            # Handle Docker-based versions by running temporary containers
            docker_image = None

            if tamarin_version.docker_preset:
                from ..model.tamarin_recipe import DockerPreset

                docker_image = DockerPreset.get_docker_image(
                    tamarin_version.docker_preset.value
                )
            elif tamarin_version.docker_image:
                docker_image = tamarin_version.docker_image.image
            elif tamarin_version.dockerfile:
                # For Dockerfile, we need the built image tag
                if hasattr(tamarin_version.dockerfile, "tag"):
                    docker_image = tamarin_version.dockerfile.tag

            if docker_image:
                try:
                    # Try multiple version extraction strategies for compatibility
                    version_output = None
                    version_strategies = [
                        ["tamarin-prover", "--version"],
                        ["tamarin-prover", "-V"],
                        [
                            "tamarin-prover",
                            "test",
                        ],  # Fallback: extract from test output
                    ]

                    for strategy in version_strategies:
                        version_output = await docker_manager.run_temporary_container(
                            docker_image, strategy, timeout=30.0
                        )
                        if version_output and version_output.get("stdout"):
                            break

                    if version_output:
                        error_type = version_output.get("error_type")
                        stdout = version_output.get("stdout", "")
                        stderr = version_output.get("stderr", "")

                        # Handle specific error types
                        if error_type == "timeout":
                            notification_manager.warning(
                                f"[TamarinVersion] Timeout extracting version from Docker image '{docker_image}' for '{version_name}'"
                            )
                            tamarin_version.version = ""
                        elif error_type == "memory_limit":
                            notification_manager.warning(
                                f"[TamarinVersion] Memory limit exceeded extracting version from Docker image '{docker_image}' for '{version_name}'"
                            )
                            tamarin_version.version = ""
                        elif error_type == "unknown":
                            notification_manager.warning(
                                f"[TamarinVersion] Unknown error extracting version from Docker image '{docker_image}' for '{version_name}': {stderr}"
                            )
                            tamarin_version.version = ""
                        elif stdout:
                            # Parse the output to extract version using multiple strategies
                            version_found = False
                            lines = stdout.split("\n")

                            # Strategy 1: Look for version in standard output format
                            for line in lines:
                                version_patterns = [
                                    r"tamarin-prover\s+(\d+\.\d+\.\d+)",  # Standard format
                                    r"tamarin.*version.*?(\d+\.\d+\.\d+)",  # Tamarin version context
                                    r"version.*tamarin.*?(\d+\.\d+\.\d+)",  # Version tamarin context
                                ]

                                for pattern in version_patterns:
                                    version_match = re.search(pattern, line)
                                    if version_match:
                                        version = version_match.group(1)
                                        tamarin_version.version = f"v{version}"
                                        notification_manager.debug(
                                            f"[TamarinVersion] Extracted version {tamarin_version.version} from Docker image '{docker_image}' for '{version_name}'"
                                        )
                                        version_found = True
                                        break

                                if version_found:
                                    break

                            # Strategy 2: If version not found in output, try extracting from image tag
                            if not version_found and ":" in docker_image:
                                tag_part = docker_image.split(":")[-1]
                                version_match = re.search(r"(\d+\.\d+\.\d+)", tag_part)
                                if version_match:
                                    version = version_match.group(1)
                                    tamarin_version.version = f"v{version}"
                                    notification_manager.warning(
                                        f"[TamarinVersion] Version command failed, using version from image tag: {tamarin_version.version} for '{version_name}'"
                                    )
                                    version_found = True

                            if not version_found:
                                notification_manager.warning(
                                    f"[TamarinVersion] Could not parse version from Docker output or image tag for '{version_name}'"
                                )
                                tamarin_version.version = ""
                        else:
                            # Last resort: try to extract version from Docker image tag
                            if ":" in docker_image:
                                tag_part = docker_image.split(":")[-1]
                                version_match = re.search(r"(\d+\.\d+\.\d+)", tag_part)
                                if version_match:
                                    version = version_match.group(1)
                                    tamarin_version.version = f"v{version}"
                                    notification_manager.warning(
                                        f"[TamarinVersion] Container failed, using version from image tag: {tamarin_version.version} for '{version_name}'"
                                    )
                                else:
                                    notification_manager.warning(
                                        f"[TamarinVersion] Empty response from Docker image '{docker_image}' for '{version_name}'"
                                    )
                                    tamarin_version.version = ""
                            else:
                                notification_manager.warning(
                                    f"[TamarinVersion] Empty response from Docker image '{docker_image}' for '{version_name}'"
                                )
                                tamarin_version.version = ""
                    else:
                        # Final fallback: extract version from Docker image tag
                        if ":" in docker_image:
                            tag_part = docker_image.split(":")[-1]
                            version_match = re.search(r"(\d+\.\d+\.\d+)", tag_part)
                            if version_match:
                                version = version_match.group(1)
                                tamarin_version.version = f"v{version}"
                                notification_manager.warning(
                                    f"[TamarinVersion] Container failed to start, using version from image tag: {tamarin_version.version} for '{version_name}'"
                                )
                            else:
                                notification_manager.warning(
                                    f"[TamarinVersion] Could not extract version from Docker image '{docker_image}' for '{version_name}' - container failed to start"
                                )
                                tamarin_version.version = ""
                        else:
                            notification_manager.warning(
                                f"[TamarinVersion] Could not extract version from Docker image '{docker_image}' for '{version_name}' - container failed to start"
                            )
                            tamarin_version.version = ""
                except Exception as e:
                    notification_manager.warning(
                        f"[TamarinVersion] Failed to run version command in Docker for '{version_name}': {e}"
                    )
                    tamarin_version.version = ""
                continue

            # If we get here, no execution mode was found
            notification_manager.error(
                f"[TamarinVersion] No valid execution mode found for alias '{version_name}'"
            )
            tamarin_version.version = ""

        except Exception as e:
            notification_manager.error(
                f"[TamarinVersion] Failed to extract version for tamarin alias '{version_name}': {e}"
            )
            tamarin_version.version = ""


async def check_tamarin_integrity(tamarin_versions: Dict[str, TamarinVersion]) -> None:
    """
    Test tamarin executables for functionality and update TamarinVersion objects.

    Args:
        versions: Dictionary of tamarin versions to revalidate
    """
    for version_name, tamarin_version in tamarin_versions.items():
        try:
            # Resolve executable path (handles both file paths and bare commands)
            try:
                tamarin_path = resolve_executable_path(tamarin_version.path)
            except (FileNotFoundError, ValueError) as e:
                notification_manager.critical(
                    f"[TamarinTest] Tamarin executable resolution failed for '{version_name}': {e}"
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

        except Exception as e:
            notification_manager.error(
                f"[TamarinTest] Failed to revalidate tamarin alias '{version_name}': {e}"
            )
            tamarin_version.test_success = False
