"""Tree-sitter grammar builder for Tamarin spthy with modern tree-sitter support."""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from tree_sitter import Language


class TamarinGrammarBuilder:
    """Handles building and loading the Tamarin spthy grammar."""

    def __init__(self) -> None:
        # Locate grammar directory - assume package installation
        try:
            import tamarin_wrapper

            package_path = Path(tamarin_wrapper.__file__).parent.parent
            self.grammar_dir = package_path / "vendor" / "tree-sitter-spthy"
        except (ImportError, AttributeError):
            # Fallback for development
            self.grammar_dir = Path("vendor/tree-sitter-spthy")

        # Use user cache directory for compiled libraries
        cache_dir = Path(tempfile.gettempdir()) / "tamarin_wrapper_cache"
        self.build_dir = cache_dir / "parsers" / "build"
        self.so_file = self.build_dir / "tamarin-spthy.so"

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        self.build_dir.mkdir(parents=True, exist_ok=True)

    def _has_required_files(self) -> bool:
        """Check if all required files are present."""
        required_files = [
            self.grammar_dir / "grammar.js",
            self.grammar_dir / "src" / "parser.c",
        ]
        return all(f.exists() for f in required_files)

    def _compile_grammar(self) -> bool:
        """Compile the grammar using system compiler."""
        if not self._has_required_files():
            print("Error: Required grammar files not found")
            print("Expected files:")
            print(f"  - {self.grammar_dir / 'grammar.js'}")
            print(f"  - {self.grammar_dir / 'src' / 'parser.c'}")
            return False

        print("Compiling Tamarin spthy grammar...")

        # Paths to source files
        parser_c = self.grammar_dir / "src" / "parser.c"
        scanner_c = self.grammar_dir / "src" / "scanner.c"

        # Compilation command
        cmd = ["gcc", "-shared", "-fPIC", "-O2", str(parser_c)]

        # Add scanner if it exists
        if scanner_c.exists():
            cmd.append(str(scanner_c))

        # Output file
        cmd.extend(["-o", str(self.so_file)])

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"✓ Grammar compiled successfully: {self.so_file}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error compiling grammar: {e}")
            print(f"Command: {' '.join(cmd)}")
            if e.stdout:
                print(f"stdout: {e.stdout}")
            if e.stderr:
                print(f"stderr: {e.stderr}")
            return False
        except FileNotFoundError:
            print("Error: gcc not found. Please ensure a C compiler is installed.")
            return False

    def build_grammar(self) -> bool:
        """Build the Tamarin spthy tree-sitter grammar."""
        if not self.grammar_dir.exists():
            print(
                "Error: Tamarin tree-sitter grammar not found in vendor/tree-sitter-spthy"
            )
            print(
                "Note: The vendor directory needs to be populated with the Tamarin grammar."
            )
            print("This requires a git subtree setup by the project maintainer.")
            print(
                "For now, the output processor will work without tree-sitter parsing."
            )
            return False

        self._ensure_directories()

        # If the .so file already exists and is newer than source files, skip compilation
        if self.so_file.exists():
            parser_c = self.grammar_dir / "src" / "parser.c"
            if parser_c.exists():
                so_mtime = self.so_file.stat().st_mtime
                parser_mtime = parser_c.stat().st_mtime
                if so_mtime > parser_mtime:
                    print(f"✓ Grammar already compiled: {self.so_file}")
                    return True

        return self._compile_grammar()

    def load_language(self) -> Optional[Language]:
        """Load the compiled language."""
        if not self.so_file.exists():
            if not self.build_grammar():
                return None

        try:
            # Modern tree-sitter approach - load from compiled shared library
            return Language(str(self.so_file))
        except Exception as e:
            print(f"Error loading grammar: {e}")
            return None

    def verify_setup(self) -> bool:
        """Verify that the tree-sitter setup works."""
        language = self.load_language()
        if language is None:
            print("Grammar verification failed.")
            return False

        print("✓ Tree-sitter setup working")
        return True


def get_language() -> Optional[Language]:
    """Get the Tamarin language for use in parsers.

    This function automatically handles grammar compilation if needed.
    """
    builder = TamarinGrammarBuilder()
    return builder.load_language()


def build_tamarin_grammar() -> None:
    """Build the Tamarin spthy tree-sitter grammar."""
    builder = TamarinGrammarBuilder()

    if builder.build_grammar():
        print("✓ Grammar built successfully")
    else:
        print("Note: Tree-sitter parsing will be disabled.")
        print("The output processor will work with regex-based parsing only.")


def verify_setup() -> bool:
    """Verify that the tree-sitter setup works."""
    builder = TamarinGrammarBuilder()

    if builder.verify_setup():
        return True
    else:
        print("✗ Setup verification failed")
        print("This is expected if the Tamarin grammar hasn't been set up yet.")
        print("The output processor will work without tree-sitter parsing.")
        return False
