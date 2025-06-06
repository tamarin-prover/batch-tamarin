import os
import platform
import subprocess
from pathlib import Path

from utils.notifications import notification_manager


def detect_tamarin_installations() -> list[Path]:
    """
    Detect tamarin-prover installations on the system.

    Returns:
        list[Path]: List of paths to potential tamarin-prover executables
    """
    candidate_paths: set[Path] = set()  # Use set to avoid duplicates

    # 1. Check PATH environment variable
    path_candidates = _check_path_environment()
    candidate_paths.update(path_candidates)

    # 2. Check common installation directories
    common_candidates = _check_common_directories()
    candidate_paths.update(common_candidates)

    # 3. Check package manager specific locations
    package_candidates = _check_package_manager_locations()
    candidate_paths.update(package_candidates)

    return list(candidate_paths)


def _check_path_environment() -> list[Path]:
    """Check if tamarin-prover is available in PATH."""
    candidates: list[Path] = []
    try:
        # Determine the command based on OS
        if platform.system() == "Windows":
            cmd = ["where", "tamarin-prover"]
        else:
            cmd = ["which", "tamarin-prover"]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0 and result.stdout.strip():
            # Parse output - there might be multiple paths
            paths = result.stdout.strip().split("\n")
            for path_str in paths:
                path_str = path_str.strip()
                if path_str:
                    candidates.append(Path(path_str))

    except Exception as e:
        notification_manager.warning(f"Error checking PATH environment: {e}")

    return candidates


def _check_common_directories() -> list[Path]:
    """Check common installation directories for tamarin-prover."""
    candidates: list[Path] = []
    system = platform.system()

    # Define common directories based on OS
    if system == "Darwin":  # macOS
        common_dirs: list[str | Path] = [
            "/usr/local/bin",
            "/opt/homebrew/bin",
            "/usr/bin",
            "/opt/local/bin",  # MacPorts
            Path.home() / ".local" / "bin",
            Path.home() / "bin",
        ]
    elif system == "Linux":
        common_dirs: list[str | Path] = [
            "/usr/bin",
            "/usr/local/bin",
            "/opt/bin",
            Path.home() / ".local" / "bin",
            Path.home() / "bin",
            "/snap/bin",  # Snap packages
        ]
    elif system == "Windows":
        common_dirs: list[str | Path] = [
            Path("C:/Program Files"),
            Path("C:/Program Files (x86)"),
            Path.home() / "AppData" / "Local" / "Programs",
            Path.home() / "AppData" / "Roaming",
        ]
    else:
        # Generic Unix-like system
        common_dirs: list[str | Path] = [
            "/usr/bin",
            "/usr/local/bin",
            Path.home() / ".local" / "bin",
            Path.home() / "bin",
        ]

    # Check each directory for tamarin-prover executable
    for directory in common_dirs:
        try:
            dir_path = Path(directory)
            if dir_path.exists() and dir_path.is_dir():
                # Look for tamarin-prover executable
                if system == "Windows":
                    executable_names = ["tamarin-prover.exe", "tamarin-prover"]
                else:
                    executable_names = ["tamarin-prover"]

                for exe_name in executable_names:
                    exe_path = dir_path / exe_name
                    if exe_path.exists() and exe_path.is_file():
                        # Check if file is executable (Unix-like systems)
                        if system != "Windows" and not os.access(exe_path, os.X_OK):
                            continue
                        candidates.append(exe_path)
        except Exception as e:
            notification_manager.warning(f"Error checking directory {directory}: {e}")

    return candidates


def _check_package_manager_locations() -> list[Path]:
    """Check package manager specific locations."""
    candidates: list[Path] = []
    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            # Check Homebrew locations
            homebrew_candidates = _check_homebrew_locations()
            candidates.extend(homebrew_candidates)

            # Check MacPorts
            macports_path = Path("/opt/local/bin/tamarin-prover")
            if macports_path.exists():
                candidates.append(macports_path)

        # Check Haskell Stack/Cabal locations (cross-platform)
        stack_candidates = _check_haskell_locations()
        candidates.extend(stack_candidates)

        # Check Nix locations (cross-platform)
        nix_candidates = _check_nix_locations()
        candidates.extend(nix_candidates)

    except Exception as e:
        notification_manager.warning(f"Error checking package manager locations: {e}")

    return candidates


def _check_homebrew_locations() -> list[Path]:
    """Check Homebrew installation locations."""
    candidates: list[Path] = []

    # Common Homebrew prefixes
    homebrew_prefixes = [
        "/opt/homebrew",  # Apple Silicon Macs
        "/usr/local",  # Intel Macs
    ]

    for prefix in homebrew_prefixes:
        brew_path = Path(prefix) / "bin" / "tamarin-prover"
        if brew_path.exists():
            candidates.append(brew_path)

    return candidates


def _check_haskell_locations() -> list[Path]:
    """Check Haskell Stack and Cabal installation locations."""
    candidates: list[Path] = []

    # Stack local bin
    stack_local = Path.home() / ".local" / "bin" / "tamarin-prover"
    if stack_local.exists():
        candidates.append(stack_local)

    # Cabal bin
    cabal_bin = Path.home() / ".cabal" / "bin" / "tamarin-prover"
    if cabal_bin.exists():
        candidates.append(cabal_bin)

    return candidates


def _check_nix_locations() -> list[Path]:
    """Check Nix package manager locations."""
    candidates: list[Path] = []

    try:
        # Check if nix-env is available
        result = subprocess.run(
            ["which", "nix-env"], capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0:
            # Check Nix profile
            nix_profile = Path.home() / ".nix-profile" / "bin" / "tamarin-prover"
            if nix_profile.exists():
                candidates.append(nix_profile)

    except Exception as e:
        notification_manager.warning(f"Error checking Nix locations: {e}")

    return candidates
