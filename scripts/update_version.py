from pathlib import Path
from typing import List, TypedDict

import toml


class Author(TypedDict):
    name: str
    email: str


class Project(TypedDict):
    version: str
    authors: List[Author]
    description: str


class Pyproject(TypedDict):
    project: Project


def update_version():
    # Read pyproject.toml
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "r") as f:
        data: Pyproject = toml.load(f)

    # Extract metadata
    version = data["project"]["version"]
    authors = data["project"]["authors"]

    # Format authors string
    authors_str = ", ".join([f"{a['name']} <{a['email']}>" for a in authors])

    # Update __init__.py
    init_path = Path(__file__).parent.parent / "src" / "tamarin_wrapper" / "__init__.py"
    content = f'''"""Tamarin Python Wrapper - Run Tamarin Prover models with JSON recipes."""

__version__ = "{version}"
__author__ = "{authors_str}"

from .main import app

__all__ = ["app"]
'''
    with open(init_path, "w") as f:
        f.write(content)


if __name__ == "__main__":
    update_version()
