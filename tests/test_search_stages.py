"""
test_search_stages.py
Automated test suite for progressive 3-stage password recovery in Version 2.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator
import pytest

from modules.hint_collector import HintModel
from modules.candidate_generator import generate_stage1_candidates, generate_stage2_candidates, generate_stage3_candidates
from modules.candidate_ranker import rank_candidates
from modules.search_stages import (
    STAGE_1_ID,
    STAGE_1_NAME,
    STAGE_2_ID,
    STAGE_2_NAME,
    STAGE_3_ID,
    STAGE_3_NAME,
    STAGE_NAMES,
    ALL_STAGES,
    StageStats,
    StageRecoveryResult,
    get_stage_candidates,
    stream_progressive_stages,
    execute_progressive_recovery,
)


# ──────────────────────────────────────────────────────────────────────────────
# 1. Stage Sequencing & Ordering Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_stage_constants_and_names():
    """Verify stage IDs and canonical names match specifications."""
    assert STAGE_1_ID == 1
    assert STAGE_2_ID == 2
    assert STAGE_3_ID == 3
    assert ALL_STAGES == (1, 2, 3)
    assert STAGE_NAMES[1] == "Stage 1 — Direct Hint Search"
    assert STAGE_NAMES[2] == "Stage 2 — Hint Transformation Search"
    assert STAGE_NAMES[3] == "Stage 3 — Expanded Hint Search"


def test_stream_progressive_stages_strict_ordering():
    """Stage 1 candidates must precede Stage 2, and Stage 2 must precede Stage 3."""
    hints = HintModel(
        name=["Saniya"],
        number=["7070"],
        special_character=["@"],
    )

    stage_order: list[int] = []
    candidates_by_stage: dict[int, list[str]] = {1: [], 2: [], 3: []}

    for stage_id, cand in stream_progressive_stages(hints):
        if not stage_order or stage_order[-1] != stage_id:
            stage_order.append(stage_id)
        candidates_by_stage[stage_id].append(cand)

    assert stage_order == [1, 2, 3]
    assert len(candidates_by_stage[1]) > 0
    assert len(candidates_by_stage[2]) > 0
    assert len(candidates_by_stage[3]) > 0


def test_stage2_does_not_start_while_stage1_has_candidates():
    """Stage 2 must only commence after Stage 1 candidate generator is fully exhausted."""
    hints = HintModel(name=["Alice"], number=["123"])
    events: list[str] = []

    def on_stage_start(stage_id: int, stage_name: str):
        events.append(f"start_{stage_id}")

    def on_stage_end(stage_id: int, stage_name: str, count: int, success: bool):
        events.append(f"end_{stage_id}")

    def mock_verify(target_file, cand):
        return False

    res = execute_progressive_recovery(
        target_file="test.zip",
        hints=hints,
        verify_fn=mock_verify,
        on_stage_start=on_stage_start,
        on_stage_end=on_stage_end,
    )

    assert not res.success
    # Strict lifecycle: start_1 -> end_1 -> start_2 -> end_2 -> start_3 -> end_3
    assert events == ["start_1", "end_1", "start_2", "end_2", "start_3", "end_3"]


# ──────────────────────────────────────────────────────────────────────────────
# 2. Early Success Termination Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_stage1_success_stops_immediately():
    """If a candidate succeeds in Stage 1, Stage 2 and Stage 3 must never execute."""
    hints = HintModel(
        name=["Saniya"],
        number=["7070"],
        special_character=["@"],
    )
    # Pick a candidate known to be in Stage 1
    target = "Saniya7070@"
    tested_candidates: list[str] = []
    stages_started: list[int] = []

    def mock_verify(target_file, cand):
        tested_candidates.append(cand)
        return cand == target

    result = execute_progressive_recovery(
        target_file="dummy.zip",
        hints=hints,
        verify_fn=mock_verify,
        on_stage_start=lambda sid, name: stages_started.append(sid),
    )

    assert result.success is True
    assert result.found_password == target
    assert result.successful_stage == 1
    assert result.stages_executed == [1]
    assert stages_started == [1]
    assert tested_candidates[-1] == target
    assert result.total_attempts == len(tested_candidates)


def test_stage2_success_stops_immediately():
    """If a candidate succeeds in Stage 2, Stage 3 must never execute."""
    hints = HintModel(
        name=["Saniya"],
        number=["7070"],
    )
    # Pick a candidate known to be in Stage 2 (casing transformation 'saniya7070' if Saniya was input)
    # Saniya is title case in hint, so saniya is a Stage 2 lowercase transformation
    target = "saniya7070"
    tested_candidates: list[str] = []
    stages_started: list[int] = []

    def mock_verify(target_file, cand):
        tested_candidates.append(cand)
        return cand == target

    result = execute_progressive_recovery(
        target_file="dummy.docx",
        hints=hints,
        verify_fn=mock_verify,
        on_stage_start=lambda sid, name: stages_started.append(sid),
    )

    assert result.success is True
    assert result.found_password == target
    assert result.successful_stage == 2
    assert result.stages_executed == [1, 2]
    assert stages_started == [1, 2]
    assert tested_candidates[-1] == target
    assert 3 not in result.stage_stats


def test_stage3_success_stops_immediately():
    """If a candidate succeeds in Stage 3, execution completes successfully without overrun."""
    hints = HintModel(
        name=["Saniya", "Sakshi"],
        number=["7070"],
    )
    # Compound base pairing 'SaniyaSakshi7070' is in Stage 3
    target = "SaniyaSakshi7070"
    tested_candidates: list[str] = []
    stages_started: list[int] = []

    def mock_verify(target_file, cand):
        tested_candidates.append(cand)
        return cand == target

    result = execute_progressive_recovery(
        target_file="dummy.pdf",
        hints=hints,
        verify_fn=mock_verify,
        on_stage_start=lambda sid, name: stages_started.append(sid),
    )

    assert result.success is True
    assert result.found_password == target
    assert result.successful_stage == 3
    assert result.stages_executed == [1, 2, 3]
    assert stages_started == [1, 2, 3]
    assert tested_candidates[-1] == target


# ──────────────────────────────────────────────────────────────────────────────
# 3. Global Deduplication Across Stages
# ──────────────────────────────────────────────────────────────────────────────


def test_global_deduplication_across_stages():
    """A candidate generated in Stage 1 must never be re-tested in Stage 2 or Stage 3."""
    hints = HintModel(
        name=["Saniya"],
        number=["7070"],
        special_character=["@"],
    )

    seen_globally: list[str] = []

    def mock_verify(target_file, cand):
        seen_globally.append(cand)
        return False

    res = execute_progressive_recovery(
        target_file="dummy.xlsx",
        hints=hints,
        verify_fn=mock_verify,
    )

    assert not res.success
    assert len(seen_globally) == len(set(seen_globally)), "Zero duplicate candidates across all stages"


# ──────────────────────────────────────────────────────────────────────────────
# 4. Lazy / Progressive Generation Guarantees
# ──────────────────────────────────────────────────────────────────────────────


def test_lazy_generation_does_not_evaluate_unused_candidates():
    """Verifier success on the 1st candidate stops generator immediately."""
    hints = HintModel(
        name=["Alice"],
        number=["123", "456", "789"],
        special_character=["!", "@", "#"],
    )

    tested: list[str] = []

    def mock_verify(target_file, cand):
        tested.append(cand)
        return True  # Match immediately on the first candidate tested

    res = execute_progressive_recovery(
        target_file="dummy.zip",
        hints=hints,
        verify_fn=mock_verify,
    )

    assert res.success is True
    assert res.total_attempts == 1
    assert len(tested) == 1
    assert res.successful_stage == 1
    assert res.stages_executed == [1]


# ──────────────────────────────────────────────────────────────────────────────
# 5. Empty Hints & Failure Edge Cases
# ──────────────────────────────────────────────────────────────────────────────


def test_execute_progressive_recovery_empty_hints():
    """Empty hint model returns failure with 0 attempts and empty stages."""
    hints = HintModel()
    res = execute_progressive_recovery(
        target_file="dummy.zip",
        hints=hints,
        verify_fn=lambda f, p: True,
    )
    assert res.success is False
    assert res.found_password is None
    assert res.total_attempts == 0
    assert res.stages_executed == []


def test_get_stage_candidates_invalid_stage_id():
    """Invalid stage ID raises ValueError."""
    hints = HintModel(name=["Alice"])
    with pytest.raises(ValueError, match="Unknown stage ID: 99"):
        get_stage_candidates(99, hints)


# ──────────────────────────────────────────────────────────────────────────────
# 6. Safety & Side-Effect Verifications
# ──────────────────────────────────────────────────────────────────────────────


def test_no_disk_files_created(tmp_path):
    """Running progressive recovery creates no attempt log or session files."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    hints = HintModel(name=["Alice"], number=["123"])
    execute_progressive_recovery(
        target_file="test.zip",
        hints=hints,
        verify_fn=lambda f, p: False,
    )

    assert list(results_dir.iterdir()) == []


def test_candidate_tested_callback_parameters():
    """on_candidate_tested callback receives expected arguments."""
    hints = HintModel(name=["Alice"])
    calls: list[tuple[str, int, int, bool]] = []

    def on_cand(cand: str, stage_id: int, attempt: int, is_match: bool):
        calls.append((cand, stage_id, attempt, is_match))

    res = execute_progressive_recovery(
        target_file="test.zip",
        hints=hints,
        verify_fn=lambda f, p: p == "Alice",
        on_candidate_tested=on_cand,
    )

    assert res.success is True
    assert len(calls) > 0
    last_call = calls[-1]
    assert last_call[0] == "Alice"
    assert last_call[1] == 1
    assert last_call[3] is True
