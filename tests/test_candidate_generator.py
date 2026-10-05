"""
tests/test_candidate_generator.py
Comprehensive unit tests for progressive, lazy candidate generator in Version 2.
"""

import inspect
from pathlib import Path
from unittest.mock import patch

import pytest

from modules.candidate_generator import (
    generate_candidates,
    generate_stage1_candidates,
    generate_stage2_candidates,
    generate_stage3_candidates,
)
from modules.hint_collector import HintModel
from modules.search_space import calculate_search_space


# ──────────────────────────────────────────────────────────────────────────────
# Core Candidate Generator Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestCandidateGeneratorCore:
    def test_1_empty_disabled_hints_yields_empty_stream(self) -> None:
        hints = HintModel()
        candidates = list(generate_candidates(hints))
        assert candidates == []

    def test_2_one_name(self) -> None:
        hints = HintModel(name=["Saniya"])
        candidates = list(generate_candidates(hints))
        assert "Saniya" in candidates
        assert len(candidates) == len(set(candidates))
        assert len(candidates) == calculate_search_space(hints).total_distinct_count

    def test_3_multiple_names(self) -> None:
        hints = HintModel(name=["Saniya", "Sakshi"])
        candidates = list(generate_candidates(hints))
        assert "Saniya" in candidates
        assert "Sakshi" in candidates
        assert len(candidates) == calculate_search_space(hints).total_distinct_count

    def test_4_one_word(self) -> None:
        hints = HintModel(word=["school"])
        candidates = list(generate_candidates(hints))
        assert "school" in candidates
        assert len(candidates) == calculate_search_space(hints).total_distinct_count

    def test_5_multiple_words(self) -> None:
        hints = HintModel(word=["school", "office"])
        candidates = list(generate_candidates(hints))
        assert "school" in candidates
        assert "office" in candidates
        assert len(candidates) == calculate_search_space(hints).total_distinct_count

    def test_6_numbers(self) -> None:
        hints = HintModel(number=["7070", "123"])
        candidates = list(generate_candidates(hints))
        assert "7070" in candidates
        assert "123" in candidates
        assert len(candidates) == calculate_search_space(hints).total_distinct_count

    def test_7_special_characters(self) -> None:
        hints = HintModel(name=["Saniya"], special_character=["@", "#"])
        candidates = list(generate_candidates(hints))
        assert "Saniya@" in candidates
        assert "Saniya#" in candidates
        assert len(candidates) == calculate_search_space(hints).total_distinct_count

    def test_8_prefix(self) -> None:
        hints = HintModel(name=["Saniya"], prefix=["@Sai"])
        candidates = list(generate_candidates(hints))
        assert "@SaiSaniya" in candidates
        assert len(candidates) == calculate_search_space(hints).total_distinct_count

    def test_9_suffix(self) -> None:
        hints = HintModel(name=["Saniya"], suffix=["123@"])
        candidates = list(generate_candidates(hints))
        assert "Saniya123@" in candidates
        assert len(candidates) == calculate_search_space(hints).total_distinct_count

    def test_10_multiple_active_categories(self) -> None:
        hints = HintModel(
            name=["Saniya"],
            word=["School"],
            number=["7070"],
            special_character=["@"],
            prefix=["Pre"],
            suffix=["Suf"],
        )
        candidates = list(generate_candidates(hints))
        assert len(candidates) == calculate_search_space(hints).total_distinct_count


# ──────────────────────────────────────────────────────────────────────────────
# Stage-Specific Generation Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestCandidateGeneratorStages:
    def test_11_stage1_generation(self) -> None:
        hints = HintModel(name=["Saniya"], number=["7070"], special_character=["@"])
        s1 = list(generate_stage1_candidates(hints))
        assert "Saniya" in s1
        assert "7070" in s1
        assert "Saniya7070" in s1
        assert "Saniya@" in s1
        assert "Saniya7070@" in s1

    def test_12_stage2_generation(self) -> None:
        hints = HintModel(name=["Saniya"], number=["7070"])
        seen = set(generate_stage1_candidates(hints))
        s2 = list(generate_stage2_candidates(hints, seen=seen))
        # Case mutations
        assert "saniya" in s2 or "saniya" in seen
        assert "SANIYA" in s2
        # Delimiters
        assert "Saniya_7070" in s2
        assert "Saniya-7070" in s2

    def test_13_stage3_generation(self) -> None:
        hints = HintModel(name=["Saniya", "Sakshi"], number=["2024"])
        seen = set(generate_stage1_candidates(hints))
        seen.update(generate_stage2_candidates(hints, seen=seen))
        s3 = list(generate_stage3_candidates(hints, seen=seen))
        # Compound
        assert "SaniyaSakshi" in s3
        assert "SaniyaSakshi2024" in s3
        # 2-digit year
        assert "Saniya24" in s3


# ──────────────────────────────────────────────────────────────────────────────
# Length Filtering Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestCandidateGeneratorLengthFiltering:
    def test_14_length_filtering_general(self) -> None:
        hints = HintModel(name=["A"], number=["1234567890"], min_length=4, max_length=6)
        candidates = list(generate_candidates(hints))
        for c in candidates:
            assert 4 <= len(c) <= 6

    def test_15_minimum_boundary_only(self) -> None:
        hints = HintModel(name=["Bob"], number=["1"], min_length=4)
        candidates = list(generate_candidates(hints))
        assert "Bob" not in candidates  # len 3
        assert "1" not in candidates    # len 1
        assert "Bob1" in candidates     # len 4
        for c in candidates:
            assert len(c) >= 4

    def test_16_maximum_boundary_only(self) -> None:
        hints = HintModel(name=["Saniya"], word=["University"], max_length=8)
        candidates = list(generate_candidates(hints))
        assert "University" not in candidates  # len 10
        for c in candidates:
            assert len(c) <= 8

    def test_17_both_boundaries(self) -> None:
        hints = HintModel(name=["Saniya"], number=["7070"], min_length=10, max_length=10)
        candidates = list(generate_candidates(hints))
        for c in candidates:
            assert len(c) == 10

    def test_18_disabled_categories(self) -> None:
        hints = HintModel(
            name=["Saniya"],
            word=None,
            number=None,
            special_character=None,
            prefix=None,
            suffix=None,
        )
        candidates = list(generate_candidates(hints))
        assert len(candidates) == calculate_search_space(hints).total_distinct_count


# ──────────────────────────────────────────────────────────────────────────────
# Deduplication, Determinism & Lazy Generator Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestCandidateGeneratorProperties:
    def test_19_duplicate_elimination_within_stages(self) -> None:
        hints = HintModel(name=["Saniya"], number=["7070"])
        candidates = list(generate_candidates(hints))
        assert len(candidates) == len(set(candidates))

    def test_20_cross_stage_duplicate_elimination(self) -> None:
        # e.g. "Saniya" lowercase in Stage 2 if already in Stage 1
        hints = HintModel(name=["saniya"], number=["1"])
        candidates = list(generate_candidates(hints))
        assert candidates.count("saniya") == 1

    def test_21_deterministic_ordering(self) -> None:
        hints = HintModel(
            name=["Saniya", "Sakshi"],
            word=["School"],
            number=["7070"],
            special_character=["@"],
            prefix=["#"],
            suffix=["!"],
            min_length=6,
            max_length=16,
        )
        run1 = list(generate_candidates(hints))
        run2 = list(generate_candidates(hints))
        run3 = list(generate_candidates(hints))

        assert run1 == run2 == run3

    def test_22_lazy_iterator_generator_behavior(self) -> None:
        hints = HintModel(name=["Saniya"], number=["7070"])
        gen = generate_candidates(hints)

        assert inspect.isgenerator(gen)
        # Advance item by item
        first = next(gen)
        second = next(gen)
        assert isinstance(first, str)
        assert isinstance(second, str)
        assert first != second

    @pytest.mark.parametrize(
        "hints",
        [
            HintModel(name=["Saniya"]),
            HintModel(name=["Saniya", "Sakshi"]),
            HintModel(name=["Saniya"], number=["7070"]),
            HintModel(name=["Saniya"], number=["7070", "123"]),
            HintModel(name=["Saniya"], special_character=["@"]),
            HintModel(name=["Saniya"], prefix=["Pre"], suffix=["Suf"]),
            HintModel(name=["Saniya"], number=["7070"], min_length=8, max_length=12),
            HintModel(name=["Saniya", "Sakshi"], word=["Home"], number=["7070"], special_character=["@"]),
        ],
    )
    def test_23_search_space_count_equals_generator_unique_count(self, hints: HintModel) -> None:
        calculated_count = calculate_search_space(hints).total_distinct_count
        generated_list = list(generate_candidates(hints))
        assert len(generated_list) == calculated_count
        assert len(set(generated_list)) == calculated_count

    def test_24_no_candidate_generated_twice(self) -> None:
        hints = HintModel(
            name=["Saniya", "Sakshi", "Saura"],
            word=["School", "Office"],
            number=["7070", "123", "2024"],
            special_character=["@", "#"],
            prefix=["Pre"],
            suffix=["Suf"],
        )
        candidates = list(generate_candidates(hints))
        assert len(candidates) == len(set(candidates))

    def test_25_generator_does_not_call_verifier(self) -> None:
        hints = HintModel(name=["Saniya"], number=["7070"])
        with patch("modules.verifier.verify") as mock_verify:
            _ = list(generate_candidates(hints))
            mock_verify.assert_not_called()

    def test_26_generator_does_not_create_files(self, tmp_path: Path) -> None:
        hints = HintModel(name=["Saniya"], number=["7070"])
        initial_files = list(tmp_path.iterdir())
        _ = list(generate_candidates(hints))
        final_files = list(tmp_path.iterdir())
        assert initial_files == final_files


# ──────────────────────────────────────────────────────────────────────────────
# Boundary Overlap Tests (Prefix + Base Case-Insensitive Shared Boundary)
# ──────────────────────────────────────────────────────────────────────────────


class TestBoundaryOverlapVariation:
    def test_prefix_boundary_overlap_basic(self) -> None:
        hints = HintModel(name=["ayush"], prefix=["@A"])
        candidates = list(generate_candidates(hints))
        # Normal candidate
        assert "@Aayush" in candidates
        # Overlap candidate (prefix casing preserved)
        assert "@Ayush" in candidates
        assert len(candidates) == calculate_search_space(hints).total_distinct_count

    def test_prefix_boundary_overlap_with_number(self) -> None:
        hints = HintModel(name=["ayush"], number=["7210"], prefix=["@A"])
        candidates = list(generate_candidates(hints))
        assert "@Aayush7210" in candidates
        assert "@Ayush7210" in candidates
        assert len(candidates) == calculate_search_space(hints).total_distinct_count

    def test_prefix_non_overlapping_does_not_create_overlap(self) -> None:
        hints = HintModel(name=["ayush"], prefix=["@X"])
        candidates = list(generate_candidates(hints))
        assert "@Xayush" in candidates
        assert "@Xyush" not in candidates
        assert len(candidates) == calculate_search_space(hints).total_distinct_count

    def test_case_insensitive_boundary_matching(self) -> None:
        # Prefix lowercase 'a', name uppercase 'Ayush'
        hints1 = HintModel(name=["Ayush"], prefix=["@a"])
        cands1 = list(generate_candidates(hints1))
        assert "@aAyush" in cands1
        assert "@ayush" in cands1

        # Prefix uppercase 'A', name lowercase 'ayush'
        hints2 = HintModel(name=["ayush"], prefix=["@A"])
        cands2 = list(generate_candidates(hints2))
        assert "@Aayush" in cands2
        assert "@Ayush" in cands2

    def test_overlap_candidate_length_filtering(self) -> None:
        # "@Ayush" is length 6, "@Aayush" is length 7
        # With min_length=7, "@Ayush" should be filtered out, "@Aayush" kept
        hints_min = HintModel(name=["ayush"], prefix=["@A"], min_length=7)
        cands_min = list(generate_candidates(hints_min))
        assert "@Aayush" in cands_min
        assert "@Ayush" not in cands_min

        # With max_length=6, "@Ayush" should be kept, "@Aayush" filtered out
        hints_max = HintModel(name=["ayush"], prefix=["@A"], max_length=6)
        cands_max = list(generate_candidates(hints_max))
        assert "@Ayush" in cands_max
        assert "@Aayush" not in cands_max

    def test_real_pc_test_case_includes_target_password(self) -> None:
        """The exact real-world scenario from PC testing."""
        hints = HintModel(
            name=["ayush"],
            number=["7210"],
            special_character=["@", "*", ")"],
            prefix=["@A"],
            suffix=["10"],
            min_length=10,
            max_length=11,
        )
        s1 = list(generate_stage1_candidates(hints))
        all_cands = list(generate_candidates(hints))
        search_space = calculate_search_space(hints)

        # Target password must be in Stage 1 and in all candidates
        assert "@Ayush7210" in s1
        assert "@Aayush7210" in s1
        assert "@Ayush7210" in all_cands
        assert "@Aayush7210" in all_cands
        assert len(all_cands) == search_space.total_distinct_count

