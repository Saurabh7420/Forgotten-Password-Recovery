"""
candidate_ranker.py
Deterministic priority ranking for generated candidate passwords in Version 2.

Overview & Design Principles
----------------------------
- Pure ranking layer: Evaluates candidates produced by `candidate_generator`.
- Never creates, alters, or invents new candidate strings.
- 100% deterministic and reproducible scoring (no randomness, timestamps, or network calls).
- Prioritizes candidates with high hint-fidelity:
  - Exact prefix and suffix preservation.
  - Exact name and word containment with original casing.
  - Number and special character containment.
  - Canonical Stage 1 combinations before transformed (Stage 2) or compound (Stage 3) combinations.
- Implements stable deterministic tie-breaking (score descending -> original index -> lexical order).
"""

from __future__ import annotations

from typing import Iterable, Iterator, Sequence

from modules.hint_collector import HintModel
from modules.candidate_generator import (
    generate_stage1_candidates,
    generate_stage2_candidates,
    generate_stage3_candidates,
)


# ──────────────────────────────────────────────────────────────────────────────
# Deterministic Scoring Weights
# ──────────────────────────────────────────────────────────────────────────────

STAGE_WEIGHT_STAGE1: int = 100
STAGE_WEIGHT_STAGE2: int = 50
STAGE_WEIGHT_STAGE3: int = 0

WEIGHT_NAME_MATCH: int = 30
WEIGHT_WORD_MATCH: int = 25
WEIGHT_PREFIX_MATCH: int = 20
WEIGHT_SUFFIX_MATCH: int = 20
WEIGHT_NUMBER_MATCH: int = 15
WEIGHT_SPECIAL_MATCH: int = 10
WEIGHT_EXACT_CASING_BONUS: int = 10


# ──────────────────────────────────────────────────────────────────────────────
# Candidate Scoring
# ──────────────────────────────────────────────────────────────────────────────


def score_candidate(
    candidate: str,
    hints: HintModel,
    stage: int | None = None,
) -> int:
    """
    Compute a deterministic heuristic priority score for *candidate* against *hints*.

    Higher score indicates higher priority.

    Parameters
    ----------
    candidate:
        The candidate password string to evaluate.
    hints:
        The HintModel containing the user's supplied hints.
    stage:
        Optional stage identifier (1, 2, or 3) to factor in stage priority.

    Returns
    -------
    int
        Deterministic priority score.
    """
    score = 0

    # 1. Stage Priority Weight
    if stage == 1:
        score += STAGE_WEIGHT_STAGE1
    elif stage == 2:
        score += STAGE_WEIGHT_STAGE2
    elif stage == 3:
        score += STAGE_WEIGHT_STAGE3

    # 2. Prefix Match
    if hints.prefix:
        for p in hints.prefix:
            if candidate.startswith(p):
                score += WEIGHT_PREFIX_MATCH
                break

    # 3. Suffix Match
    if hints.suffix:
        for u in hints.suffix:
            if candidate.endswith(u):
                score += WEIGHT_SUFFIX_MATCH
                break

    # 4. Name Match & Casing Bonus
    if hints.name:
        for n in hints.name:
            if n in candidate:
                score += WEIGHT_NAME_MATCH + WEIGHT_EXACT_CASING_BONUS
                break
            elif n.lower() in candidate.lower():
                score += WEIGHT_NAME_MATCH
                break

    # 5. Word Match & Casing Bonus
    if hints.word:
        for w in hints.word:
            if w in candidate:
                score += WEIGHT_WORD_MATCH + WEIGHT_EXACT_CASING_BONUS
                break
            elif w.lower() in candidate.lower():
                score += WEIGHT_WORD_MATCH
                break

    # 6. Number Match
    if hints.number:
        for d in hints.number:
            if d in candidate:
                score += WEIGHT_NUMBER_MATCH
                break

    # 7. Special Character Match
    if hints.special_character:
        for s in hints.special_character:
            if s in candidate:
                score += WEIGHT_SPECIAL_MATCH
                break

    return score


# ──────────────────────────────────────────────────────────────────────────────
# Ranking Functions
# ──────────────────────────────────────────────────────────────────────────────


def rank_candidates(
    candidates: Iterable[str],
    hints: HintModel,
    stage: int | None = None,
) -> Iterator[str]:
    """
    Rank an arbitrary iterable of candidates in deterministic priority order.

    Deduplicates candidates on-the-fly and sorts by:
    1. Score descending
    2. Original input order (Timsort stability)
    3. Lexical string order as secondary tie-breaker

    Parameters
    ----------
    candidates:
        Iterable of candidate password strings.
    hints:
        HintModel instance containing user hints.
    stage:
        Optional stage identifier.

    Yields
    ------
    str
        Candidate strings ordered from highest to lowest priority.
    """
    seen: set[str] = set()
    buffered: list[tuple[str, int, int]] = []  # (candidate, score, index)

    for idx, cand in enumerate(candidates):
        if cand not in seen:
            seen.add(cand)
            s = score_candidate(cand, hints, stage=stage)
            buffered.append((cand, s, idx))

    # Sort deterministically: highest score first (-score), then original index, then lexical
    buffered.sort(key=lambda item: (-item[1], item[2], item[0]))

    for cand, _, _ in buffered:
        yield cand


def rank_progressive_candidates(hints: HintModel) -> Iterator[str]:
    """
    Progressively rank candidates stage-by-stage across all 3 stages.

    Executes Stage 1 -> Stage 2 -> Stage 3 sequentially, ranking candidates
    within each stage before yielding, maintaining strict cross-stage deduplication
    without materializing the full universe in memory at once.

    Parameters
    ----------
    hints:
        HintModel instance containing user hints.

    Yields
    ------
    str
        Ranked candidate strings.
    """
    if not hints.has_any_hints:
        return

    seen: set[str] = set()

    # ── Stage 1: Direct Hint Search ───────────────────────────────────────────
    s1_stream = list(generate_stage1_candidates(hints, seen=seen))
    for cand in rank_candidates(s1_stream, hints, stage=1):
        yield cand

    # ── Stage 2: Hint Transformation Search ───────────────────────────────────
    s2_stream = list(generate_stage2_candidates(hints, seen=seen))
    for cand in rank_candidates(s2_stream, hints, stage=2):
        yield cand

    # ── Stage 3: Expanded Hint Search ─────────────────────────────────────────
    s3_stream = list(generate_stage3_candidates(hints, seen=seen))
    for cand in rank_candidates(s3_stream, hints, stage=3):
        yield cand
