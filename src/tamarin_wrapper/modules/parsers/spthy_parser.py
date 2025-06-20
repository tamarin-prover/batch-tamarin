"""
Tree-sitter based parser for .spthy files using official Tamarin grammar.

This module implements parsing of Tamarin theory files using the official
tree-sitter grammar to extract lemmas, proofs, and other structural information.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ...model.output_models import (
    FunctionDeclaration,
    RestrictionDeclaration,
    RuleDeclaration,
    SpthyAnalysis,
    SpthyLemmaInfo,
)
from ...setup.tree_sitter import get_language

try:
    from tree_sitter import Node, Parser

    tree_sitter_available = True
except ImportError:
    tree_sitter_available = False
    if TYPE_CHECKING:
        from tree_sitter import Node, Parser
    else:
        Node = Any
        Parser = Any


class SpthyFileParser:
    """
    Tree-sitter based parser using official Tamarin spthy grammar.
    Focuses on lemma and proof extraction for output processing.
    """

    def __init__(self):
        """Initialize the parser with the compiled Tamarin grammar."""
        if not tree_sitter_available:
            raise ImportError("tree-sitter not available. Run: pip install tree-sitter")

        try:
            # Use the proper tree-sitter setup from our setup module
            self.language = get_language()
            if self.language is None:
                raise RuntimeError("Failed to load Tamarin grammar")

            self.parser = Parser()
            self.parser.set_language(self.language)  # type: ignore
        except Exception as e:
            raise RuntimeError(f"Failed to load Tamarin grammar: {e}")

    def parse_file(self, file_path: Path) -> SpthyAnalysis:
        """
        Parse spthy file using tree-sitter and extract structured information.

        Args:
            file_path: Path to the .spthy file to parse

        Returns:
            SpthyAnalysis containing extracted information

        Raises:
            FileNotFoundError: If the file doesn't exist
            UnicodeDecodeError: If the file cannot be decoded
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Spthy file not found: {file_path}")

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            raise UnicodeDecodeError(
                e.encoding,
                e.object,
                e.start,
                e.end,
                f"Cannot decode file {file_path}: {e.reason}",
            ) from e

        tree = self.parser.parse(content.encode("utf8"))

        return self._extract_analysis(tree.root_node, content)

    def _extract_analysis(self, root: Node, content: str) -> SpthyAnalysis:
        """
        Extract structured information from parse tree.

        Args:
            root: Root node of the parse tree
            content: Original file content

        Returns:
            SpthyAnalysis with extracted information
        """
        theory_name = self._extract_theory_name(root, content)
        lemmas = self._extract_lemmas(root, content)

        # These can be extended later for more complete analysis
        functions: List[FunctionDeclaration] = []
        rules: List[RuleDeclaration] = []
        restrictions: List[RestrictionDeclaration] = []

        # Tree-sitter provides good error recovery, so parsing errors are rare
        parsing_errors: List[str] = []

        return SpthyAnalysis(
            theory_name=theory_name,
            lemmas=lemmas,
            functions=functions,
            rules=rules,
            restrictions=restrictions,
            parsing_errors=parsing_errors,
        )

    def _extract_lemmas(self, root: Node, content: str) -> Dict[str, SpthyLemmaInfo]:
        """
        Extract all lemmas from parse tree.

        Args:
            root: Root node of the parse tree
            content: Original file content

        Returns:
            Dictionary mapping lemma names to SpthyLemmaInfo
        """
        lemmas: Dict[str, SpthyLemmaInfo] = {}
        lemma_nodes = self._find_nodes_by_type(root, "lemma")

        for lemma_node in lemma_nodes:
            lemma_info = self._parse_lemma_node(lemma_node, content)
            if lemma_info:
                lemmas[lemma_info.name] = lemma_info

        return lemmas

    def _parse_lemma_node(
        self, lemma_node: Node, content: str
    ) -> Optional[SpthyLemmaInfo]:
        """
        Parse individual lemma node and extract proof information.

        Args:
            lemma_node: Tree-sitter node representing a lemma
            content: Original file content

        Returns:
            SpthyLemmaInfo if successfully parsed, None otherwise
        """
        # Extract lemma name
        name_node = lemma_node.child_by_field_name("lemma_identifier")
        if not name_node:
            # Try alternative field names or fallback methods
            name_node = self._find_child_by_type(lemma_node, "identifier")

        if not name_node:
            return None

        name = self._get_node_text(name_node, content).strip()

        # Extract attributes [sources], [reuse], etc.
        attributes = self._extract_lemma_attributes(lemma_node, content)

        # Extract trace quantifier (all-traces, exists-trace)
        trace_quantifier = self._extract_trace_quantifier(lemma_node, content)

        # Extract formula
        formula_node = lemma_node.child_by_field_name("formula")
        if not formula_node:
            formula_node = self._find_child_by_type(lemma_node, "formula")

        formula = (
            self._get_node_text(formula_node, content).strip() if formula_node else ""
        )

        # Extract proof information
        proof_status, proof_method = self._extract_proof_info(lemma_node, content)

        return SpthyLemmaInfo(
            name=name,
            attributes=attributes,
            analysis_type=trace_quantifier or "all-traces",
            formula=formula,
            proof_status=proof_status,
            proof_method=proof_method,
            proof_steps=[],  # Can be enhanced later with detailed step extraction
            line_number=lemma_node.start_point[0] + 1,
            end_line=lemma_node.end_point[0] + 1,
        )

    def _extract_proof_info(
        self, lemma_node: Node, content: str
    ) -> tuple[str, Optional[str]]:
        """
        Extract proof status and method from lemma.

        Args:
            lemma_node: Tree-sitter node representing a lemma
            content: Original file content

        Returns:
            Tuple of (proof_status, proof_method)
        """
        proof_skeleton_node = lemma_node.child_by_field_name("proof_skeleton")
        if not proof_skeleton_node:
            proof_skeleton_node = self._find_child_by_type(lemma_node, "proof")

        if not proof_skeleton_node:
            return "unproven", None

        # Check for different proof types
        if self._find_nodes_by_type(proof_skeleton_node, "solved"):
            return "proven", "automatic"
        elif self._find_nodes_by_type(proof_skeleton_node, "by_method"):
            method_nodes = self._find_nodes_by_type(proof_skeleton_node, "proof_method")
            if method_nodes:
                method = self._get_node_text(method_nodes[0], content)
                if "sorry" in method.lower():
                    return "unproven", "sorry"
                else:
                    return "proven", method.strip()
        elif self._find_nodes_by_type(proof_skeleton_node, "cases"):
            return "proven", "cases"

        # Check if proof contains "sorry" (unfinished proof)
        proof_text = self._get_node_text(proof_skeleton_node, content).lower()
        if "sorry" in proof_text:
            return "unproven", "sorry"

        return "unproven", None

    def _extract_lemma_attributes(self, lemma_node: Node, content: str) -> List[str]:
        """
        Extract lemma attributes like [sources], [reuse], etc.

        Args:
            lemma_node: Tree-sitter node representing a lemma
            content: Original file content

        Returns:
            List of attribute strings
        """
        attrs: List[str] = []

        # Look for attribute nodes - this depends on the specific grammar structure
        attr_nodes = self._find_nodes_by_type(lemma_node, "attribute")
        for attr_node in attr_nodes:
            attr_text = self._get_node_text(attr_node, content).strip()
            if attr_text:
                attrs.append(attr_text)

        return attrs

    def _extract_trace_quantifier(
        self, lemma_node: Node, content: str
    ) -> Optional[str]:
        """
        Extract trace quantifier (all-traces, exists-trace).

        Args:
            lemma_node: Tree-sitter node representing a lemma
            content: Original file content

        Returns:
            Trace quantifier string or None
        """
        quantifier_node = lemma_node.child_by_field_name("trace_quantifier")
        if not quantifier_node:
            # Look for quantifier patterns in the lemma text
            lemma_text = self._get_node_text(lemma_node, content)
            if "exists-trace" in lemma_text.lower():
                return "exists-trace"
            elif "all-traces" in lemma_text.lower():
                return "all-traces"
        else:
            return self._get_node_text(quantifier_node, content).strip()

        return None

    def _extract_theory_name(self, root: Node, content: str) -> str:
        """
        Extract theory name from parse tree.

        Args:
            root: Root node of the parse tree
            content: Original file content

        Returns:
            Theory name or "Unknown" if not found
        """
        theory_nodes = self._find_nodes_by_type(root, "theory")
        if theory_nodes:
            theory_node = theory_nodes[0]
            name_node = theory_node.child_by_field_name("theory_name")
            if not name_node:
                # Try to find identifier child
                name_node = self._find_child_by_type(theory_node, "identifier")

            if name_node:
                return self._get_node_text(name_node, content).strip()

        return "Unknown"

    def _find_nodes_by_type(self, root: Node, node_type: str) -> List[Node]:
        """
        Find all nodes of specific type in tree.

        Args:
            root: Root node to search from
            node_type: Type of nodes to find

        Returns:
            List of matching nodes
        """
        nodes: List[Node] = []

        def traverse(node: Node) -> None:
            if node.type == node_type:
                nodes.append(node)
            for child in node.children:
                traverse(child)

        traverse(root)
        return nodes

    def _find_child_by_type(self, node: Node, child_type: str) -> Optional[Node]:
        """
        Find first direct child of specific type.

        Args:
            node: Parent node
            child_type: Type of child to find

        Returns:
            First matching child node or None
        """
        for child in node.children:
            if child.type == child_type:
                return child
        return None

    def _get_node_text(self, node: Node, content: str) -> str:
        """
        Extract text content from node.

        Args:
            node: Tree-sitter node
            content: Original file content

        Returns:
            Text content of the node
        """
        return content[node.start_byte : node.end_byte]
