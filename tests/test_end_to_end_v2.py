"""
test_end_to_end_v2.py
End-to-End and Integration tests for Version 2 hint-based password recovery.

Tests the full recovery pipeline from HintModel through search-space calculation,
candidate generation, ranking, 3-stage progressive execution, attempt logging,
verifier invocation, and final recovery summary.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch
import pytest
from rich.console import Console

from main import _recover_with_hints, _recover_with_password_list
from modules.attempt_logger import AttemptLogger
from modules.candidate_loader import load_candidates
from modules.candidate_generator import generate_candidates
from modules.candidate_ranker import rank_progressive_candidates
from modules.file_detector import DetectedFile
from modules.hint_collector import HintModel
from modules.recovery_summary import EXHAUSTION_MESSAGE, format_recovery_summary, display_recovery_summary
from modules.search_space import calculate_search_space
from modules.search_stages import execute_progressive_recovery
from modules.verifier import VerificationError, verify


# ──────────────────────────────────────────────────────────────────────────────
# 1. End-to-End Scenarios 1–3: Success in Each Stage
# ──────────────────────────────────────────────────────────────────────────────


def test_e2e_scenario1_stage1_success(tmp_path):
    """Scenario 1: Password found in Stage 1 terminates immediately with correct stats and log."""
    hints = HintModel(
        name=["Saniya"],
        number=["7070"],
        special_character=["@"],
    )
    search_space = calculate_search_space(hints)
    winning_password = "Saniya7070@"  # Stage 1 canonical triplet

    tested_calls: list[str] = []

    def mock_verifier(target_file, cand):
        tested_calls.append(cand)
        return cand == winning_password

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_160100") as logger:
        result = execute_progressive_recovery(
            target_file="test_doc.docx",
            hints=hints,
            verify_fn=mock_verifier,
            attempt_logger=logger,
        )

    assert result.success is True
    assert result.found_password == winning_password
    assert result.successful_stage == 1
    assert result.stages_executed == [1]
    assert result.total_attempts == len(tested_calls)

    # Attempts file integrity
    logged_attempts = logger.file_path.read_text(encoding="utf-8").splitlines()
    assert len(logged_attempts) == result.total_attempts
    assert logged_attempts[-1] == winning_password

    # Summary verification
    summary = format_recovery_summary(result, search_space=search_space, attempts_file=logger.file_path)
    assert "PASSWORD FOUND" in summary
    assert f"Password: {winning_password}" in summary
    assert "Stage: Stage 1 — Direct Hint Search" in summary
    assert EXHAUSTION_MESSAGE not in summary


def test_e2e_scenario2_stage2_success(tmp_path):
    """Scenario 2: Password found in Stage 2 executes Stage 1 completely, stops mid Stage 2."""
    hints = HintModel(
        name=["Saniya"],
        number=["7070"],
    )
    search_space = calculate_search_space(hints)
    winning_password = "saniya7070"  # Stage 2 lowercase variation

    tested_calls: list[str] = []

    def mock_verifier(target_file, cand):
        tested_calls.append(cand)
        return cand == winning_password

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_160200") as logger:
        result = execute_progressive_recovery(
            target_file="test_doc.docx",
            hints=hints,
            verify_fn=mock_verifier,
            attempt_logger=logger,
        )

    assert result.success is True
    assert result.found_password == winning_password
    assert result.successful_stage == 2
    assert result.stages_executed == [1, 2]
    assert 3 not in result.stage_stats

    logged_attempts = logger.file_path.read_text(encoding="utf-8").splitlines()
    assert logged_attempts[-1] == winning_password
    assert len(logged_attempts) == result.total_attempts

    summary = format_recovery_summary(result, search_space=search_space, attempts_file=logger.file_path)
    assert "PASSWORD FOUND" in summary
    assert "Stage: Stage 2 — Hint Transformation Search" in summary
    assert f"Stage 1 Attempts: {result.stage_stats[1].candidates_tested}" in summary
    assert f"Stage 2 Attempts: {result.stage_stats[2].candidates_tested}" in summary
    assert "Stage 3 Attempts: 0" in summary


def test_e2e_scenario3_stage3_success(tmp_path):
    """Scenario 3: Password found in Stage 3 executes Stage 1 & 2 fully, stops mid Stage 3."""
    hints = HintModel(
        name=["Saniya", "Sakshi"],
        number=["7070"],
    )
    search_space = calculate_search_space(hints)
    winning_password = "SaniyaSakshi7070"  # Stage 3 compound pairing

    tested_calls: list[str] = []

    def mock_verifier(target_file, cand):
        tested_calls.append(cand)
        return cand == winning_password

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_160300") as logger:
        result = execute_progressive_recovery(
            target_file="test_doc.pdf",
            hints=hints,
            verify_fn=mock_verifier,
            attempt_logger=logger,
        )

    assert result.success is True
    assert result.found_password == winning_password
    assert result.successful_stage == 3
    assert result.stages_executed == [1, 2, 3]

    logged_attempts = logger.file_path.read_text(encoding="utf-8").splitlines()
    assert logged_attempts[-1] == winning_password
    assert len(logged_attempts) == result.total_attempts

    summary = format_recovery_summary(result, search_space=search_space, attempts_file=logger.file_path)
    assert "PASSWORD FOUND" in summary
    assert "Stage: Stage 3 — Expanded Hint Search" in summary
    assert f"Stage 1 Attempts: {result.stage_stats[1].candidates_tested}" in summary
    assert f"Stage 2 Attempts: {result.stage_stats[2].candidates_tested}" in summary
    assert f"Stage 3 Attempts: {result.stage_stats[3].candidates_tested}" in summary


# ──────────────────────────────────────────────────────────────────────────────
# 2. End-to-End Scenarios 4–7: Exhaustion, Zero Candidates, Constraints
# ──────────────────────────────────────────────────────────────────────────────


def test_e2e_scenario4_complete_exhaustion(tmp_path):
    """Scenario 4: Password not found after all 3 stages displays exact not-found summary."""
    hints = HintModel(name=["Alice"], number=["123"])
    search_space = calculate_search_space(hints)

    tested_calls: list[str] = []

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_160400") as logger:
        result = execute_progressive_recovery(
            target_file="test.zip",
            hints=hints,
            verify_fn=lambda f, p: tested_calls.append(p) or False,
            attempt_logger=logger,
        )

    assert result.success is False
    assert result.found_password is None
    assert result.stages_executed == [1, 2, 3]
    assert result.total_attempts == len(tested_calls)

    logged_attempts = logger.file_path.read_text(encoding="utf-8").splitlines()
    assert logged_attempts == tested_calls

    summary = format_recovery_summary(result, search_space=search_space, attempts_file=logger.file_path)
    assert "PASSWORD NOT FOUND" in summary
    assert EXHAUSTION_MESSAGE in summary
    assert f"Attempts: {result.total_attempts:,}" in summary


def test_e2e_scenario5_zero_candidates(tmp_path):
    """Scenario 5: Search space with zero valid candidates reports not-found with 0 attempts."""
    hints = HintModel(name=["Alice"], min_length=99, max_length=100)
    search_space = calculate_search_space(hints)
    assert search_space.total_distinct_count == 0

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_160500") as logger:
        result = execute_progressive_recovery(
            target_file="test.zip",
            hints=hints,
            verify_fn=lambda f, p: True,
            attempt_logger=logger,
        )

    assert result.success is False
    assert result.total_attempts == 0
    logged_attempts = logger.file_path.read_text(encoding="utf-8").splitlines()
    assert logged_attempts == []

    summary = format_recovery_summary(result, search_space=search_space, attempts_file=logger.file_path)
    assert EXHAUSTION_MESSAGE in summary
    assert "Attempts: 0" in summary


def test_e2e_scenario6_multi_value_hints_flow(tmp_path):
    """Scenario 6: Multi-value hints across fields generate and test complete combinations."""
    hints = HintModel(
        name=["Alice", "Bob"],
        number=["100", "200"],
        special_character=["!", "#"],
    )
    search_space = calculate_search_space(hints)

    tested_calls: list[str] = []
    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_160600") as logger:
        result = execute_progressive_recovery(
            target_file="test.7z",
            hints=hints,
            verify_fn=lambda f, p: tested_calls.append(p) or False,
            attempt_logger=logger,
        )

    assert result.success is False
    assert result.total_attempts == search_space.total_distinct_count
    assert len(tested_calls) == len(set(tested_calls)), "No duplicate candidate tested"


def test_e2e_scenario7_length_constraints_eliminate_candidates(tmp_path):
    """Scenario 7: Length boundaries filter out candidates outside range."""
    hints = HintModel(
        name=["Saniya"],
        number=["7070"],
        special_character=["@"],
        min_length=11,
        max_length=12,
    )
    search_space = calculate_search_space(hints)

    tested_calls: list[str] = []
    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_160700") as logger:
        execute_progressive_recovery(
            target_file="test.zip",
            hints=hints,
            verify_fn=lambda f, p: tested_calls.append(p) or False,
            attempt_logger=logger,
        )

    for cand in tested_calls:
        assert 11 <= len(cand) <= 12, f"Candidate '{cand}' violated length bounds"


# ──────────────────────────────────────────────────────────────────────────────
# 3. End-to-End Scenarios 8–12: Invariants, Errors & Version 1 Isolation
# ──────────────────────────────────────────────────────────────────────────────


def test_e2e_scenario8_cross_stage_duplicates_tested_only_once(tmp_path):
    """Scenario 8: Candidates possible in multiple stages are tested strictly once."""
    hints = HintModel(name=["Alice"], number=["123"])
    all_tested: list[str] = []

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_160800") as logger:
        execute_progressive_recovery(
            target_file="test.docx",
            hints=hints,
            verify_fn=lambda f, p: all_tested.append(p) or False,
            attempt_logger=logger,
        )

    assert len(all_tested) == len(set(all_tested))


def test_e2e_scenario9_and_10_no_testing_after_success(tmp_path):
    """Scenarios 9 & 10: Successful candidate is logged once and stops all further testing."""
    hints = HintModel(name=["Alice"], number=["123", "456", "789"])
    winning = "Alice123"

    calls_after_success = 0
    found = False

    def mock_verifier(target_file, cand):
        nonlocal calls_after_success, found
        if found:
            calls_after_success += 1
        if cand == winning:
            found = True
            return True
        return False

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_160900") as logger:
        result = execute_progressive_recovery(
            target_file="test.xlsx",
            hints=hints,
            verify_fn=mock_verifier,
            attempt_logger=logger,
        )

    assert result.success is True
    assert calls_after_success == 0, "Verifier was called after success!"
    logged = logger.file_path.read_text(encoding="utf-8").splitlines()
    assert logged.count(winning) == 1
    assert logged[-1] == winning


def test_e2e_scenario11_verification_error_is_not_treated_as_not_found(tmp_path):
    """Scenario 11: Unrecoverable verification error raises exception without reporting not-found."""
    hints = HintModel(name=["Alice"])

    def broken_verifier(target_file, cand):
        raise VerificationError("File header is severely corrupt")

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_161100") as logger:
        with pytest.raises(VerificationError, match="File header is severely corrupt"):
            execute_progressive_recovery(
                target_file="corrupt.docx",
                hints=hints,
                verify_fn=broken_verifier,
                attempt_logger=logger,
            )

    # Attempts logged prior to failure are safely persisted
    logged = logger.file_path.read_text(encoding="utf-8").splitlines()
    assert len(logged) == 1


def test_e2e_scenario12_v1_password_list_mode_independence(tmp_path):
    """Scenario 12: Version 1 manual password-list workflow works completely independently."""
    list_file = tmp_path / "custom_candidates.txt"
    list_file.write_text("# header comment\nAlpha123\nBeta456\n# trailing\n", encoding="utf-8")

    cands, stats = load_candidates(list_file)
    assert cands == ["Alpha123", "Beta456"]
    assert stats.total_usable == 2
    assert stats.comment_lines == 2


# ──────────────────────────────────────────────────────────────────────────────
# 4. Search-Space / Generator Consistency & Determinism
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "hints",
    [
        HintModel(name=["Alice"]),
        HintModel(word=["Secret"]),
        HintModel(number=["2024"]),
        HintModel(name=["Alice"], number=["123"]),
        HintModel(name=["Alice"], special_character=["@"]),
        HintModel(name=["Alice"], prefix=["#"]),
        HintModel(name=["Alice"], suffix=["!"]),
        HintModel(name=["Alice", "Bob"], number=["1", "2"]),
        HintModel(name=["Alice"], number=["123"], special_character=["@"], prefix=["#"], suffix=["!"]),
        HintModel(name=["Alice"], min_length=5, max_length=10),
    ],
)
def test_search_space_generator_and_ranker_mathematical_identity(hints: HintModel):
    """Verify search_space count == generator universe count == ranked candidate count."""
    analysis = calculate_search_space(hints)
    generated_list = list(generate_candidates(hints))
    ranked_list = list(rank_progressive_candidates(hints))

    assert analysis.total_distinct_count == len(generated_list), (
        f"Search space count ({analysis.total_distinct_count}) != generated count ({len(generated_list)})"
    )
    assert set(generated_list) == set(ranked_list), "Universe of ranked candidates differed from generator"
    assert len(ranked_list) == len(set(ranked_list)), "Ranked candidates had duplicates"


def test_strict_determinism_across_multiple_runs():
    """Verify identical hints produce identical search spaces, stream order, and ranking across runs."""
    hints = HintModel(
        name=["Sakshi", "Saurabh"],
        number=["123", "2024"],
        special_character=["!", "@"],
        prefix=["admin#"],
        suffix=["99$"],
    )

    space1 = calculate_search_space(hints)
    space2 = calculate_search_space(hints)
    assert space1.total_distinct_count == space2.total_distinct_count
    assert space1.stage1_count == space2.stage1_count
    assert space1.stage2_count == space2.stage2_count
    assert space1.stage3_count == space2.stage3_count

    gen1 = list(generate_candidates(hints))
    gen2 = list(generate_candidates(hints))
    assert gen1 == gen2

    rank1 = list(rank_progressive_candidates(hints))
    rank2 = list(rank_progressive_candidates(hints))
    assert rank1 == rank2
