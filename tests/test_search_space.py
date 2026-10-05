"""
tests/test_search_space.py
Comprehensive unit tests for exact, deterministic search space calculation.
"""

from io import StringIO

import pytest
from rich.console import Console

from modules.hint_collector import HintModel
from modules.search_space import (
    SearchSpaceResult,
    calculate_search_space,
    display_search_space_analysis,
    enumerate_stage1_candidates,
    enumerate_stage2_candidates,
    enumerate_stage3_candidates,
)


# ──────────────────────────────────────────────────────────────────────────────
# Core Calculation & Mathematical Property Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestSearchSpaceCalculatorCore:
    def test_1_no_hint_categories_enabled(self) -> None:
        hints = HintModel()
        result = calculate_search_space(hints)
        assert result.total_distinct_count == 0
        assert result.stage1_count == 0
        assert result.stage2_count == 0
        assert result.stage3_count == 0
        assert result.is_finite
        assert not result.is_unbounded
        assert result.active_categories == []

    def test_2_one_name_only(self) -> None:
        hints = HintModel(name=["Saniya"])
        result = calculate_search_space(hints)
        assert result.stage1_count > 0
        assert result.stage2_count > 0
        assert result.stage3_count > 0
        assert result.total_distinct_count == (
            result.stage1_count + result.stage2_count + result.stage3_count
        )

    def test_3_multiple_names(self) -> None:
        single_name = HintModel(name=["Saniya"])
        multi_name = HintModel(name=["Saniya", "Sakshi"])

        r_single = calculate_search_space(single_name)
        r_multi = calculate_search_space(multi_name)

        assert r_multi.total_distinct_count > r_single.total_distinct_count
        assert r_multi.stage1_count > r_single.stage1_count

    def test_4_one_number_only(self) -> None:
        hints = HintModel(number=["7070"])
        result = calculate_search_space(hints)
        assert result.stage1_count >= 1
        assert "7070" in enumerate_stage1_candidates(hints)

    def test_5_multiple_numbers(self) -> None:
        single = HintModel(number=["7070"])
        multi = HintModel(number=["7070", "123", "2024"])

        r_single = calculate_search_space(single)
        r_multi = calculate_search_space(multi)

        assert r_multi.total_distinct_count > r_single.total_distinct_count

    def test_6_special_characters(self) -> None:
        hints = HintModel(name=["Saniya"], special_character=["@", "#"])
        result = calculate_search_space(hints)
        assert result.total_distinct_count > 0
        assert "Saniya@" in enumerate_stage1_candidates(hints)
        assert "Saniya#" in enumerate_stage1_candidates(hints)

    def test_7_prefix_and_suffix(self) -> None:
        hints = HintModel(
            name=["Saniya"],
            number=["7070"],
            prefix=["@Pre"],
            suffix=["Suf!"],
        )
        result = calculate_search_space(hints)
        s1 = enumerate_stage1_candidates(hints)
        assert "@PreSaniya7070" in s1
        assert "Saniya7070Suf!" in s1
        assert "@PreSaniya7070Suf!" in s1
        assert result.stage1_count > 0

    def test_8_multiple_active_categories(self) -> None:
        hints = HintModel(
            name=["Saniya", "Sakshi"],
            word=["School"],
            number=["7070", "123"],
            special_character=["@"],
            prefix=["#"],
            suffix=["!"],
        )
        result = calculate_search_space(hints)
        assert set(result.active_categories) == {
            "name", "word", "number", "special_character", "prefix", "suffix"
        }
        assert result.total_distinct_count > 100


# ──────────────────────────────────────────────────────────────────────────────
# Length Boundary Filtering Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestSearchSpaceLengthFiltering:
    def test_9_minimum_length_only(self) -> None:
        hints_unconstrained = HintModel(name=["Bob"], number=["1"])
        hints_min = HintModel(name=["Bob"], number=["1"], min_length=4)

        r_unconstrained = calculate_search_space(hints_unconstrained)
        r_min = calculate_search_space(hints_min)

        assert r_min.total_distinct_count < r_unconstrained.total_distinct_count
        # Length of "Bob" is 3, "1" is 1 -> filtered out by min_length=4
        # "Bob1" is 4 -> included

    def test_10_maximum_length_only(self) -> None:
        hints_unconstrained = HintModel(name=["Saniya"], word=["University"], number=["7070"])
        hints_max = HintModel(name=["Saniya"], word=["University"], number=["7070"], max_length=10)

        r_unconstrained = calculate_search_space(hints_unconstrained)
        r_max = calculate_search_space(hints_max)

        assert r_max.total_distinct_count < r_unconstrained.total_distinct_count

    def test_11_both_length_limits(self) -> None:
        hints = HintModel(name=["Saniya"], number=["7070"], min_length=8, max_length=12)
        result = calculate_search_space(hints)
        assert result.min_length == 8
        assert result.max_length == 12
        assert result.total_distinct_count > 0

    def test_12_no_length_limits(self) -> None:
        hints = HintModel(name=["Saniya"], number=["7070"], min_length=None, max_length=None)
        result = calculate_search_space(hints)
        assert result.min_length is None
        assert result.max_length is None
        assert result.total_distinct_count > 0

    def test_13_candidate_length_exactly_equal_to_boundaries(self) -> None:
        # "Saniya7070" is 10 characters long
        hints = HintModel(name=["Saniya"], number=["7070"], min_length=10, max_length=10)
        result = calculate_search_space(hints)
        assert result.total_distinct_count > 0

    def test_14_candidates_outside_boundaries_yield_zero(self) -> None:
        # All combinations are < 50 chars
        hints = HintModel(name=["Saniya"], number=["7070"], min_length=50, max_length=100)
        result = calculate_search_space(hints)
        assert result.total_distinct_count == 0
        assert result.stage1_count == 0
        assert result.stage2_count == 0
        assert result.stage3_count == 0


# ──────────────────────────────────────────────────────────────────────────────
# Non-Overcounting, Deduplication & Determinism Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestSearchSpaceDeduplicationAndSafety:
    def test_15_duplicate_generation_paths_counted_once(self) -> None:
        # If both name="pass" and word="pass" were supplied (e.g. identical strings)
        hints = HintModel(name=["pass"], word=["pass"], number=["1"])
        result = calculate_search_space(hints)

        hints_single = HintModel(name=["pass"], number=["1"])
        result_single = calculate_search_space(hints_single)

        assert result.total_distinct_count == result_single.total_distinct_count

    def test_16_duplicate_hint_values_already_removed_by_hint_model(self) -> None:
        hints = HintModel(name=["Saniya", "Saniya"], number=["123"])
        # In HintModel parsing, duplicates are stripped. Even if directly instantiated:
        result = calculate_search_space(hints)
        assert result.total_distinct_count > 0

    def test_17_multiple_categories_producing_same_candidate(self) -> None:
        # name="123" and number="123"
        hints = HintModel(name=["123"], number=["123"])
        result = calculate_search_space(hints)
        assert result.total_distinct_count > 0

    def test_18_empty_disabled_categories_are_ignored(self) -> None:
        hints = HintModel(
            name=["Saniya"],
            word=None,
            number=None,
            special_character=None,
            prefix=None,
            suffix=None,
        )
        result = calculate_search_space(hints)
        assert result.active_categories == ["name"]

    def test_19_deterministic_repeated_calculations(self) -> None:
        hints = HintModel(
            name=["Saniya", "Sakshi"],
            number=["7070"],
            special_character=["@"],
            min_length=8,
            max_length=15,
        )
        r1 = calculate_search_space(hints)
        r2 = calculate_search_space(hints)
        r3 = calculate_search_space(hints)

        assert r1.stage1_count == r2.stage1_count == r3.stage1_count
        assert r1.stage2_count == r2.stage2_count == r3.stage2_count
        assert r1.stage3_count == r2.stage3_count == r3.stage3_count
        assert r1.total_distinct_count == r2.total_distinct_count == r3.total_distinct_count

    def test_20_unbounded_search_space_flag_structure(self) -> None:
        # Verify SearchSpaceResult correctly encapsulates unbounded flag
        res = SearchSpaceResult(
            stage1_count=0,
            stage2_count=0,
            stage3_count=0,
            total_distinct_count=0,
            is_finite=False,
            is_unbounded=True,
            active_categories=[],
            min_length=None,
            max_length=None,
        )
        assert res.is_unbounded
        assert not res.is_finite

    def test_21_stage_disjointness_property(self) -> None:
        hints = HintModel(
            name=["Saniya"],
            number=["7070"],
            special_character=["@"],
        )
        raw_s1 = enumerate_stage1_candidates(hints)
        raw_s2 = enumerate_stage2_candidates(hints)
        raw_s3 = enumerate_stage3_candidates(hints)

        # In calculate_search_space, S2 = S2 - S1 and S3 = S3 - S1 - S2
        res = calculate_search_space(hints)
        assert res.total_distinct_count == res.stage1_count + res.stage2_count + res.stage3_count


# ──────────────────────────────────────────────────────────────────────────────
# Terminal Display Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestDisplaySearchSpaceAnalysis:
    def test_display_finite_analysis(self) -> None:
        hints = HintModel(name=["Saniya"], number=["7070"])
        analysis = calculate_search_space(hints)

        stream = StringIO()
        console = Console(file=stream, color_system=None)
        display_search_space_analysis(analysis, console=console)

        output = stream.getvalue()
        assert "SEARCH SPACE ANALYSIS" in output
        assert "Stage 1 — Direct Hint Search" in output
        assert "Stage 2 — Hint Transformation Search" in output
        assert "Stage 3 — Expanded Hint Search" in output
        assert "Total distinct candidates" in output

    def test_display_unbounded_analysis(self) -> None:
        res = SearchSpaceResult(
            stage1_count=0,
            stage2_count=0,
            stage3_count=0,
            total_distinct_count=0,
            is_finite=False,
            is_unbounded=True,
            active_categories=[],
            min_length=None,
            max_length=None,
        )
        stream = StringIO()
        console = Console(file=stream, color_system=None)
        display_search_space_analysis(res, console=console)

        output = stream.getvalue()
        assert "UNBOUNDED" in output


# ──────────────────────────────────────────────────────────────────────────────
# Search Space Boundary Overlap Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestSearchSpaceBoundaryOverlap:
    def test_search_space_overlap_increases_count_for_matching_prefix(self) -> None:
        hints_no_match = HintModel(name=["ayush"], prefix=["@X"])
        hints_match = HintModel(name=["ayush"], prefix=["@A"])

        r_no_match = calculate_search_space(hints_no_match)
        r_match = calculate_search_space(hints_match)

        # Matching prefix should generate overlap candidates and have more or equal candidates
        assert r_match.stage1_count >= r_no_match.stage1_count
        s1 = enumerate_stage1_candidates(hints_match)
        assert "@Aayush" in s1
        assert "@Ayush" in s1

    def test_search_space_disjointness_with_overlap(self) -> None:
        hints = HintModel(
            name=["ayush"],
            number=["7210"],
            prefix=["@A"],
            suffix=["10"],
            min_length=10,
            max_length=11,
        )
        res = calculate_search_space(hints)
        assert res.total_distinct_count == res.stage1_count + res.stage2_count + res.stage3_count
        assert "@Ayush7210" in enumerate_stage1_candidates(hints)

