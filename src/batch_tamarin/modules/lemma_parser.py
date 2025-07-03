"""
Lemma parser module for extracting lemma names from Tamarin theory files.

This module uses tree-sitter-spthy to parse Tamarin Security Protocol Theory (.spthy) files
and extract all lemma declarations to enable fine-grained task creation.
"""

from pathlib import Path
from types import FunctionType
from typing import List, Optional, Set

try:
    import tree_sitter_spthy as ts_spthy
    from tree_sitter import Node, Parser
except ImportError as e:
    raise ImportError(
        "tree-sitter is required for lemma discovery."
        "tree-sitter-spthy is required for lemma parsing. "
        "Please ensure it's installed via pip: [bold]pip install tree-sitter>=0.21.0 py-tree-sitter-spthy>=1.1.1[/bold]"
        "This might be an architecture incompatibility issue, if pip install fails, you may want to open an issue at https://github.com/lmandrelli/py-tree-sitter-spthy/issues"
    ) from e

from ..utils.notifications import notification_manager


class LemmaParsingError(Exception):
    """Exception raised when lemma parsing fails."""


class LemmaParser:
    """Parser for extracting lemma names from Tamarin theory files."""

    def __init__(self, external_flags: Optional[List[str]] = None) -> None:
        """
        Initialize the parser with the Tamarin grammar.

        Args:
            external_flags: External preprocessor flags (e.g., from CLI -D arguments)
        """
        try:
            self.language = ts_spthy.language()
            self.parser = Parser(self.language)  # type: ignore
            self.external_flags = set(external_flags or [])
        except Exception as e:
            raise LemmaParsingError(f"Failed to initialize Tamarin parser: {e}") from e

    def parse_lemmas_from_file(self, theory_file: Path) -> List[str]:
        """
        Parse all lemma names from a Tamarin theory file.

        Args:
            theory_file: Path to the .spthy theory file

        Returns:
            List of lemma names found in the file

        Raises:
            LemmaParsingError: If parsing fails or file cannot be read
        """
        try:
            # Check if file exists
            if not theory_file.exists():
                raise LemmaParsingError(f"Theory file not found: {theory_file}")

            # Read the file content
            with open(theory_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse the content with tree-sitter
            tree = self.parser.parse(content.encode("utf-8"))

            # Extract lemma names using tree-sitter
            lemma_names = self._extract_lemma_names(tree.root_node, content)

            return lemma_names

        except LemmaParsingError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            raise LemmaParsingError(
                f"Failed to parse lemmas from {theory_file}: {e}"
            ) from e

    def _extract_lemma_names(self, node: Node, content: str) -> List[str]:
        """
        Recursively extract lemma names from the syntax tree.

        Args:
            node: Current tree-sitter node
            content: Original file content for extracting text

        Returns:
            List of unique lemma names
        """
        lemma_names: Set[str] = set()
        defined_symbols: Set[str] = set(
            self.external_flags
        )  # Start with the JSON recipe given flags

        def traverse_node(node: Node, active: bool = True) -> None:
            """
            Recursively traverse the syntax tree to find lemma nodes

            Args:
                node: Current node to traverse
                active: Whether the current block is active (preprocessor directives)
            """
            # Check for all lemma types - only add if in active block
            if active and node.type in [
                "lemma",
                "diff_lemma",
                "accountability_lemma",
                "equiv_lemma",
                "diff_equiv_lemma",
            ]:
                lemma_name = self._extract_lemma_name_from_node(node, content)
                if lemma_name:
                    lemma_names.add(lemma_name)

            # Handle preprocessor directives
            elif node.type == "preprocessor":
                for child in node.children:
                    if child.type == "define":
                        # Extract defined symbol
                        symbol = self._extract_define_symbol(child, content)
                        if symbol:
                            defined_symbols.add(symbol)
                        # Continue with active status unchanged
                        traverse_node(child, active)
                    elif child.type == "ifdef":
                        # Evaluate ifdef condition
                        condition_active = self._evaluate_ifdef_condition(
                            child, content, defined_symbols
                        )
                        # Only process the appropriate branch
                        self._traverse_ifdef_node(
                            child, condition_active and active, traverse_node
                        )
                    else:
                        traverse_node(child, active)

            # For all other nodes, continue normal traversal with current active status
            else:
                for child in node.children:
                    traverse_node(child, active)

        traverse_node(node)  # Start traversal from the root node
        return list(lemma_names)

    def _extract_lemma_name_from_node(
        self, lemma_node: Node, content: str
    ) -> str | None:
        """
        Extract the lemma name from a lemma declaration node.

        Args:
            lemma_node: Tree-sitter node representing a lemma declaration
            content: Original file content

        Returns:
            Lemma name if found, None otherwise
        """
        try:
            lemma_type = lemma_node.type

            # Extract using field names
            if hasattr(lemma_node, "child_by_field_name"):
                lemma_id_node = lemma_node.child_by_field_name("lemma_identifier")
                if lemma_id_node:
                    # Use byte-based slicing to handle UTF-8 encoding correctly
                    raw_text = (
                        content.encode("utf-8")[
                            lemma_id_node.start_byte : lemma_id_node.end_byte
                        ]
                        .decode("utf-8")
                        .strip()
                    )
                    return raw_text

            # Fallback: traverse children to find identifier
            for child in lemma_node.children:
                if child.type == "ident":
                    # Use byte-based slicing to handle UTF-8 encoding correctly
                    raw_text = (
                        content.encode("utf-8")[child.start_byte : child.end_byte]
                        .decode("utf-8")
                        .strip()
                    )
                    return raw_text
                elif child.type == "identifier":
                    # Use byte-based slicing to handle UTF-8 encoding correctly
                    raw_text = (
                        content.encode("utf-8")[child.start_byte : child.end_byte]
                        .decode("utf-8")
                        .strip()
                    )
                    return raw_text

            # Special handling for different lemma types
            if lemma_type in ["equiv_lemma", "diff_equiv_lemma"]:
                # Generate default names for these types if no explicit name found
                return f"{lemma_type}_line_{lemma_node.start_point[0] + 1}"

            notification_manager.error(
                f"[LemmaParser] Could not find identifier in {lemma_type} node at line {lemma_node.start_point[0] + 1}"
            )
            return None

        except Exception as e:
            notification_manager.warning(
                f"[LemmaParser] Error extracting lemma name from node: {e}"
            )
            return None

    def _extract_define_symbol(self, define_node: Node, content: str) -> str | None:
        """
        Extract the symbol name from a #define directive.

        Args:
            define_node: Tree-sitter node representing a #define directive
            content: Original file content

        Returns:
            Symbol name if found, None otherwise
        """
        try:
            for child in define_node.children:
                if child.type == "ident" or child.type == "identifier":
                    # Use byte-based slicing to handle UTF-8 encoding correctly
                    symbol_text = (
                        content.encode("utf-8")[child.start_byte : child.end_byte]
                        .decode("utf-8")
                        .strip()
                    )
                    return symbol_text
            return None
        except Exception:
            return None

    def _evaluate_ifdef_condition(
        self, ifdef_node: Node, content: str, defined_symbols: Set[str]
    ) -> bool:
        """
        Evaluate an #ifdef condition against defined symbols.

        Args:
            ifdef_node: Tree-sitter node representing an #ifdef directive
            content: Original file content
            defined_symbols: Set of currently defined symbols

        Returns:
            True if condition is satisfied, False otherwise
        """
        try:
            # Find the condition node
            for child in ifdef_node.children:
                if (
                    child.type == "condition"
                    or child.type == "ident"
                    or child.type == "identifier"
                ):
                    # Use byte-based slicing to handle UTF-8 encoding correctly
                    condition_text = (
                        content.encode("utf-8")[child.start_byte : child.end_byte]
                        .decode("utf-8")
                        .strip()
                    )
                    return self._evaluate_condition_expression(
                        condition_text, defined_symbols
                    )

            # If no condition found, assume false
            return False
        except Exception:
            # If evaluation fails, assume false to be safe
            return False

    def _evaluate_condition_expression(
        self, condition: str, defined_symbols: Set[str]
    ) -> bool:
        """
        Recursively evaluate a preprocessor condition expression.

        Args:
            condition: Condition string (e.g., "KEYWORD1", "(KEYWORD1 | KEYWORD2) & KEYWORD3")
            defined_symbols: Set of defined symbols

        Returns:
            True if condition is satisfied, False otherwise
        """
        try:
            # Simple implementation - handle basic cases
            condition = condition.strip()

            # Remove parentheses for simplicity
            condition = condition.replace("(", "").replace(")", "")

            # Handle NOT operator
            if condition.startswith("not "):
                inner_condition = condition[4:].strip()
                return not self._evaluate_condition_expression(
                    inner_condition, defined_symbols
                )

            # Handle OR operator
            if "|" in condition:
                parts = [part.strip() for part in condition.split("|")]
                return any(
                    self._evaluate_condition_expression(part, defined_symbols)
                    for part in parts
                )

            # Handle AND operator
            if "&" in condition:
                parts = [part.strip() for part in condition.split("&")]
                return all(
                    self._evaluate_condition_expression(part, defined_symbols)
                    for part in parts
                )

            # Simple symbol check
            return condition in defined_symbols
        except Exception:
            return False

    def _traverse_ifdef_node(
        self, ifdef_node: Node, condition_active: bool, traverse_func: FunctionType
    ) -> None:
        """
        Traverse an #ifdef node, processing only the active branch.

        Args:
            ifdef_node: The #ifdef node
            content: Original file content
            condition_active: Whether the condition is satisfied
            traverse_func: Function to call for traversing child nodes
        """
        try:
            found_else = False

            for child in ifdef_node.children:
                if child.type == "else":
                    found_else = True
                    # Process else branch only if condition is not active
                    if not condition_active:
                        for else_child in child.children:
                            traverse_func(else_child, True)
                elif child.type not in ["condition", "ident", "identifier"]:
                    # This is part of the main ifdef body
                    if condition_active:
                        traverse_func(child, True)

            # If no else branch was found and condition is active, process all non-condition children
            if not found_else and condition_active:
                for child in ifdef_node.children:
                    if child.type not in ["condition", "ident", "identifier"]:
                        traverse_func(child, True)
        except Exception:
            # If traversal fails, skip this ifdef block
            pass
