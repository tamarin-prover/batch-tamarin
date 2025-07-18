"""
DOT file utilities for converting DOT files to SVG format.

This module provides utilities for validating and converting DOT files
to SVG format for inclusion in reports.
"""

import subprocess
from pathlib import Path
from typing import Any, Optional

from ..utils.notifications import notification_manager

# Try to import graphviz for fallback DOT rendering
try:
    import graphviz

    HAS_GRAPHVIZ = True
except ImportError:
    graphviz = None
    HAS_GRAPHVIZ = False


def is_dot_file_empty(dot_file: Path) -> bool:
    """
    Check if a DOT file is empty or contains only whitespace/comments.

    Args:
        dot_file: Path to the DOT file

    Returns:
        True if the file is empty or contains no meaningful content
    """
    if not dot_file.exists():
        return True

    try:
        content = dot_file.read_text(encoding="utf-8").strip()

        # Check if file is empty
        if not content:
            return True

        # Check if file contains only comments and whitespace
        lines = content.split("\n")
        meaningful_lines: list[str] = []

        for line in lines:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith("//") and not line.startswith("#"):
                meaningful_lines.append(line)

        # If we only have basic DOT structure without nodes/edges, consider it empty
        if len(meaningful_lines) <= 2:  # Just 'digraph {' and '}'
            return True

        return False

    except Exception as e:
        notification_manager.warning(f"Error reading DOT file {dot_file}: {e}")
        return True


def convert_dot_to_svg(
    dot_file: Path, output_svg: Optional[Path] = None
) -> Optional[Path]:
    """
    Convert a DOT file to SVG format using Graphviz.

    Args:
        dot_file: Path to the input DOT file
        output_svg: Path for the output SVG file (optional, defaults to same name with .svg extension)

    Returns:
        Path to the generated SVG file, or None if conversion failed
    """
    if not dot_file.exists():
        notification_manager.warning(f"DOT file does not exist: {dot_file}")
        return None

    if is_dot_file_empty(dot_file):
        notification_manager.debug(
            f"DOT file is empty, skipping conversion: {dot_file}"
        )
        return None

    if output_svg is None:
        output_svg = dot_file.with_suffix(".svg")

    try:
        # First try using dot command directly
        result = subprocess.run(
            ["dot", "-Tsvg", str(dot_file), "-o", str(output_svg)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            notification_manager.debug(
                f"Successfully converted {dot_file} to {output_svg}"
            )
            return output_svg
        else:
            notification_manager.debug(
                f"Direct dot command failed: {result.stderr.strip()}"
            )
            # Fall back to Python graphviz package
            return _convert_with_graphviz_package(dot_file, output_svg)

    except subprocess.TimeoutExpired:
        notification_manager.warning(f"Timeout converting DOT file: {dot_file}")
        return _convert_with_graphviz_package(dot_file, output_svg)
    except FileNotFoundError:
        notification_manager.debug(
            "Graphviz 'dot' command not found. Trying Python graphviz package..."
        )
        return _convert_with_graphviz_package(dot_file, output_svg)
    except Exception as e:
        notification_manager.debug(f"Error with dot command: {e}")
        return _convert_with_graphviz_package(dot_file, output_svg)


def _convert_with_graphviz_package(dot_file: Path, output_svg: Path) -> Optional[Path]:
    """
    Convert DOT file to SVG using Python graphviz package as fallback.

    Args:
        dot_file: Path to the input DOT file
        output_svg: Path for the output SVG file

    Returns:
        Path to the generated SVG file, or None if conversion failed
    """
    if not HAS_GRAPHVIZ:
        notification_manager.warning(
            "Neither 'dot' command nor Python 'graphviz' package available. "
            "Please install Graphviz to enable DOT to SVG conversion."
        )
        return None

    try:
        # Read DOT file content
        dot_content = dot_file.read_text(encoding="utf-8")

        # Create graphviz object from DOT content
        if graphviz is None:
            return None
        src: Any = graphviz.Source(dot_content)

        # Render to SVG
        svg_content: Any = src.pipe(format="svg", encoding="utf-8")
        if not isinstance(svg_content, str):
            svg_content = str(svg_content)

        # Write SVG content to file
        output_svg.write_text(svg_content, encoding="utf-8")

        notification_manager.debug(
            f"Successfully converted {dot_file} to {output_svg} using graphviz package"
        )
        return output_svg

    except Exception as e:
        notification_manager.warning(
            f"Failed to convert DOT to SVG using graphviz package: {e}"
        )
        return None


def get_svg_content(svg_file: Path) -> Optional[str]:
    """
    Read SVG content from file, removing XML declaration for embedding.

    Args:
        svg_file: Path to the SVG file

    Returns:
        SVG content as string, or None if file cannot be read
    """
    if not svg_file.exists():
        return None

    try:
        content = svg_file.read_text(encoding="utf-8")

        # Remove XML declaration and DOCTYPE for embedding
        lines = content.split("\n")
        filtered_lines: list[str] = []

        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith("<?xml") or line_stripped.startswith(
                "<!DOCTYPE"
            ):
                continue
            filtered_lines.append(line)

        return "\n".join(filtered_lines)

    except Exception as e:
        notification_manager.warning(f"Error reading SVG file {svg_file}: {e}")
        return None


def process_dot_file(dot_file: Path) -> Optional[str]:
    """
    Process a DOT file: validate, convert to SVG, and return SVG content.

    Args:
        dot_file: Path to the DOT file

    Returns:
        SVG content as string, or None if processing failed
    """
    if is_dot_file_empty(dot_file):
        return None

    svg_file = convert_dot_to_svg(dot_file)
    if svg_file is None:
        return None

    return get_svg_content(svg_file)
