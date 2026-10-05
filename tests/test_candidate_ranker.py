"""
test_candidate_ranker.py
Automated test suite for candidate priority ranking in Version 2.
"""

from __future__ import annotations

import pytest
from typing import Iterator

from modules.hint_collector import HintModel
from modules.candidate_generator import generate_candidates
from modules.candidate_ranker import (
    score_candidate,
    rank_candidates,
    rank_progressive_candidates,
    STAGE_WEIGHT_STAGE1,
    STAGE_WEIGHT_STAGE2,
    STAGE_WEIGHT_STAGE3,
    WEIGHT_NAME_MATCH,
    WEIGHT_WORD_MATCH,
    WEIGHT_PREFIX_MATCH,
    WEIGHT_SUFFIX_MATCH,
    WEIGHT_NUMBER_MATCH,
    WEIGHT_SPECIAL_MATCH,
    WEIGHT_EXACT_CASING_BONUS,
)


# ──────────────────────────────────────────────────────────────────────────────
# 1. Scoring Logic Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_score_empty_hints():
    """Evaluating a candidate against empty hints gives score 0."""
    hints = HintModel()
    assert score_candidate("Password123!", hints) == 0


def test_score_stage_weights():
    """Stage weight is correctly added based on stage argument."""
    hints = HintModel(name=["Alice"])
    score_s1 = score_candidate("Alice", hints, stage=1)
    score_s2 = score_candidate("Alice", hints, stage=2)
    score_s3 = score_candidate("Alice", hints, stage=3)
    score_no_stage = score_candidate("Alice", hints, stage=None)

    base = WEIGHT_NAME_MATCH + WEIGHT_EXACT_CASING_BONUS
    assert score_no_stage == base
    assert score_s1 == base + STAGE_WEIGHT_STAGE1
    assert score_s2 == base + STAGE_WEIGHT_STAGE2
    assert score_s3 == base + STAGE_WEIGHT_STAGE3


def test_score_prefix_match():
    """Prefix match adds +20 if candidate starts with any prefix."""
    hints = HintModel(prefix=["@Sai", "admin#"])
    assert score_candidate("@Sai1234", hints) == WEIGHT_PREFIX_MATCH
    assert score_candidate("admin#pass", hints) == WEIGHT_PREFIX_MATCH
    assert score_candidate("wrong@Sai", hints) == 0


def test_score_suffix_match():
    """Suffix match adds +20 if candidate ends with any suffix."""
    hints = HintModel(suffix=["123@", "!2024"])
    assert score_candidate("Pass123@", hints) == WEIGHT_SUFFIX_MATCH
    assert score_candidate("Secret!2024", hints) == WEIGHT_SUFFIX_MATCH
    assert score_candidate("123@Pass", hints) == 0


def test_score_name_exact_and_case_insensitive():
    """Exact casing gets name weight + exact casing bonus; case-insensitive gets name weight."""
    hints = HintModel(name=["Saniya"])
    # Exact casing
    assert score_candidate("Saniya123", hints) == WEIGHT_NAME_MATCH + WEIGHT_EXACT_CASING_BONUS
    # Lowercase / altered casing
    assert score_candidate("saniya123", hints) == WEIGHT_NAME_MATCH
    assert score_candidate("SANIYA123", hints) == WEIGHT_NAME_MATCH


def test_score_word_exact_and_case_insensitive():
    """Exact casing gets word weight + exact casing bonus; case-insensitive gets word weight."""
    hints = HintModel(word=["school"])
    # Exact casing
    assert score_candidate("school7070", hints) == WEIGHT_WORD_MATCH + WEIGHT_EXACT_CASING_BONUS
    # Uppercase / altered casing
    assert score_candidate("School7070", hints) == WEIGHT_WORD_MATCH
    assert score_candidate("SCHOOL7070", hints) == WEIGHT_WORD_MATCH


def test_score_number_match():
    """Number match adds +15 if number is in candidate."""
    hints = HintModel(number=["7070", "2024"])
    assert score_candidate("Pass7070", hints) == WEIGHT_NUMBER_MATCH
    assert score_candidate("Pass2024", hints) == WEIGHT_NUMBER_MATCH
    assert score_candidate("Pass8080", hints) == 0


def test_score_special_character_match():
    """Special character match adds +10 if special character is in candidate."""
    hints = HintModel(special_character=["@", "#"])
    assert score_candidate("Pass@", hints) == WEIGHT_SPECIAL_MATCH
    assert score_candidate("Pass#", hints) == WEIGHT_SPECIAL_MATCH
    assert score_candidate("Pass$", hints) == 0


def test_score_multi_field_composite():
    """All matched fields aggregate additively into the total score."""
    hints = HintModel(
        name=["Saniya"],
        number=["7070"],
        special_character=["@"],
        prefix=["#"],
        suffix=["!"],
    )
    # Candidate matches: prefix (#), suffix (!), name exact (Saniya), number (7070), special (@) + Stage 1
    cand = "#Saniya7070@!"
    expected = (
        STAGE_WEIGHT_STAGE1
        + WEIGHT_PREFIX_MATCH
        + WEIGHT_SUFFIX_MATCH
        + WEIGHT_NAME_MATCH
        + WEIGHT_EXACT_CASING_BONUS
        + WEIGHT_NUMBER_MATCH
        + WEIGHT_SPECIAL_MATCH
    )
    assert score_candidate(cand, hints, stage=1) == expected


def test_score_multi_value_hints_token_matching():
    """Multi-value fields trigger match if any value in the list is present."""
    hints = HintModel(name=["Alice", "Bob"], number=["100", "200"])
    assert score_candidate("Alice100", hints) == (
        WEIGHT_NAME_MATCH + WEIGHT_EXACT_CASING_BONUS + WEIGHT_NUMBER_MATCH
    )
    assert score_candidate("Bob200", hints) == (
        WEIGHT_NAME_MATCH + WEIGHT_EXACT_CASING_BONUS + WEIGHT_NUMBER_MATCH
    )
    assert score_candidate("Charlie300", hints) == 0


# ──────────────────────────────────────────────────────────────────────────────
# 2. `rank_candidates` Functional Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_rank_candidates_empty_iterable():
    """Ranking an empty candidate stream yields nothing."""
    hints = HintModel(name=["Alice"])
    result = list(rank_candidates([], hints))
    assert result == []


def test_rank_candidates_single_candidate():
    """Ranking a single candidate yields that exact candidate."""
    hints = HintModel(name=["Alice"])
    result = list(rank_candidates(["Alice123"], hints))
    assert result == ["Alice123"]


def test_rank_candidates_sorts_by_score_descending():
    """Candidates with higher score are yielded before lower scoring candidates."""
    hints = HintModel(name=["Alice"], number=["123"], special_character=["!"])
    # Alice123! has name(exact), number, special -> high score
    # Alice123 has name(exact), number -> medium score
    # random_pass has no hints -> 0 score
    input_cands = ["random_pass", "Alice123", "Alice123!"]
    ranked = list(rank_candidates(input_cands, hints))
    assert ranked == ["Alice123!", "Alice123", "random_pass"]


def test_rank_candidates_tie_breaking_preserves_input_stability():
    """When candidates have identical scores, original stream order is preserved."""
    hints = HintModel(name=["Alice"])
    # Both have identical score (name exact)
    input_cands = ["Alice_apple", "Alice_banana", "Alice_cherry"]
    ranked = list(rank_candidates(input_cands, hints))
    assert ranked == ["Alice_apple", "Alice_banana", "Alice_cherry"]


def test_rank_candidates_deduplication():
    """Duplicate candidates in the input stream are yielded only once."""
    hints = HintModel(name=["Alice"])
    input_cands = ["Alice123", "Alice123", "Alice999", "Alice123"]
    ranked = list(rank_candidates(input_cands, hints))
    assert ranked == ["Alice123", "Alice999"]
    assert len(ranked) == 2


def test_rank_candidates_does_not_create_or_alter_candidates():
    """Ranker never creates, alters, or invents new strings."""
    hints = HintModel(name=["Alice"], number=["123"])
    input_cands = ["test1", "Alice123", "test2", "Alice"]
    ranked = list(rank_candidates(input_cands, hints))
    assert set(ranked) == set(input_cands)
    for cand in ranked:
        assert cand in input_cands


def test_rank_candidates_accepts_generator():
    """rank_candidates accepts lazy generator expressions as input."""
    hints = HintModel(name=["Alice"])
    gen = (f"Alice{i}" for i in range(5))
    ranked = list(rank_candidates(gen, hints))
    assert len(ranked) == 5
    assert all(isinstance(c, str) for c in ranked)


def test_rank_candidates_exact_casing_ranked_higher():
    """Exact case matching is ranked ahead of transformed casing."""
    hints = HintModel(name=["Saniya"], number=["7070"])
    input_cands = ["saniya7070", "Saniya7070", "SANIYA7070"]
    ranked = list(rank_candidates(input_cands, hints))
    # Saniya7070 has exact casing bonus -> ranked 1st
    assert ranked[0] == "Saniya7070"
    assert set(ranked) == set(input_cands)


# ──────────────────────────────────────────────────────────────────────────────
# 3. `rank_progressive_candidates` Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_rank_progressive_candidates_no_hints():
    """If hints are empty, rank_progressive_candidates yields 0 candidates."""
    hints = HintModel()
    assert list(rank_progressive_candidates(hints)) == []


def test_rank_progressive_candidates_matches_generator_universe():
    """The set of candidates from rank_progressive_candidates exactly equals generate_candidates."""
    hints = HintModel(
        name=["Saniya"],
        number=["7070"],
        special_character=["@"],
        min_length=4,
        max_length=15,
    )
    unranked_set = set(generate_candidates(hints))
    ranked_list = list(rank_progressive_candidates(hints))
    ranked_set = set(ranked_list)

    assert len(ranked_list) == len(ranked_set), "Ranked list must contain zero duplicates"
    assert ranked_set == unranked_set, "Ranked candidates set must exactly match generated set"


def test_rank_progressive_stage_precedence():
    """Stage 1 candidates are prioritized before Stage 2 and Stage 3 candidates."""
    hints = HintModel(
        name=["Saniya"],
        number=["7070"],
        special_character=["@"],
    )
    ranked = list(rank_progressive_candidates(hints))

    # Stage 1 candidate (e.g. Saniya7070@) must appear early in the output
    # Stage 2 transformations (e.g. saniya7070@ or SANIYA7070@) appear after Stage 1
    assert "Saniya7070@" in ranked
    pos_s1 = ranked.index("Saniya7070@")
    if "saniya7070@" in ranked:
        pos_s2 = ranked.index("saniya7070@")
        assert pos_s1 < pos_s2


def test_rank_progressive_deterministic_repeatability():
    """Multiple runs of rank_progressive_candidates on the same hints produce identical sequences."""
    hints = HintModel(
        name=["Sakshi", "Saurabh"],
        number=["123", "2024"],
        special_character=["!", "#"],
        prefix=["admin"],
    )
    run1 = list(rank_progressive_candidates(hints))
    run2 = list(rank_progressive_candidates(hints))
    assert run1 == run2


def test_rank_progressive_cross_stage_deduplication():
    """Deduplication is maintained across stages without leaking duplicates."""
    hints = HintModel(
        name=["Saniya"],
        number=["7070"],
    )
    ranked = list(rank_progressive_candidates(hints))
    seen = set()
    for cand in ranked:
        assert cand not in seen, f"Duplicate candidate found: {cand}"
        seen.add(cand)


def test_rank_candidates_returns_iterator():
    """rank_candidates returns an Iterator."""
    hints = HintModel(name=["Alice"])
    res = rank_candidates(["Alice"], hints)
    assert isinstance(res, Iterator)
    assert next(res) == "Alice"


def test_rank_progressive_candidates_returns_iterator():
    """rank_progressive_candidates returns an Iterator."""
    hints = HintModel(name=["Alice"])
    res = rank_progressive_candidates(hints)
    assert isinstance(res, Iterator)
