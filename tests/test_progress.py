"""
tests/test_progress.py
Unit tests for modules/progress.py

Only pure-calculation helper methods are tested here.
Rich live rendering (start / update / stop) requires an interactive terminal
and is intentionally excluded from the automated test suite.
"""

import pytest

from modules.progress import ProgressUI


# ──────────────────────────────────────────────────────────────────────────────
# ProgressUI.percentage()
# ──────────────────────────────────────────────────────────────────────────────


class TestPercentage:
    """Tests for ProgressUI.percentage() — a pure function of _total."""

    def _make_ui(self, total: int) -> ProgressUI:
        """Create a ProgressUI with _total set without triggering Rich."""
        ui = ProgressUI()
        ui._total = total
        return ui

    def test_zero_tested_gives_zero_percent(self) -> None:
        ui = self._make_ui(100)
        assert ui.percentage(0) == 0.0

    def test_half_tested_gives_fifty_percent(self) -> None:
        ui = self._make_ui(100)
        assert ui.percentage(50) == 50.0

    def test_all_tested_gives_hundred_percent(self) -> None:
        ui = self._make_ui(100)
        assert ui.percentage(100) == 100.0

    def test_over_total_clamped_to_hundred(self) -> None:
        ui = self._make_ui(100)
        assert ui.percentage(9999) == 100.0

    def test_zero_total_returns_zero_for_any_tested(self) -> None:
        ui = self._make_ui(0)
        assert ui.percentage(0) == 0.0
        assert ui.percentage(50) == 0.0
        assert ui.percentage(10000) == 0.0

    def test_one_of_one_gives_hundred_percent(self) -> None:
        ui = self._make_ui(1)
        assert ui.percentage(1) == 100.0

    def test_result_is_float(self) -> None:
        ui = self._make_ui(200)
        result = ui.percentage(100)
        assert isinstance(result, float)

    def test_fractional_percentage(self) -> None:
        ui = self._make_ui(3)
        pct = ui.percentage(1)
        assert abs(pct - 33.333333) < 0.001

    def test_large_total(self) -> None:
        ui = self._make_ui(1_000_000)
        assert ui.percentage(250_000) == pytest.approx(25.0)

    def test_percentage_never_exceeds_100(self) -> None:
        ui = self._make_ui(10)
        for tested in range(0, 200, 5):
            assert ui.percentage(tested) <= 100.0


# ──────────────────────────────────────────────────────────────────────────────
# ProgressUI.format_elapsed()
# ──────────────────────────────────────────────────────────────────────────────


class TestFormatElapsed:
    """Tests for ProgressUI.format_elapsed() — a static pure function."""

    def test_zero_seconds(self) -> None:
        assert ProgressUI.format_elapsed(0) == "00:00:00"

    def test_one_second(self) -> None:
        assert ProgressUI.format_elapsed(1) == "00:00:01"

    def test_fifty_nine_seconds(self) -> None:
        assert ProgressUI.format_elapsed(59) == "00:00:59"

    def test_exactly_one_minute(self) -> None:
        assert ProgressUI.format_elapsed(60) == "00:01:00"

    def test_ninety_seconds(self) -> None:
        assert ProgressUI.format_elapsed(90) == "00:01:30"

    def test_exactly_one_hour(self) -> None:
        assert ProgressUI.format_elapsed(3600) == "01:00:00"

    def test_complex_duration(self) -> None:
        # 1h 23m 45s = 5025 seconds
        assert ProgressUI.format_elapsed(3600 + 23 * 60 + 45) == "01:23:45"

    def test_more_than_24_hours(self) -> None:
        # 25h = 90000s → "25:00:00"
        assert ProgressUI.format_elapsed(90000) == "25:00:00"

    def test_negative_clamped_to_zero(self) -> None:
        assert ProgressUI.format_elapsed(-1) == "00:00:00"
        assert ProgressUI.format_elapsed(-999) == "00:00:00"

    def test_fractional_seconds_truncated(self) -> None:
        assert ProgressUI.format_elapsed(61.9) == "00:01:01"
        assert ProgressUI.format_elapsed(59.999) == "00:00:59"

    def test_output_is_string(self) -> None:
        assert isinstance(ProgressUI.format_elapsed(0), str)

    def test_output_format_hh_mm_ss(self) -> None:
        result = ProgressUI.format_elapsed(3661)
        parts = result.split(":")
        assert len(parts) == 3
        assert all(len(p) == 2 for p in parts)

    def test_all_parts_zero_padded(self) -> None:
        result = ProgressUI.format_elapsed(3661)  # 01:01:01
        assert result == "01:01:01"


# ──────────────────────────────────────────────────────────────────────────────
# ProgressUI instantiation (no rendering)
# ──────────────────────────────────────────────────────────────────────────────


class TestProgressUIInstantiation:
    def test_default_total_is_zero(self) -> None:
        ui = ProgressUI()
        assert ui._total == 0

    def test_default_progress_is_none(self) -> None:
        ui = ProgressUI()
        assert ui._progress is None

    def test_default_live_is_none(self) -> None:
        ui = ProgressUI()
        assert ui._live is None
