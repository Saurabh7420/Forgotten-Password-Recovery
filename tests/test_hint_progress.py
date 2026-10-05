"""
tests/test_hint_progress.py
Unit and integration tests for HintProgressUI (live progress display for hint-based recovery).
"""

from __future__ import annotations

import pytest
from io import StringIO
from rich.console import Console

from modules.hint_collector import HintModel
from modules.progress import HintProgressUI
from modules.search_stages import execute_progressive_recovery


# ──────────────────────────────────────────────────────────────────────────────
# 1. Pure Calculation Helpers: Percentage & Remaining
# ──────────────────────────────────────────────────────────────────────────────


class TestHintProgressCalculations:
    def test_percentage_calculation(self) -> None:
        ui = HintProgressUI(total=884)
        assert ui.percentage(0) == 0.0
        assert ui.percentage(110) == pytest.approx(12.4434, rel=1e-3)
        assert f"{ui.percentage(110):.2f}%" == "12.44%"
        assert ui.percentage(884) == 100.0
        assert ui.percentage(9999) == 100.0  # Clamped

    def test_percentage_with_zero_total(self) -> None:
        ui = HintProgressUI(total=0)
        assert ui.percentage(0) == 0.0
        assert ui.percentage(50) == 0.0

    def test_remaining_calculation(self) -> None:
        ui = HintProgressUI(total=884)
        assert ui.remaining(0) == 884
        assert ui.remaining(110) == 774
        assert ui.remaining(884) == 0
        assert ui.remaining(1000) == 0  # Clamped


# ──────────────────────────────────────────────────────────────────────────────
# 2. Time and Duration Formatting
# ──────────────────────────────────────────────────────────────────────────────


class TestHintProgressDurationFormatting:
    def test_format_duration_seconds_only(self) -> None:
        assert HintProgressUI.format_duration(0) == "00:00"
        assert HintProgressUI.format_duration(18) == "00:18"
        assert HintProgressUI.format_duration(59) == "00:59"

    def test_format_duration_minutes_and_seconds(self) -> None:
        assert HintProgressUI.format_duration(60) == "01:00"
        assert HintProgressUI.format_duration(126) == "02:06"
        assert HintProgressUI.format_duration(3599) == "59:59"

    def test_format_duration_hours(self) -> None:
        assert HintProgressUI.format_duration(3600) == "01:00:00"
        assert HintProgressUI.format_duration(3665) == "01:01:05"
        assert HintProgressUI.format_duration(7320) == "02:02:00"

    def test_format_duration_negative_clamped(self) -> None:
        assert HintProgressUI.format_duration(-10) == "00:00"


# ──────────────────────────────────────────────────────────────────────────────
# 3. ETA Calculation Based on Measured Attempt Rate
# ──────────────────────────────────────────────────────────────────────────────


class TestHintProgressETACalculation:
    def test_eta_at_beginning_is_calculating(self) -> None:
        # tested = 0
        assert HintProgressUI.calculate_eta(0, 884, 0.0) == "Calculating..."
        assert HintProgressUI.calculate_eta(0, 884, 5.0) == "Calculating..."

    def test_eta_zero_elapsed_is_calculating(self) -> None:
        assert HintProgressUI.calculate_eta(10, 884, 0.0) == "Calculating..."

    def test_eta_negative_elapsed_is_calculating(self) -> None:
        assert HintProgressUI.calculate_eta(10, 884, -2.0) == "Calculating..."

    def test_eta_measured_rate_matches_specification(self) -> None:
        # Rate: 110 tested in 18 seconds = 6.111 cand/sec
        # Remaining: 884 - 110 = 774
        # Estimated time: 774 / 6.111 = 126.65 sec = 02:06
        eta = HintProgressUI.calculate_eta(tested=110, total=884, elapsed_seconds=18.0)
        assert eta == "02:06"

    def test_eta_when_completed(self) -> None:
        assert HintProgressUI.calculate_eta(tested=884, total=884, elapsed_seconds=30.0) == "00:00"


# ──────────────────────────────────────────────────────────────────────────────
# 4. Display Text Formatting
# ──────────────────────────────────────────────────────────────────────────────


class TestHintProgressDisplayText:
    def test_display_text_active_testing(self) -> None:
        text = HintProgressUI.get_display_text(
            tested=110,
            total=884,
            elapsed_seconds=18.0,
            status="Testing candidate...",
        )
        lines = text.splitlines()
        assert "Tested          : 110 / 884" in lines
        assert "Progress        : 12.44%" in lines
        assert "Remaining       : 774" in lines
        assert "Elapsed Time    : 00:18" in lines
        assert "Estimated Left  : 02:06" in lines
        assert "Status          : Testing candidate..." in lines

    def test_display_text_initial_state(self) -> None:
        text = HintProgressUI.get_display_text(
            tested=0,
            total=884,
            elapsed_seconds=0.0,
            status="Testing candidate...",
        )
        assert "Tested          : 0 / 884" in text
        assert "Progress        : 0.00%" in text
        assert "Remaining       : 884" in text
        assert "Elapsed Time    : 00:00" in text
        assert "Estimated Left  : Calculating..." in text
        assert "Status          : Testing candidate..." in text

    def test_display_text_password_found(self) -> None:
        text = HintProgressUI.get_display_text(
            tested=110,
            total=884,
            elapsed_seconds=18.0,
            status="Password found",
            header="PASSWORD FOUND",
        )
        lines = text.splitlines()
        assert lines[0] == "PASSWORD FOUND"
        assert lines[1] == ""
        assert "Tested          : 110 / 884" in lines
        assert "Progress        : 12.44%" in lines
        assert "Remaining       : 774" in lines
        assert "Elapsed Time    : 00:18" in lines
        assert "Status          : Password found" in lines
        # Estimated Left is omitted on completion
        assert "Estimated Left" not in text

    def test_display_text_password_not_found_exhausted(self) -> None:
        text = HintProgressUI.get_display_text(
            tested=884,
            total=884,
            elapsed_seconds=30.0,
            status="All candidates exhausted",
            header="PASSWORD NOT FOUND",
        )
        lines = text.splitlines()
        assert lines[0] == "PASSWORD FOUND" or lines[0] == "PASSWORD NOT FOUND"
        assert lines[0] == "PASSWORD NOT FOUND"
        assert lines[1] == ""
        assert "Tested          : 884 / 884" in lines
        assert "Progress        : 100.00%" in lines
        assert "Remaining       : 0" in lines
        assert "Elapsed Time    : 00:30" in lines
        assert "Status          : All candidates exhausted" in lines
        assert "Estimated Left" not in text


# ──────────────────────────────────────────────────────────────────────────────
# 5. HintProgressUI Lifecycle and Integration Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestHintProgressLifecycleAndIntegration:
    def test_ui_lifecycle_state_transitions(self) -> None:
        clock = 100.0

        def mock_time() -> float:
            return clock

        console = Console(file=StringIO())
        ui = HintProgressUI(total=100, console=console, time_func=mock_time)
        assert ui.tested == 0
        assert ui.start_time is None

        ui.start()
        assert ui.start_time == 100.0

        clock = 110.0
        ui.update(tested=25)
        assert ui.tested == 25

        clock = 120.0
        ui.finish(success=True, tested=50)
        assert ui.found is True
        assert ui.header == "PASSWORD FOUND"
        assert ui.status == "Password found"

    def test_ui_exhaustion_sets_tested_to_total(self) -> None:
        console = Console(file=StringIO())
        ui = HintProgressUI(total=100, console=console)
        ui.finish(success=False, tested=100)
        assert ui.found is False
        assert ui.header == "PASSWORD NOT FOUND"
        assert ui.status == "All candidates exhausted"
        assert ui.tested == 100

    def test_integration_with_execute_progressive_recovery_success(self) -> None:
        hints = HintModel(name=["Saniya"], number=["7070"])
        console = Console(file=StringIO())
        ui = HintProgressUI(total=100, console=console)

        def mock_verify(target, cand):
            return cand == "Saniya7070"

        res = execute_progressive_recovery(
            target_file="test.docx",
            hints=hints,
            verify_fn=mock_verify,
            progress_ui=ui,
        )
        assert res.success is True
        assert ui.found is True
        assert ui.header == "PASSWORD FOUND"

    def test_integration_with_execute_progressive_recovery_exhausted(self) -> None:
        hints = HintModel(name=["Saniya"], number=["7070"])
        console = Console(file=StringIO())
        ui = HintProgressUI(total=100, console=console)

        def mock_verify(target, cand):
            return False

        res = execute_progressive_recovery(
            target_file="test.docx",
            hints=hints,
            verify_fn=mock_verify,
            progress_ui=ui,
        )
        assert res.success is False
        assert ui.found is False
        assert ui.header == "PASSWORD NOT FOUND"
