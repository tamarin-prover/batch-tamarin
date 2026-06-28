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

    # Update __init__.py
    init_path = Path(__file__).parent.parent / "src" / "batch_tamarin" / "__init__.py"

    # Preserve __author__ and __contributors__ from existing __init__.py if present.
    # NOTE: __author__ may intentionally contain Rich console markup (e.g.
    # [dim green]...[/dim green]) so that --version output is styled when printed
    # with rprint().  Manual edits to add markup are expected and preserved.
    authors_str: str = ", ".join([f"{a['name']} <{a['email']}>" for a in authors])
    contributors_line = ""
    if init_path.exists():
        existing_content = init_path.read_text()

        author_match = re.search(
            r'^__author__\s*=\s*".*?"\s*$',
            existing_content,
            re.MULTILINE | re.DOTALL,
        )
        if author_match:
            # Keep the existing author line (may contain Rich markup)
            authors_str = author_match.group(0).split("=", 1)[1].strip().strip('"')

        contributors_match = re.search(
            r"^__contributors__\s*=\s*\[.*?\]$",
            existing_content,
            re.MULTILINE | re.DOTALL,
        )
        if contributors_match:
            contributors_line = "\n" + contributors_match.group(0).rstrip()

    content: str = f'''"""Tamarin Python Wrapper - Run Tamarin Prover models with JSON recipes."""

__version__ = "{version}"
__author__ = "{authors_str}"{contributors_line}

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

        # Check current version in this nix file before deciding whether to invalidate hash
        current_nix_version_match = re.search(
            r'batch-tamarin = python\.pkgs\.buildPythonPackage rec \{\s*pname = "batch-tamarin";\s*version = "([^"]+)"',
            nix_content,
        )
        version_changed = (
            current_nix_version_match is not None
            and current_nix_version_match.group(1) != version
        )

        # Update the batch-tamarin version in the nix file
        version_pattern = r'(batch-tamarin = python\.pkgs\.buildPythonPackage rec \{\s*pname = "batch-tamarin";\s*version = ")[^"]+(";)'
        new_nix_content = re.sub(version_pattern, rf"\g<1>{version}\g<2>", nix_content)

        # Also update description line (e.g. "Tamarin Prover X.Y.Z and batch-tamarin 1.1.0")
        desc_pattern = (
            r'(description = "Tamarin Prover [\d.]+ and batch-tamarin )[^"]+(";)'
        )
        new_nix_content = re.sub(desc_pattern, rf"\g<1>{version}\g<2>", new_nix_content)

        # Invalidate the sha256 hash when version changes so Nix will report the correct one
        if version_changed:
            # Replace sha256-... with a zeroed-out valid base64 SRI hash.
            # Nix will fail and print the expected hash, which the maintainer can copy.
            # Only invalidate the hash inside the batch-tamarin block (not other
            # packages such as py-tree-sitter-spthy that also use rev + hash).
            new_nix_content = re.sub(
                r'(repo = "batch-tamarin";\s*rev = "v\$\{version\}";\s*hash = ")sha256-[^"]+(")',
                r"\1sha256-0000000000000000000000000000000000000000000=\2",
                new_nix_content,
            )

        with open(nix_file, "w") as f:
            f.write(new_nix_content)


if __name__ == "__main__":
    update_version()
