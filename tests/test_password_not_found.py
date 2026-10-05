"""
test_password_not_found.py
Automated test suite for password-not-found handling and search exhaustion in Version 2.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import pytest
from rich.console import Console

from modules.attempt_logger import AttemptLogger
from modules.hint_collector import HintModel
from modules.recovery_summary import (
    EXHAUSTION_MESSAGE,
    format_recovery_summary,
    display_recovery_summary,
)
from modules.search_space import calculate_search_space
from modules.search_stages import (
    StageRecoveryResult,
    StageStats,
    execute_progressive_recovery,
)
from modules.verifier import VerificationError


# ──────────────────────────────────────────────────────────────────────────────
# 1. Exact Exhaustion Message & Stage Flow Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_exact_exhaustion_message_constant():
    """Verify exact wording of the exhaustion message."""
    assert EXHAUSTION_MESSAGE == "Password not found using the provided hints and configured rules."


def test_complete_three_stage_exhaustion_summary():
    """Full 3-stage exhaustion reports not-found with exact attempt counts."""
    hints = HintModel(name=["Alice"], number=["123"])
    search_space = calculate_search_space(hints)

    tested: list[str] = []

    def mock_verify(target_file, cand):
        tested.append(cand)
        return False  # No candidate matches

    res = execute_progressive_recovery(
        target_file="test.docx",
        hints=hints,
        verify_fn=mock_verify,
    )

    assert res.success is False
    assert res.found_password is None
    assert res.successful_stage is None
    assert res.stages_executed == [1, 2, 3]
    assert res.total_attempts == len(tested)
    assert res.total_attempts == (
        res.stage_stats[1].candidates_tested
        + res.stage_stats[2].candidates_tested
        + res.stage_stats[3].candidates_tested
    )

    summary = format_recovery_summary(res, search_space=search_space, attempts_file="results/attempts_test.txt")
    assert "PASSWORD NOT FOUND" in summary
    assert "PASSWORD FOUND" not in summary
    assert EXHAUSTION_MESSAGE in summary
    assert f"Attempts: {res.total_attempts:,}" in summary
    assert f"Stage 1 Attempts: {res.stage_stats[1].candidates_tested:,}" in summary
    assert f"Stage 2 Attempts: {res.stage_stats[2].candidates_tested:,}" in summary
    assert f"Stage 3 Attempts: {res.stage_stats[3].candidates_tested:,}" in summary


def test_failure_is_not_reported_early_after_stage1_or_stage2():
    """Execution does not stop with failure after Stage 1 or 2; it progresses until Stage 3."""
    hints = HintModel(name=["Bob"], number=["999"])
    stages_executed: list[int] = []

    def on_stage_start(stage_id: int, stage_name: str):
        stages_executed.append(stage_id)

    res = execute_progressive_recovery(
        target_file="test.pdf",
        hints=hints,
        verify_fn=lambda f, p: False,
        on_stage_start=on_stage_start,
    )

    assert stages_executed == [1, 2, 3]
    assert res.stages_executed == [1, 2, 3]
    assert res.success is False


# ──────────────────────────────────────────────────────────────────────────────
# 2. Success Prevents Password-Not-Found
# ──────────────────────────────────────────────────────────────────────────────


def test_stage1_success_prevents_not_found():
    """Stage 1 success shows PASSWORD FOUND and never shows not-found message."""
    hints = HintModel(name=["Alice"])
    res = execute_progressive_recovery(
        target_file="test.zip",
        hints=hints,
        verify_fn=lambda f, p: p == "Alice",
    )
    assert res.success is True
    summary = format_recovery_summary(res, attempts_file="results/attempts.txt")
    assert "PASSWORD FOUND" in summary
    assert EXHAUSTION_MESSAGE not in summary


def test_stage2_success_prevents_not_found():
    """Stage 2 success shows PASSWORD FOUND and never shows not-found message."""
    hints = HintModel(name=["Alice"], number=["10"])
    # "alice10" is in Stage 2 (casing transformation)
    res = execute_progressive_recovery(
        target_file="test.zip",
        hints=hints,
        verify_fn=lambda f, p: p == "alice10",
    )
    assert res.success is True
    assert res.successful_stage == 2
    summary = format_recovery_summary(res, attempts_file="results/attempts.txt")
    assert "PASSWORD FOUND" in summary
    assert EXHAUSTION_MESSAGE not in summary


def test_stage3_success_prevents_not_found():
    """Stage 3 success shows PASSWORD FOUND and never shows not-found message."""
    hints = HintModel(name=["Alice", "Bob"])
    # "AliceBob" is in Stage 3 (compound base pairing)
    res = execute_progressive_recovery(
        target_file="test.zip",
        hints=hints,
        verify_fn=lambda f, p: p == "AliceBob",
    )
    assert res.success is True
    assert res.successful_stage == 3
    summary = format_recovery_summary(res, attempts_file="results/attempts.txt")
    assert "PASSWORD FOUND" in summary
    assert EXHAUSTION_MESSAGE not in summary


# ──────────────────────────────────────────────────────────────────────────────
# 3. Zero-Candidate Edge Case Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_zero_candidates_produces_not_found_with_zero_attempts():
    """When hint constraints yield zero candidates, not-found is reported with 0 attempts."""
    # min_length of 50 exceeds any candidate generated
    hints = HintModel(name=["Alice"], min_length=50, max_length=60)
    search_space = calculate_search_space(hints)

    res = execute_progressive_recovery(
        target_file="test.xlsx",
        hints=hints,
        verify_fn=lambda f, p: False,
    )

    assert res.success is False
    assert res.total_attempts == 0

    summary = format_recovery_summary(res, search_space=search_space, attempts_file="results/attempts.txt")
    assert "PASSWORD NOT FOUND" in summary
    assert EXHAUSTION_MESSAGE in summary
    assert "Attempts: 0" in summary
    assert "Stage 1 Attempts: 0" in summary
    assert "Stage 2 Attempts: 0" in summary
    assert "Stage 3 Attempts: 0" in summary


# ──────────────────────────────────────────────────────────────────────────────
# 4. Exception Handling vs. Exhaustion Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_exception_in_stage1_does_not_report_password_not_found(tmp_path):
    """An unhandled VerificationError in Stage 1 raises and does not display not-found."""
    hints = HintModel(name=["Alice"])

    def failing_verify(target_file, cand):
        raise VerificationError("Corrupt header encountered in Stage 1")

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_130000") as logger:
        with pytest.raises(VerificationError, match="Corrupt header"):
            execute_progressive_recovery(
                target_file="corrupt.zip",
                hints=hints,
                verify_fn=failing_verify,
                attempt_logger=logger,
            )

    # Attempts logger preserved the 1 attempt that triggered the error
    logged = logger.file_path.read_text(encoding="utf-8").splitlines()
    assert len(logged) == 1


def test_exception_in_stage2_does_not_report_password_not_found(tmp_path):
    """An unhandled VerificationError in Stage 2 raises and does not display not-found."""
    hints = HintModel(name=["Alice"], number=["10"])
    call_count = 0

    def failing_verify_stage2(target_file, cand):
        nonlocal call_count
        call_count += 1
        # Fail after Stage 1 finishes (e.g. candidate #10 in Stage 2)
        if cand == "alice10":
            raise VerificationError("I/O error during Stage 2 verification")
        return False

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_130100") as logger:
        with pytest.raises(VerificationError, match="I/O error during Stage 2"):
            execute_progressive_recovery(
                target_file="test.docx",
                hints=hints,
                verify_fn=failing_verify_stage2,
                attempt_logger=logger,
            )

    logged = logger.file_path.read_text(encoding="utf-8").splitlines()
    assert len(logged) == call_count
    assert "alice10" in logged


def test_exception_in_stage3_does_not_report_password_not_found(tmp_path):
    """An unhandled VerificationError in Stage 3 raises and does not display not-found."""
    hints = HintModel(name=["Alice", "Bob"])

    def failing_verify_stage3(target_file, cand):
        if cand == "AliceBob":
            raise VerificationError("Disk error during Stage 3")
        return False

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_130200") as logger:
        with pytest.raises(VerificationError, match="Disk error during Stage 3"):
            execute_progressive_recovery(
                target_file="test.pdf",
                hints=hints,
                verify_fn=failing_verify_stage3,
                attempt_logger=logger,
            )


# ──────────────────────────────────────────────────────────────────────────────
# 5. Attempts File Preservation & Non-Creation of Extra Files
# ──────────────────────────────────────────────────────────────────────────────


def test_attempts_file_preserved_after_exhaustion(tmp_path):
    """The single session attempts file remains intact and accurate after search exhaustion."""
    hints = HintModel(name=["Alice"], number=["1"])

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_130300") as logger:
        res = execute_progressive_recovery(
            target_file="test.zip",
            hints=hints,
            verify_fn=lambda f, p: False,
            attempt_logger=logger,
        )

    # Exactly 1 file in results directory
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    assert files[0] == logger.file_path

    # File contains every single tested candidate
    lines = logger.file_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == res.total_attempts


def test_display_summary_rendering_does_not_throw(tmp_path):
    """display_recovery_summary renders exhaustion to console cleanly."""
    console = Console(record=True, width=80)
    res = StageRecoveryResult(
        success=False,
        found_password=None,
        successful_stage=None,
        total_attempts=0,
        stage_stats={},
        stages_executed=[1, 2, 3],
    )
    display_recovery_summary(res, search_space=None, attempts_file=tmp_path / "attempts.txt", console=console)
    output = console.export_text()
    assert EXHAUSTION_MESSAGE in output
