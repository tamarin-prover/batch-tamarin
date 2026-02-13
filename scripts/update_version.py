import re
from pathlib import Path
from typing import Any

try:
    import tomllib  # type: ignore[import]
except ImportError:
    import toml as tomllib  # type: ignore[import]


def update_version() -> None:
    # Read pyproject.toml
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data: dict[str, Any] = tomllib.load(f)

    # Extract metadata
    version: str = data["project"]["version"]
    authors: list[dict[str, str]] = data["project"]["authors"]

    # Format authors string
    authors_str: str = ", ".join([f"{a['name']} <{a['email']}>" for a in authors])

    # Update __init__.py
    init_path = Path(__file__).parent.parent / "src" / "batch_tamarin" / "__init__.py"
    content: str = f'''"""Tamarin Python Wrapper - Run Tamarin Prover models with JSON recipes."""

__version__ = "{version}"
__author__ = "{authors_str}"

from .main import app

__all__ = ["app"]
'''
    with open(init_path, "w") as f:
        f.write(content)

    # Update README.md badge version
    # README.md is in the project root, not in scripts/
    readme_path = Path(__file__).parent.parent / "README.md"
    with open(readme_path) as f:
        readme_content = f.read()

    # Regex to match the release badge and update the version (robust to color and whitespace)
    badge_pattern = r"(!\[Release\]\(https://img\.shields\.io/badge/release-)([^-]+)(-[a-zA-Z0-9]+?\))"

    def badge_repl(match: re.Match[str]) -> str:
        return f"{match.group(1)}{version}{match.group(3)}"

    new_readme_content = re.sub(badge_pattern, badge_repl, readme_content, count=1)

    with open(readme_path, "w") as f:
        f.write(new_readme_content)

    # Update nix dockerfiles
    nix_dockerfiles_dir = (
        Path(__file__).parent.parent
        / "examples"
        / "__dockerfiles__"
        / "with-batch-tamarin"
    )
    for nix_file in nix_dockerfiles_dir.glob("*.nix"):
        with open(nix_file) as f:
            nix_content = f.read()

        # Update the batch-tamarin version in the nix file
        version_pattern = r'(batch-tamarin = python\.pkgs\.buildPythonPackage rec \{\s*pname = "batch-tamarin";\s*version = ")[^"]+(";)'
        new_nix_content = re.sub(version_pattern, rf"\g<1>{version}\g<2>", nix_content)

        # Also update description line (e.g., "Tamarin Prover X.Y.Z and batch-tamarin 1.1.0")
        desc_pattern = (
            r'(description = "Tamarin Prover [\d.]+ and batch-tamarin )[^"]+(";)'
        )
        new_nix_content = re.sub(desc_pattern, rf"\g<1>{version}\g<2>", new_nix_content)

        with open(nix_file, "w") as f:
            f.write(new_nix_content)


if __name__ == "__main__":
    update_version()
