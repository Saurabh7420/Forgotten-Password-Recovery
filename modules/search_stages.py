"""
search_stages.py
Progressive 3-stage password recovery executor for Version 2.

Stage Architecture
------------------
- Stage 1: Direct Hint Search (Canonical direct combinations)
- Stage 2: Hint Transformation Search (Casing, delimiters, l33t variations)
- Stage 3: Expanded Hint Search (Compound pairings, reversed, repeated/years)

Execution Protocol
------------------
- Sequential execution: Stage 1 -> Stage 2 -> Stage 3.
- Lazy execution: Subsequent stages are never generated or evaluated if an earlier stage succeeds.
- Global deduplication: Shared `seen` set ensures no candidate is ever verified twice across stages.
- Deterministic ranking: Candidates within each stage are ranked by priority before verification.
- Instant termination: Verification stops immediately upon finding the correct password.
- Pure local processing: Zero network calls, zero external API calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

from modules.hint_collector import HintModel
from modules.attempt_logger import AttemptLogger, RoundHistoryLogger
from modules.candidate_generator import (
    generate_stage1_candidates,
    generate_stage2_candidates,
    generate_stage3_candidates,
)
from modules.candidate_ranker import rank_candidates
from modules.progress import HintProgressUI
from modules.verifier import verify


# ──────────────────────────────────────────────────────────────────────────────
# Stage Constants
# ──────────────────────────────────────────────────────────────────────────────

STAGE_1_ID: int = 1
STAGE_1_NAME: str = "Stage 1 — Direct Hint Search"

STAGE_2_ID: int = 2
STAGE_2_NAME: str = "Stage 2 — Hint Transformation Search"

STAGE_3_ID: int = 3
STAGE_3_NAME: str = "Stage 3 — Expanded Hint Search"

STAGE_NAMES: dict[int, str] = {
    STAGE_1_ID: STAGE_1_NAME,
    STAGE_2_ID: STAGE_2_NAME,
    STAGE_3_ID: STAGE_3_NAME,
}

ALL_STAGES: tuple[int, ...] = (STAGE_1_ID, STAGE_2_ID, STAGE_3_ID)


# ──────────────────────────────────────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class StageStats:
    """Statistics for an individual recovery stage execution."""
    stage_id: int
    stage_name: str
    candidates_tested: int = 0
    success: bool = False
    found_password: str | None = None


@dataclass
class StageRecoveryResult:
    """Overall result of the progressive 3-stage recovery execution."""
    success: bool
    found_password: str | None
    successful_stage: int | None
    total_attempts: int
    stage_stats: dict[int, StageStats] = field(default_factory=dict)
    stages_executed: list[int] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# Stage Generators & Streamers
# ──────────────────────────────────────────────────────────────────────────────


def get_stage_candidates(
    stage_id: int,
    hints: HintModel,
    seen: set[str] | None = None,
) -> Iterator[str]:
    """
    Generate and rank candidates for a single specified stage.

    Parameters
    ----------
    stage_id:
        Stage identifier (1, 2, or 3).
    hints:
        Validated HintModel instance.
    seen:
        Optional shared set for global deduplication across stages.

    Returns
    -------
    Iterator[str]
        Deterministic ranked stream of candidates for the given stage.
    """
    if seen is None:
        seen = set()

    if stage_id == STAGE_1_ID:
        raw_stream = generate_stage1_candidates(hints, seen=seen)
        return rank_candidates(raw_stream, hints, stage=STAGE_1_ID)
    elif stage_id == STAGE_2_ID:
        raw_stream = generate_stage2_candidates(hints, seen=seen)
        return rank_candidates(raw_stream, hints, stage=STAGE_2_ID)
    elif stage_id == STAGE_3_ID:
        raw_stream = generate_stage3_candidates(hints, seen=seen)
        return rank_candidates(raw_stream, hints, stage=STAGE_3_ID)
    else:
        raise ValueError(f"Unknown stage ID: {stage_id}. Expected 1, 2, or 3.")


def stream_progressive_stages(
    hints: HintModel,
) -> Iterator[tuple[int, str]]:
    """
    Stream ranked candidates across all 3 stages progressively.

    Yields pairs of `(stage_id, candidate_password)` in sequential stage order
    with full cross-stage deduplication.

    Parameters
    ----------
    hints:
        Validated HintModel instance.

    Yields
    ------
    tuple[int, str]
        (stage_id, candidate)
    """
    if not hints.has_any_hints:
        return

    seen: set[str] = set()

    for stage_id in ALL_STAGES:
        for candidate in get_stage_candidates(stage_id, hints, seen=seen):
            yield stage_id, candidate


# ──────────────────────────────────────────────────────────────────────────────
# Stage Execution Engine
# ──────────────────────────────────────────────────────────────────────────────


def execute_progressive_recovery(
    target_file: Path | str,
    hints: HintModel,
    verify_fn: Callable[[Path | str, str], bool] = verify,
    attempt_logger: AttemptLogger | None = None,
    progress_ui: HintProgressUI | None = None,
    seen: set[str] | None = None,
    on_stage_start: Callable[[int, str], None] | None = None,
    on_candidate_tested: Callable[[str, int, int, bool], None] | None = None,
    on_stage_end: Callable[[int, str, int, bool], None] | None = None,
    round_logger: RoundHistoryLogger | None = None,
) -> StageRecoveryResult:
    """
    Execute the 3 progressive recovery stages sequentially against `target_file`.

    Protocol:
    1. Stage 1 executes first.
    2. If Stage 1 candidate matches -> stop immediately.
    3. If Stage 1 is exhausted -> proceed to Stage 2.
    4. If Stage 2 candidate matches -> stop immediately.
    5. If Stage 2 is exhausted -> proceed to Stage 3.
    6. If Stage 3 candidate matches -> stop immediately.
    7. If Stage 3 is exhausted -> return failure result.

    Parameters
    ----------
    target_file:
        Path to the locked file being recovered.
    hints:
        The user-provided HintModel.
    verify_fn:
        Verification function (defaults to `modules.verifier.verify`).
    attempt_logger:
        Optional AttemptLogger session instance for logging tested candidates.
    progress_ui:
        Optional HintProgressUI instance for live progress and ETA updates.
    seen:
        Optional set of already tested candidates to avoid retesting across rounds.
    on_stage_start:
        Optional callback called when a stage begins: `(stage_id, stage_name)`.
    on_candidate_tested:
        Optional callback called after testing each candidate:
        `(candidate, stage_id, cumulative_attempt_number, is_match)`.
    on_stage_end:
        Optional callback called when a stage completes:
        `(stage_id, stage_name, candidates_tested_in_stage, success)`.
    round_logger:
        Optional RoundHistoryLogger instance for recording round-specific history.

    Returns
    -------
    StageRecoveryResult
        Structured execution result including success status, recovered password,
        successful stage, total attempts, and per-stage stats.
    """
    if not hints.has_any_hints:
        if progress_ui is not None:
            progress_ui.finish(success=False, tested=0)
        return StageRecoveryResult(
            success=False,
            found_password=None,
            successful_stage=None,
            total_attempts=0,
            stage_stats={},
            stages_executed=[],
        )

    if seen is None:
        seen = set()
    total_attempts = 0
    stage_stats: dict[int, StageStats] = {}
    stages_executed: list[int] = []

    for stage_id in ALL_STAGES:
        stage_name = STAGE_NAMES[stage_id]
        stages_executed.append(stage_id)
        current_stats = StageStats(stage_id=stage_id, stage_name=stage_name)
        stage_stats[stage_id] = current_stats

        if on_stage_start is not None:
            on_stage_start(stage_id, stage_name)

        stage_candidates = get_stage_candidates(stage_id, hints, seen=seen)

        for cand in stage_candidates:
            total_attempts += 1
            current_stats.candidates_tested += 1

            if attempt_logger is not None:
                attempt_logger.log_attempt(cand)

            if round_logger is not None:
                round_logger.log_attempt(cand)

            if progress_ui is not None:
                progress_ui.update(tested=total_attempts)

            is_match = False
            try:
                is_match = verify_fn(target_file, cand)
            except NotImplementedError:
                # Handle stub verifiers gracefully
                is_match = False

            if on_candidate_tested is not None:
                on_candidate_tested(cand, stage_id, total_attempts, is_match)

            if is_match:
                current_stats.success = True
                current_stats.found_password = cand

                if progress_ui is not None:
                    progress_ui.finish(success=True, tested=total_attempts)

                if on_stage_end is not None:
                    on_stage_end(stage_id, stage_name, current_stats.candidates_tested, True)

                return StageRecoveryResult(
                    success=True,
                    found_password=cand,
                    successful_stage=stage_id,
                    total_attempts=total_attempts,
                    stage_stats=stage_stats,
                    stages_executed=stages_executed,
                )

        # Stage exhausted without match
        if on_stage_end is not None:
            on_stage_end(stage_id, stage_name, current_stats.candidates_tested, False)

    # All 3 stages exhausted
    if progress_ui is not None:
        progress_ui.finish(success=False, tested=total_attempts)

    return StageRecoveryResult(
        success=False,
        found_password=None,
        successful_stage=None,
        total_attempts=total_attempts,
        stage_stats=stage_stats,
        stages_executed=stages_executed,
    )
