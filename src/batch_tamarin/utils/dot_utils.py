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
    import graphviz  # type: ignore

    HAS_GRAPHVIZ = True
except ImportError:
    graphviz = None
    HAS_GRAPHVIZ = False  # type: ignore


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


def convert_dot_to_format(
    dot_file: Path, output_format: str, output_file: Optional[Path] = None
) -> Optional[Path]:
    """
    Convert a DOT file to specified format using Graphviz.

    Args:
        dot_file: Path to the input DOT file
        output_format: Target format (svg, pdf, png, etc.)
        output_file: Path for the output file (optional, defaults to same name with new extension)

    Returns:
        Path to the generated file, or None if conversion failed
    """
    if not dot_file.exists():
        notification_manager.warning(f"DOT file does not exist: {dot_file}")
        return None

    if is_dot_file_empty(dot_file):
        notification_manager.debug(
            f"DOT file is empty, skipping conversion: {dot_file}"
        )
        return None

    if output_file is None:
        output_file = dot_file.with_suffix(f".{output_format}")

    try:
        # Build command with quality options for PNG
        cmd = ["dot", f"-T{output_format}"]

        # Add high-quality options for PNG
        if output_format.lower() == "png":
            cmd.extend(["-Gdpi=300", "-Gsize=12,8!", "-Gratio=fill"])

        cmd.extend([str(dot_file), "-o", str(output_file)])

        # First try using dot command directly
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            notification_manager.debug(
                f"Successfully converted {dot_file} to {output_file}"
            )
            return output_file
        else:
            notification_manager.debug(
                f"Direct dot command failed: {result.stderr.strip()}"
            )
            # Fall back to Python graphviz package
            return _convert_with_graphviz_package(dot_file, output_file, output_format)

    except subprocess.TimeoutExpired:
        notification_manager.warning(f"Timeout converting DOT file: {dot_file}")
        return _convert_with_graphviz_package(dot_file, output_file, output_format)
    except FileNotFoundError:
        notification_manager.debug(
            "Graphviz 'dot' command not found. Trying Python graphviz package..."
        )
        return _convert_with_graphviz_package(dot_file, output_file, output_format)
    except Exception as e:
        notification_manager.debug(f"Error with dot command: {e}")
        return _convert_with_graphviz_package(dot_file, output_file, output_format)


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
    return convert_dot_to_format(dot_file, "svg", output_svg)


def convert_dot_to_png(
    dot_file: Path, output_png: Optional[Path] = None
) -> Optional[Path]:
    """
    Convert a DOT file to PNG format using Graphviz.

    Args:
        dot_file: Path to the input DOT file
        output_png: Path for the output PNG file (optional, defaults to same name with .png extension)

    Returns:
        Path to the generated PNG file, or None if conversion failed
    """
    return convert_dot_to_format(dot_file, "png", output_png)


def _convert_with_graphviz_package(
    dot_file: Path, output_file: Path, output_format: str = "svg"
) -> Optional[Path]:
    """
    Convert DOT file to specified format using Python graphviz package as fallback.

    Args:
        dot_file: Path to the input DOT file
        output_file: Path for the output file
        output_format: Target format (svg, pdf, png, etc.)

    Returns:
        Path to the generated file, or None if conversion failed
    """
    if not HAS_GRAPHVIZ:
        notification_manager.warning(
            "Neither 'dot' command nor Python 'graphviz' package available. "
            f"Please install Graphviz to enable DOT to {output_format.upper()} conversion."
        )
        return None

    try:
        # Read DOT file content
        dot_content = dot_file.read_text(encoding="utf-8")

        # Create graphviz object from DOT content
        if graphviz is None:
            return None
        src: Any = graphviz.Source(dot_content)

        # Render to specified format with quality options
        renderer_kwargs = {}
        if output_format.lower() == "png":
            # High quality PNG settings
            renderer_kwargs = {
                "renderer": "dot",
                "formatter": output_format,
                "engine": "dot",
            }

        if output_format.lower() in ["svg"]:
            # For SVG, we get text content
            file_content: Any = src.pipe(
                format=output_format, encoding="utf-8", **renderer_kwargs
            )
            if not isinstance(file_content, str):
                file_content = str(file_content)
            output_file.write_text(file_content, encoding="utf-8")
        else:
            # For binary formats (PDF, PNG), we get bytes
            file_content = src.pipe(format=output_format, **renderer_kwargs)
            if isinstance(file_content, str):
                file_content = file_content.encode("utf-8")
            output_file.write_bytes(file_content)

        notification_manager.debug(
            f"Successfully converted {dot_file} to {output_file} using graphviz package"
        )
        return output_file

    except Exception as e:
        notification_manager.warning(
            f"Failed to convert DOT to {output_format.upper()} using graphviz package: {e}"
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


def is_json_trace_empty(json_file: Path) -> bool:
    """
    Check if a JSON trace file is empty or contains no meaningful trace data.

    Args:
        json_file: Path to the JSON trace file

    Returns:
        True if the file is empty or contains no trace graphs
    """
    if not json_file.exists():
        return True

    try:
        import json

        content = json_file.read_text(encoding="utf-8").strip()
        if not content:
            return True

        data = json.loads(content)

        # Check if it's the empty trace structure
        if isinstance(data, dict) and "graphs" in data:
            graphs = data.get("graphs", [])  # type: ignore
            return len(graphs) == 0  # type: ignore

        return False

    except Exception as e:
        notification_manager.warning(f"Error reading JSON trace file {json_file}: {e}")
        return True


def cleanup_empty_trace_files(trace_dir: Path) -> None:
    """
    Remove empty DOT and JSON trace files from a directory.

    Args:
        trace_dir: Directory containing trace files to clean up
    """
    if not trace_dir.exists() or not trace_dir.is_dir():
        return

    try:
        # Clean up empty DOT files
        for dot_file in trace_dir.glob("*.dot"):
            if is_dot_file_empty(dot_file):
                notification_manager.debug(f"Removing empty DOT file: {dot_file}")
                dot_file.unlink()

        # Clean up empty JSON trace files
        for json_file in trace_dir.glob("*.json"):
            if is_json_trace_empty(json_file):
                notification_manager.debug(
                    f"Removing empty JSON trace file: {json_file}"
                )
                json_file.unlink()

    except Exception as e:
        notification_manager.warning(f"Error during trace file cleanup: {e}")


def process_dot_file(dot_file: Path, format_type: str) -> Optional[str]:
    """
    Process a DOT file: validate, convert to SVG, and return SVG content.

    Args:
        dot_file: Path to the DOT file

    Returns:
        SVG content as string, or None if processing failed
    """
    if is_dot_file_empty(dot_file):
        return None

    if format_type.lower() != "tex":
        svg_file = convert_dot_to_svg(dot_file)
        if svg_file is None:
            return None
        return get_svg_content(svg_file)
    else:
        try:
            png_result = convert_dot_to_png(dot_file)
            if png_result:
                notification_manager.debug(f"Converted {dot_file.name} to PNG")
        except Exception as e:
            notification_manager.debug(f"Failed to convert {dot_file.name} to PNG: {e}")
        finally:
            # Return None for LaTeX format as we don't use SVG
            return None
