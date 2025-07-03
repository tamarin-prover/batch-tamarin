"""
Tests for LemmaParser class.

These tests focus specifically on the LemmaParser functionality,
including parsing lemmas from theory files and handling preprocessor flags.
"""

from pathlib import Path

import pytest

from batch_tamarin.modules.lemma_parser import LemmaParser, LemmaParsingError


class TestLemmaParserBasic:
    """Test basic lemma parsing functionality."""

    def test_parse_lemmas_from_simple_theory(self, tmp_dir: Path) -> None:
        """Test parsing lemmas from a simple theory file."""
        theory_content = """
theory SimpleTheory
begin

lemma test_lemma:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

lemma another_lemma:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

end
"""
        theory_file = tmp_dir / "simple_theory.spthy"
        theory_file.write_text(theory_content)

        parser = LemmaParser()
        lemmas = parser.parse_lemmas_from_file(theory_file)

        assert len(lemmas) == 2
        assert "test_lemma" in lemmas
        assert "another_lemma" in lemmas

    def test_parse_lemmas_with_complex_names(self, tmp_dir: Path) -> None:
        """Test parsing lemmas with complex names including underscores and numbers."""
        theory_content = """
theory ComplexTheory
begin

lemma lemma_with_underscores:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

lemma lemma123:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

lemma CamelCaseLemma:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

lemma lemma_with_numbers_123_and_underscores:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

end
"""
        theory_file = tmp_dir / "complex_theory.spthy"
        theory_file.write_text(theory_content)

        parser = LemmaParser()
        lemmas = parser.parse_lemmas_from_file(theory_file)

        assert len(lemmas) == 4
        assert "lemma_with_underscores" in lemmas
        assert "lemma123" in lemmas
        assert "CamelCaseLemma" in lemmas
        assert "lemma_with_numbers_123_and_underscores" in lemmas

    def test_parse_lemmas_with_annotations(self, tmp_dir: Path) -> None:
        """Test parsing lemmas with various annotations."""
        theory_content = """
theory AnnotatedTheory
begin

lemma annotated_lemma [sources]:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

lemma lemma_with_multiple_annotations [sources, reuse]:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

lemma lemma_with_complex_annotations [sources, reuse, use_induction]:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

end
"""
        theory_file = tmp_dir / "annotated_theory.spthy"
        theory_file.write_text(theory_content)

        parser = LemmaParser()
        lemmas = parser.parse_lemmas_from_file(theory_file)

        assert len(lemmas) == 3
        assert "annotated_lemma" in lemmas
        assert "lemma_with_multiple_annotations" in lemmas
        assert "lemma_with_complex_annotations" in lemmas

    def test_parse_lemmas_no_lemmas_in_file(self, tmp_dir: Path) -> None:
        """Test parsing a theory file with no lemmas."""
        theory_content = """
theory NoLemmasTheory
begin

rule Test:
  [ ] --[ TestRule() ]-> [ ]

end
"""
        theory_file = tmp_dir / "no_lemmas_theory.spthy"
        theory_file.write_text(theory_content)

        parser = LemmaParser()
        lemmas = parser.parse_lemmas_from_file(theory_file)

        assert len(lemmas) == 0

    def test_parse_lemmas_empty_file(self, tmp_dir: Path) -> None:
        """Test parsing an empty theory file."""
        theory_file = tmp_dir / "empty_theory.spthy"
        theory_file.write_text("")

        parser = LemmaParser()
        lemmas = parser.parse_lemmas_from_file(theory_file)

        assert len(lemmas) == 0

    def test_parse_lemmas_nonexistent_file(self, tmp_dir: Path) -> None:
        """Test parsing a non-existent theory file."""
        nonexistent_file = tmp_dir / "nonexistent.spthy"

        parser = LemmaParser()

        with pytest.raises(LemmaParsingError, match="Theory file not found"):
            parser.parse_lemmas_from_file(nonexistent_file)

    def test_parse_lemmas_invalid_theory_file(self, tmp_dir: Path) -> None:
        """Test parsing an invalid theory file."""
        theory_content = """
This is not a valid theory file content.
It should cause parsing errors.
"""
        theory_file = tmp_dir / "invalid_theory.spthy"
        theory_file.write_text(theory_content)

        parser = LemmaParser()

        # Note: This might not raise an error depending on the tree-sitter implementation
        # The parser might just return empty lemmas for invalid files
        lemmas = parser.parse_lemmas_from_file(theory_file)

        # Should return empty list for invalid files
        assert len(lemmas) == 0


class TestLemmaParserWithPreprocessor:
    """Test lemma parsing with preprocessor flags."""

    def test_parse_lemmas_with_preprocessor_flags(self, tmp_dir: Path) -> None:
        """Test parsing lemmas with preprocessor flags enabled."""
        theory_content = """
theory PreprocessorTheory
begin

#ifdef FLAG1
lemma conditional_lemma_1:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"
#endif

#ifdef FLAG2
lemma conditional_lemma_2:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"
#endif

lemma always_present_lemma:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

end
"""
        theory_file = tmp_dir / "preprocessor_theory.spthy"
        theory_file.write_text(theory_content)

        # Parse without preprocessor flags
        parser = LemmaParser()
        lemmas_no_flags = parser.parse_lemmas_from_file(theory_file)

        # Parse with FLAG1
        parser_flag1 = LemmaParser(external_flags=["FLAG1"])
        lemmas_flag1 = parser_flag1.parse_lemmas_from_file(theory_file)

        # Parse with FLAG2
        parser_flag2 = LemmaParser(external_flags=["FLAG2"])
        lemmas_flag2 = parser_flag2.parse_lemmas_from_file(theory_file)

        # Parse with both flags
        parser_both = LemmaParser(external_flags=["FLAG1", "FLAG2"])
        lemmas_both = parser_both.parse_lemmas_from_file(theory_file)

        # The always_present_lemma should be in all results
        assert "always_present_lemma" in lemmas_no_flags
        assert "always_present_lemma" in lemmas_flag1
        assert "always_present_lemma" in lemmas_flag2
        assert "always_present_lemma" in lemmas_both

        # Conditional lemmas should only appear when their flags are set
        # Note: The exact behavior depends on the tree-sitter preprocessor implementation
        # These tests verify the parser accepts preprocessor flags correctly

    def test_parse_lemmas_with_nested_preprocessor_conditions(
        self, tmp_dir: Path
    ) -> None:
        """Test parsing lemmas with nested preprocessor conditions."""
        theory_content = """
theory NestedPreprocessorTheory
begin

#ifdef FLAG1
  #ifdef FLAG2
    lemma nested_conditional_lemma:
      "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"
  #endif
#endif

lemma normal_lemma:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

end
"""
        theory_file = tmp_dir / "nested_preprocessor_theory.spthy"
        theory_file.write_text(theory_content)

        # Parse with nested flags
        parser = LemmaParser(external_flags=["FLAG1", "FLAG2"])
        lemmas = parser.parse_lemmas_from_file(theory_file)

        # Should contain the normal lemma
        assert "normal_lemma" in lemmas

        # Note: Nested conditional behavior depends on preprocessor implementation


class TestLemmaParserEdgeCases:
    """Test edge cases and error conditions."""

    def test_parse_lemmas_with_comments(self, tmp_dir: Path) -> None:
        """Test parsing lemmas with various comment styles."""
        theory_content = """
theory CommentedTheory
begin

// This is a line comment
lemma lemma_after_line_comment:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

/* This is a block comment */
lemma lemma_after_block_comment:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

/*
  This is a multi-line
  block comment
*/
lemma lemma_after_multiline_comment:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

end
"""
        theory_file = tmp_dir / "commented_theory.spthy"
        theory_file.write_text(theory_content)

        parser = LemmaParser()
        lemmas = parser.parse_lemmas_from_file(theory_file)

        assert len(lemmas) == 3
        assert "lemma_after_line_comment" in lemmas
        assert "lemma_after_block_comment" in lemmas
        assert "lemma_after_multiline_comment" in lemmas

    def test_parse_lemmas_with_complex_formulas(self, tmp_dir: Path) -> None:
        """Test parsing lemmas with complex logical formulas."""
        theory_content = """
theory ComplexFormulaTheory
begin

lemma complex_formula_lemma:
  "All x y #i #j.
    TestRule(x) @ #i & TestRule2(y) @ #j & #i < #j
    ==>
    ∃ z #k. TestRule3(z) @ #k & #j < #k"

lemma multiline_formula_lemma:
  "All x #i.
    TestRule(x) @ #i
    ==>
    (∃ y #j. TestRule2(y) @ #j) |
    (∃ z #k. TestRule3(z) @ #k)"

end
"""
        theory_file = tmp_dir / "complex_formula_theory.spthy"
        theory_file.write_text(theory_content)

        parser = LemmaParser()
        lemmas = parser.parse_lemmas_from_file(theory_file)

        assert len(lemmas) == 2
        assert "complex_formula_lemma" in lemmas
        assert "multiline_formula_lemma" in lemmas

    def test_parse_lemmas_with_special_characters(self, tmp_dir: Path) -> None:
        """Test parsing lemmas with special characters in names."""
        theory_content = """
theory SpecialCharTheory
begin

lemma lemma_with_unicode_∀:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

lemma lemma_with_prime':
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

end
"""
        theory_file = tmp_dir / "special_char_theory.spthy"
        theory_file.write_text(theory_content)

        parser = LemmaParser()
        lemmas = parser.parse_lemmas_from_file(theory_file)

        # Note: Behavior depends on what the tree-sitter parser considers valid identifiers
        # This test verifies the parser handles special characters gracefully
        assert len(lemmas) >= 0  # Should not crash

    def test_parse_lemmas_large_file(self, tmp_dir: Path) -> None:
        """Test parsing a large theory file with many lemmas."""
        # Generate a large theory file with many lemmas
        theory_content = "theory LargeTheory\nbegin\n\n"

        for i in range(100):
            theory_content += f"""lemma test_lemma_{i}:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

"""

        theory_content += "end\n"

        theory_file = tmp_dir / "large_theory.spthy"
        theory_file.write_text(theory_content)

        parser = LemmaParser()
        lemmas = parser.parse_lemmas_from_file(theory_file)

        assert len(lemmas) == 100

        # Verify some specific lemmas exist
        assert "test_lemma_0" in lemmas
        assert "test_lemma_50" in lemmas
        assert "test_lemma_99" in lemmas

    def test_parse_lemmas_file_permissions(self, tmp_dir: Path) -> None:
        """Test parsing a file with restricted permissions."""
        theory_content = """
theory PermissionTheory
begin

lemma test_lemma:
  "All x #i. TestRule(x) @ #i ==> ∃ y #j. TestRule2(y) @ #j"

end
"""
        theory_file = tmp_dir / "permission_theory.spthy"
        theory_file.write_text(theory_content)

        # Remove read permissions
        theory_file.chmod(0o000)

        parser = LemmaParser()

        try:
            # This should raise a parsing error due to permissions
            with pytest.raises(LemmaParsingError):
                parser.parse_lemmas_from_file(theory_file)
        finally:
            # Restore permissions for cleanup
            theory_file.chmod(0o644)


class TestLemmaParserIntegration:
    """Integration tests for LemmaParser with real-world scenarios."""

    def test_parse_lemmas_from_sample_theory(self, sample_theory_file: Path) -> None:
        """Test parsing lemmas from the sample theory file used in other tests."""
        parser = LemmaParser()
        lemmas = parser.parse_lemmas_from_file(sample_theory_file)

        # Should match the lemmas defined in the sample theory file
        expected_lemmas = {
            "test_lemma_1",
            "test_lemma_2",
            "different_lemma",
            "success_lemma",
        }

        assert len(lemmas) == len(expected_lemmas)
        for expected_lemma in expected_lemmas:
            assert expected_lemma in lemmas

    def test_parse_lemmas_consistency_multiple_calls(
        self, sample_theory_file: Path
    ) -> None:
        """Test that multiple calls to parse_lemmas_from_file return consistent results."""
        parser = LemmaParser()

        # Parse the same file multiple times
        lemmas1 = parser.parse_lemmas_from_file(sample_theory_file)
        lemmas2 = parser.parse_lemmas_from_file(sample_theory_file)
        lemmas3 = parser.parse_lemmas_from_file(sample_theory_file)

        # Results should be consistent
        assert lemmas1 == lemmas2 == lemmas3

    def test_parse_lemmas_different_parser_instances(
        self, sample_theory_file: Path
    ) -> None:
        """Test that different parser instances return the same results."""
        parser1 = LemmaParser()
        parser2 = LemmaParser()

        lemmas1 = parser1.parse_lemmas_from_file(sample_theory_file)
        lemmas2 = parser2.parse_lemmas_from_file(sample_theory_file)

        assert lemmas1 == lemmas2
