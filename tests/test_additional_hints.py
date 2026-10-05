"""
tests/test_additional_hints.py
Unit and integration tests for multi-round hint continuation after 'Password Not Found'.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import patch
import pytest
from rich.console import Console

from main import _recover_with_hints, prompt_for_additional_hints
from modules.attempt_logger import AttemptLogger
from modules.file_detector import DetectedFile
from modules.hint_collector import HintModel
from modules.progress import HintProgressUI
from modules.search_space import calculate_search_space
from modules.search_stages import execute_progressive_recovery


# ──────────────────────────────────────────────────────────────────────────────
# 1. Prompt For Additional Hints Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestPromptForAdditionalHints:
    def test_select_yes_returns_true(self) -> None:
        for val in ["1", "[1]", "yes", "Yes", "y", "Y", "YES"]:
            console = Console(file=StringIO())
            assert prompt_for_additional_hints(console=console, input_func=lambda _: val) is True

    def test_select_no_returns_false(self) -> None:
        for val in ["2", "[2]", "no", "No", "n", "N", "NO"]:
            console = Console(file=StringIO())
            assert prompt_for_additional_hints(console=console, input_func=lambda _: val) is False

    def test_invalid_input_retries_then_accepts(self) -> None:
        inputs = iter(["invalid", "abc", "1"])
        console = Console(file=StringIO())
        assert prompt_for_additional_hints(console=console, input_func=lambda _: next(inputs)) is True

    def test_eof_or_interrupt_returns_false(self) -> None:
        def raise_eof(_: str) -> str:
            raise EOFError()

        console = Console(file=StringIO())
        assert prompt_for_additional_hints(console=console, input_func=raise_eof) is False


# ──────────────────────────────────────────────────────────────────────────────
# 2. Multi-Round Deduplication & Attempt Logging Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestMultiRoundContinuationEngine:
    def test_previously_tested_candidates_skipped_in_next_round(self, tmp_path: Path) -> None:
        """Verify that passing `seen` skips already tested candidates in round 2."""
        hints_round1 = HintModel(name=["ayush"], number=["123"])
        hints_round2 = HintModel(name=["ayush"], number=["123", "456"])

        seen: set[str] = set()
        tested_round1: list[str] = []
        tested_round2: list[str] = []

        def mock_verify_r1(target, cand):
            tested_round1.append(cand)
            return False

        def mock_verify_r2(target, cand):
            tested_round2.append(cand)
            return False

        with AttemptLogger(output_dir=tmp_path, timestamp="20261005_180001") as logger:
            res1 = execute_progressive_recovery(
                target_file="test.docx",
                hints=hints_round1,
                verify_fn=mock_verify_r1,
                attempt_logger=logger,
                seen=seen,
            )
            assert res1.success is False
            assert len(tested_round1) > 0
            assert len(seen) == len(tested_round1)

            res2 = execute_progressive_recovery(
                target_file="test.docx",
                hints=hints_round2,
                verify_fn=mock_verify_r2,
                attempt_logger=logger,
                seen=seen,
            )
            assert res2.success is False
            assert len(tested_round2) > 0

            # No candidate tested in round 2 was already in round 1
            overlap = set(tested_round1).intersection(set(tested_round2))
            assert len(overlap) == 0

            # Logger recorded unique attempts
            logged_lines = logger.file_path.read_text(encoding="utf-8").splitlines()
            assert len(logged_lines) == len(tested_round1) + len(tested_round2)
            assert len(logged_lines) == len(set(logged_lines))

    def test_continuation_finds_password_in_round_2_and_stops_immediately(self, tmp_path: Path) -> None:
        """Password present only in round 2 hints is found and terminates immediately."""
        hints_round1 = HintModel(name=["Alice"], number=["111"])
        hints_round2 = HintModel(name=["Alice"], number=["222"])

        winning_password = "Alice222"
        seen: set[str] = set()
        tested_all: list[str] = []

        def mock_verify(target, cand):
            tested_all.append(cand)
            return cand == winning_password

        with AttemptLogger(output_dir=tmp_path, timestamp="20261005_180002") as logger:
            res1 = execute_progressive_recovery(
                target_file="test.docx",
                hints=hints_round1,
                verify_fn=mock_verify,
                attempt_logger=logger,
                seen=seen,
            )
            assert res1.success is False

            res2 = execute_progressive_recovery(
                target_file="test.docx",
                hints=hints_round2,
                verify_fn=mock_verify,
                attempt_logger=logger,
                seen=seen,
            )
            assert res2.success is True
            assert res2.found_password == winning_password
            assert res2.successful_stage == 1

            # Log ends with winning password
            logged_lines = logger.file_path.read_text(encoding="utf-8").splitlines()
            assert logged_lines[-1] == winning_password
            assert len(logged_lines) == len(tested_all)


# ──────────────────────────────────────────────────────────────────────────────
# 3. End-to-End Workflow with Additional Hints Loop
# ──────────────────────────────────────────────────────────────────────────────


class TestEndToEndAdditionalHintsWorkflow:
    def test_round1_exhausted_user_declines_additional_hints(self, tmp_path: Path) -> None:
        """Round 1 exhausts and user chooses [2] No -> completes with failure."""
        hints = HintModel(name=["Alice"], number=["123"])
        detected = DetectedFile(path=Path("dummy.docx"), format_name="DOCX", extension=".docx")
        console = Console(file=StringIO())

        with patch("main.collect_password_hints", return_value=hints), \
             patch("main.prompt_for_additional_hints", return_value=False), \
             patch("main.prompt_keep_unsuccessful_history", return_value=True), \
             patch("main.verify", return_value=False), \
             patch("main.RESULTS_DIR", tmp_path), \
             patch("main.display_search_space_analysis"), \
             patch("main.display_recovery_summary") as mock_summary:

            exit_code = _recover_with_hints(detected, console=console)
            assert exit_code == 0
            mock_summary.assert_called_once()
            res = mock_summary.call_args[1]["result"]
            assert res.success is False
            assert res.total_attempts > 0

    def test_round1_exhausted_user_provides_round2_hints_success(self, tmp_path: Path) -> None:
        """Round 1 exhausts, user chooses [1] Yes, Round 2 hints find password -> success."""
        hints1 = HintModel(name=["Alice"], number=["123"])
        hints2 = HintModel(name=["Alice"], number=["7210"])
        winning_password = "Alice7210"
        console = Console(file=StringIO())

        detected = DetectedFile(path=Path("dummy.docx"), format_name="DOCX", extension=".docx")

        with patch("main.collect_password_hints", side_effect=[hints1, hints2]), \
             patch("main.prompt_for_additional_hints", side_effect=[True]), \
             patch("main.prompt_save_recovery_history", return_value=True), \
             patch("main.verify", side_effect=lambda target, cand: cand == winning_password), \
             patch("main.RESULTS_DIR", tmp_path), \
             patch("main.display_search_space_analysis"), \
             patch("main.display_recovery_summary") as mock_summary:

            exit_code = _recover_with_hints(detected, console=console)
            assert exit_code == 0
            mock_summary.assert_called_once()
            res = mock_summary.call_args[1]["result"]
            assert res.success is True
            assert res.found_password == winning_password

    def test_three_rounds_continuation_exhausted(self, tmp_path: Path) -> None:
        """3 rounds of hints exhausted before user selects [2] No."""
        h1 = HintModel(name=["A"], number=["1"])
        h2 = HintModel(name=["B"], number=["2"])
        h3 = HintModel(name=["C"], number=["3"])
        console = Console(file=StringIO())

        detected = DetectedFile(path=Path("dummy.docx"), format_name="DOCX", extension=".docx")

        with patch("main.collect_password_hints", side_effect=[h1, h2, h3]), \
             patch("main.prompt_for_additional_hints", side_effect=[True, True, False]), \
             patch("main.prompt_keep_unsuccessful_history", return_value=True), \
             patch("main.verify", return_value=False), \
             patch("main.RESULTS_DIR", tmp_path), \
             patch("main.display_search_space_analysis"), \
             patch("main.display_recovery_summary") as mock_summary:

            exit_code = _recover_with_hints(detected, console=console)
            assert exit_code == 0
            mock_summary.assert_called_once()
            res = mock_summary.call_args[1]["result"]
            assert res.success is False
            assert res.total_attempts > 0
