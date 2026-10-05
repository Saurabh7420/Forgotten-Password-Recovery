"""
test_recovery_summary.py
Automated test suite for recovery summary formatting and display in Version 2.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from rich.console import Console

from modules.attempt_logger import AttemptLogger
from modules.hint_collector import HintModel
from modules.recovery_summary import (
    EXHAUSTION_MESSAGE,
    format_recovery_summary,
    display_recovery_summary,
    get_stage_attempt_counts,
)
from modules.search_space import calculate_search_space
from modules.search_stages import (
    StageStats,
    StageRecoveryResult,
    execute_progressive_recovery,
)


# ──────────────────────────────────────────────────────────────────────────────
# 1. Success Summary Tests Across Stages
# ──────────────────────────────────────────────────────────────────────────────


def test_stage1_success_summary():
    """Summary for Stage 1 success displays correct stage, password, and attempt counts."""
    result = StageRecoveryResult(
        success=True,
        found_password="Saniya7070@",
        successful_stage=1,
        total_attempts=5,
        stage_stats={
            1: StageStats(stage_id=1, stage_name="Stage 1 — Direct Hint Search", candidates_tested=5, success=True, found_password="Saniya7070@"),
        },
        stages_executed=[1],
    )
    summary = format_recovery_summary(result, attempts_file=Path("results/attempts_test.txt"))

    assert "PASSWORD FOUND" in summary
    assert "Password: Saniya7070@" in summary
    assert "Stage: Stage 1 — Direct Hint Search" in summary
    assert "Attempts File:" in summary
    assert "attempts_test.txt" in summary
    assert "Stage 1 Attempts: 5" in summary
    assert "Stage 2 Attempts: 0" in summary
    assert "Stage 3 Attempts: 0" in summary


def test_stage2_success_summary():
    """Summary for Stage 2 success displays Stage 1 complete + Stage 2 partial attempts."""
    result = StageRecoveryResult(
        success=True,
        found_password="saniya_7070",
        successful_stage=2,
        total_attempts=45,
        stage_stats={
            1: StageStats(stage_id=1, stage_name="Stage 1 — Direct Hint Search", candidates_tested=20, success=False),
            2: StageStats(stage_id=2, stage_name="Stage 2 — Hint Transformation Search", candidates_tested=25, success=True, found_password="saniya_7070"),
        },
        stages_executed=[1, 2],
    )
    summary = format_recovery_summary(result, attempts_file=Path("results/attempts_test.txt"))

    assert "PASSWORD FOUND" in summary
    assert "Password: saniya_7070" in summary
    assert "Stage: Stage 2 — Hint Transformation Search" in summary
    assert "Attempts: 45" in summary
    assert "Stage 1 Attempts: 20" in summary
    assert "Stage 2 Attempts: 25" in summary
    assert "Stage 3 Attempts: 0" in summary


def test_stage3_success_summary():
    """Summary for Stage 3 success displays Stage 1 + Stage 2 complete + Stage 3 partial."""
    result = StageRecoveryResult(
        success=True,
        found_password="SaniyaSakshi7070",
        successful_stage=3,
        total_attempts=250,
        stage_stats={
            1: StageStats(stage_id=1, stage_name="Stage 1 — Direct Hint Search", candidates_tested=20, success=False),
            2: StageStats(stage_id=2, stage_name="Stage 2 — Hint Transformation Search", candidates_tested=100, success=False),
            3: StageStats(stage_id=3, stage_name="Stage 3 — Expanded Hint Search", candidates_tested=130, success=True, found_password="SaniyaSakshi7070"),
        },
        stages_executed=[1, 2, 3],
    )
    summary = format_recovery_summary(result, attempts_file=Path("results/attempts_test.txt"))

    assert "PASSWORD FOUND" in summary
    assert "Password: SaniyaSakshi7070" in summary
    assert "Stage: Stage 3 — Expanded Hint Search" in summary
    assert "Attempts: 250" in summary
    assert "Stage 1 Attempts: 20" in summary
    assert "Stage 2 Attempts: 100" in summary
    assert "Stage 3 Attempts: 130" in summary


# ──────────────────────────────────────────────────────────────────────────────
# 2. Failure & Exhaustion Summary Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_exhaustion_summary_exact_message():
    """Exhaustion summary contains the exact required wording."""
    result = StageRecoveryResult(
        success=False,
        found_password=None,
        successful_stage=None,
        total_attempts=500,
        stage_stats={
            1: StageStats(stage_id=1, stage_name="Stage 1 — Direct Hint Search", candidates_tested=50, success=False),
            2: StageStats(stage_id=2, stage_name="Stage 2 — Hint Transformation Search", candidates_tested=200, success=False),
            3: StageStats(stage_id=3, stage_name="Stage 3 — Expanded Hint Search", candidates_tested=250, success=False),
        },
        stages_executed=[1, 2, 3],
    )
    summary = format_recovery_summary(result, attempts_file=Path("results/attempts_test.txt"))

    assert "PASSWORD NOT FOUND" in summary
    assert EXHAUSTION_MESSAGE in summary
    assert "Password not found using the provided hints and configured rules." in summary
    assert "Attempts: 500" in summary
    assert "Stage 1 Attempts: 50" in summary
    assert "Stage 2 Attempts: 200" in summary
    assert "Stage 3 Attempts: 250" in summary


def test_search_space_available_vs_actual_attempts_distinction():
    """Theoretical search space counts are clearly distinguished from actual attempts."""
    hints = HintModel(name=["Alice"], number=["123"])
    search_space = calculate_search_space(hints)

    result = StageRecoveryResult(
        success=True,
        found_password="Alice123",
        successful_stage=1,
        total_attempts=3,
        stage_stats={
            1: StageStats(stage_id=1, stage_name="Stage 1 — Direct Hint Search", candidates_tested=3, success=True, found_password="Alice123"),
        },
        stages_executed=[1],
    )

    summary = format_recovery_summary(result, search_space=search_space, attempts_file="results/attempts_test.txt")

    # Actual attempts
    assert "Attempts: 3" in summary
    assert "Stage 1 Attempts: 3" in summary
    # Configured search space
    assert "Configured Search Space:" in summary
    assert f"Stage 1 Candidates Available: {search_space.stage1_count:,}" in summary
    assert f"Total Distinct Candidates Available: {search_space.total_distinct_count:,}" in summary


# ──────────────────────────────────────────────────────────────────────────────
# 3. Integration & Rendering Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_display_recovery_summary_rich_console_rendering(tmp_path):
    """display_recovery_summary renders without exceptions on rich Console."""
    console = Console(record=True, width=80)
    result = StageRecoveryResult(
        success=True,
        found_password="TestPass123!",
        successful_stage=1,
        total_attempts=1,
        stage_stats={
            1: StageStats(stage_id=1, stage_name="Stage 1 — Direct Hint Search", candidates_tested=1, success=True, found_password="TestPass123!"),
        },
        stages_executed=[1],
    )

    display_recovery_summary(
        result=result,
        search_space=None,
        attempts_file=tmp_path / "attempts_20261005_120000.txt",
        console=console,
    )

    output = console.export_text()
    assert "Password Found" in output
    assert "TestPass123!" in output


def test_display_recovery_summary_failure_rich_console_rendering(tmp_path):
    """display_recovery_summary renders failure panel cleanly."""
    console = Console(record=True, width=80)
    result = StageRecoveryResult(
        success=False,
        found_password=None,
        successful_stage=None,
        total_attempts=10,
        stage_stats={
            1: StageStats(stage_id=1, stage_name="Stage 1 — Direct Hint Search", candidates_tested=10, success=False),
        },
        stages_executed=[1],
    )

    display_recovery_summary(
        result=result,
        search_space=None,
        attempts_file=tmp_path / "attempts_20261005_120000.txt",
        console=console,
    )

    output = console.export_text()
    assert EXHAUSTION_MESSAGE in output


def test_no_extra_files_created_by_summary(tmp_path):
    """Summary formatting and display creates zero new files on disk."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    result = StageRecoveryResult(
        success=True,
        found_password="Pass",
        successful_stage=1,
        total_attempts=1,
    )
    format_recovery_summary(result, attempts_file=results_dir / "attempts.txt")
    display_recovery_summary(result, attempts_file=results_dir / "attempts.txt")

    assert list(results_dir.iterdir()) == []


def test_get_stage_attempt_counts_helper():
    """Helper properly handles missing stage stats entries."""
    res = StageRecoveryResult(
        success=False,
        found_password=None,
        successful_stage=None,
        total_attempts=0,
    )
    s1, s2, s3 = get_stage_attempt_counts(res)
    assert s1 == 0 and s2 == 0 and s3 == 0
