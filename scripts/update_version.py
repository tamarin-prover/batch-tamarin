import re
from pathlib import Path
from typing import Any, Dict, List

import toml


def update_version() -> None:
    # Read pyproject.toml
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "r") as f:
        data: Dict[str, Any] = toml.load(f)  # type: ignore

    # Extract metadata
    version: str = data["project"]["version"]  # type: ignore
    authors: List[Dict[str, str]] = data["project"]["authors"]  # type: ignore

    # Format authors string
    authors_str: str = ", ".join([f"{a['name']} <{a['email']}>" for a in authors])  # type: ignore

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
    with open(readme_path, "r") as f:
        readme_content = f.read()

    # Regex to match the release badge and update the version (robust to color and whitespace)
    badge_pattern = r"(!\[Release\]\(https://img\.shields\.io/badge/release-)([^-]+)(-[a-zA-Z0-9]+?\))"

    def badge_repl(match: re.Match[str]) -> str:
        return f"{match.group(1)}{version}{match.group(3)}"

    new_readme_content = re.sub(badge_pattern, badge_repl, readme_content, count=1)

    with open(readme_path, "w") as f:
        f.write(new_readme_content)


if __name__ == "__main__":
    update_version()
