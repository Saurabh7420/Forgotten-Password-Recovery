"""
tests/test_round_history.py
Unit and integration tests for round-wise recovery history, session tracking,
Round_<N>.txt / Round_<N>_SUCCESS.txt files, and user-prompted history retention / deletion.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import patch
import pytest
from rich.console import Console

from main import (
    _recover_with_hints,
    _recover_with_password_list,
    prompt_keep_unsuccessful_history,
    prompt_save_recovery_history,
)
from modules.attempt_logger import AttemptLogger, RoundHistoryLogger, SessionHistoryManager
from modules.file_detector import DetectedFile
from modules.hint_collector import HintModel
from modules.search_stages import execute_progressive_recovery


# ──────────────────────────────────────────────────────────────────────────────
# 1. RoundHistoryLogger & SessionHistoryManager Unit Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestRoundHistoryLoggerUnit:
    def test_round_file_created_on_initialization(self, tmp_path: Path) -> None:
        logger = RoundHistoryLogger(
            output_dir=tmp_path,
            round_number=1,
        )
        assert logger.file_path.exists()
        assert logger.filename == "Round_1.txt"

    def test_round_file_content_on_not_found(self, tmp_path: Path) -> None:
        logger = RoundHistoryLogger(
            output_dir=tmp_path,
            round_number=1,
        )
        logger.log_attempt("Alpha1")
        logger.log_attempt("Alpha2")
        path = logger.finalize(success=False)

        assert path.name == "Round_1.txt"
        content = path.read_text(encoding="utf-8")
        assert "========================================" in content
        assert "RECOVERY ROUND 1" in content
        assert "Status: PASSWORD NOT FOUND" in content
        assert "Candidates Tested: 2" in content
        assert "TESTED PASSWORD CANDIDATES" in content
        assert "Alpha1\nAlpha2" in content
        assert "END OF ROUND 1" in content

    def test_round_file_content_on_success(self, tmp_path: Path) -> None:
        logger = RoundHistoryLogger(
            output_dir=tmp_path,
            round_number=4,
        )
        logger.log_attempt("cand1")
        logger.log_attempt("cand2")
        logger.log_attempt("@Ayush7210")
        path = logger.finalize(
            success=True,
            found_password="@Ayush7210",
            successful_stage_name="Stage 1 — Direct Hint Search",
            attempt_in_round=29,
        )

        assert path.name == "Round_4_SUCCESS.txt"
        assert not (tmp_path / "Round_4.txt").exists()
        content = path.read_text(encoding="utf-8")
        assert "========================================" in content
        assert "RECOVERY ROUND 4" in content
        assert "Status: PASSWORD FOUND" in content
        assert "Successful Candidate: @Ayush7210" in content
        assert "Stage: Stage 1 — Direct Hint Search" in content
        assert "Attempt: 29" in content
        assert "cand1\ncand2\n@Ayush7210" in content
        assert "END OF ROUND 4" in content


class TestSessionHistoryManagerUnit:
    def test_creates_round_files_and_tracks_cleanup(self, tmp_path: Path) -> None:
        sm = SessionHistoryManager(output_dir=tmp_path)
        r1 = sm.start_round(1)
        r1.log_attempt("p1")
        r1.finalize(success=False)

        r2 = sm.start_round(2)
        r2.log_attempt("p2")
        r2.finalize(success=True, found_password="p2", successful_stage_name="Stage 1", attempt_in_round=1)

        assert (tmp_path / "Round_1.txt").exists()
        assert (tmp_path / "Round_2_SUCCESS.txt").exists()

        deleted = sm.delete_session_files()
        assert (tmp_path / "Round_1.txt") in deleted
        assert (tmp_path / "Round_2_SUCCESS.txt") in deleted
        assert not (tmp_path / "Round_1.txt").exists()
        assert not (tmp_path / "Round_2_SUCCESS.txt").exists()

    def test_delete_session_files_preserves_unrelated_and_readme(self, tmp_path: Path) -> None:
        readme = tmp_path / "README.md"
        readme.write_text("Do not touch", encoding="utf-8")
        other_session = tmp_path / "Round_1_old.txt"
        other_session.write_text("Old session", encoding="utf-8")

        sm = SessionHistoryManager(output_dir=tmp_path)
        r1 = sm.start_round(1)
        r1.log_attempt("cand")
        r1.finalize(success=False)

        assert r1.file_path.exists()
        assert readme.exists()
        assert other_session.exists()

        deleted = sm.delete_session_files()
        assert r1.file_path in deleted
        assert not r1.file_path.exists()

        # Other files preserved
        assert readme.exists()
        assert other_session.exists()


# ──────────────────────────────────────────────────────────────────────────────
# 2. Interactive Prompt Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestHistoryPrompts:
    def test_prompt_save_recovery_history_yes(self) -> None:
        console = Console(file=StringIO())
        for val in ["1", "[1]", "yes", "Yes", "y", "Y"]:
            assert prompt_save_recovery_history(console=console, input_func=lambda _: val) is True

    def test_prompt_save_recovery_history_no(self) -> None:
        console = Console(file=StringIO())
        for val in ["2", "[2]", "no", "No", "n", "N"]:
            assert prompt_save_recovery_history(console=console, input_func=lambda _: val) is False

    def test_prompt_keep_unsuccessful_history_yes(self) -> None:
        console = Console(file=StringIO())
        for val in ["1", "[1]", "yes", "Yes", "y", "Y"]:
            assert prompt_keep_unsuccessful_history(console=console, input_func=lambda _: val) is True

    def test_prompt_keep_unsuccessful_history_no(self) -> None:
        console = Console(file=StringIO())
        for val in ["2", "[2]", "no", "No", "n", "N"]:
            assert prompt_keep_unsuccessful_history(console=console, input_func=lambda _: val) is False


# ──────────────────────────────────────────────────────────────────────────────
# 3. Integration & Multi-Round Workflow Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestMultiRoundHistoryIntegration:
    def test_multi_round_creates_distinct_files_and_skips_duplicates(self, tmp_path: Path) -> None:
        """Verify round 1 and round 2 create distinct Round_1.txt and Round_2.txt without duplicates."""
        hints1 = HintModel(name=["Alice"], number=["123"])
        hints2 = HintModel(name=["Alice"], number=["123", "456"])
        console = Console(file=StringIO())
        detected = DetectedFile(path=Path("test.docx"), format_name="Word Document", extension=".docx")

        with patch("main.collect_password_hints", side_effect=[hints1, hints2]), \
             patch("main.prompt_for_additional_hints", side_effect=[True, False]), \
             patch("main.prompt_keep_unsuccessful_history", return_value=True), \
             patch("main.verify", return_value=False), \
             patch("main.RESULTS_DIR", tmp_path), \
             patch("main.display_search_space_analysis"), \
             patch("main.display_recovery_summary"):

            exit_code = _recover_with_hints(detected, console=console)
            assert exit_code == 0

        r1_path = tmp_path / "Round_1.txt"
        r2_path = tmp_path / "Round_2.txt"
        assert r1_path.exists()
        assert r2_path.exists()

        content_r1 = r1_path.read_text(encoding="utf-8")
        content_r2 = r2_path.read_text(encoding="utf-8")

        assert "RECOVERY ROUND 1" in content_r1
        assert "RECOVERY ROUND 2" in content_r2

        def extract_candidates(txt: str) -> list[str]:
            lines = txt.splitlines()
            start = lines.index("TESTED PASSWORD CANDIDATES") + 2
            end = lines.index("-" * 40, start)
            return [c for c in lines[start:end] if c.strip()]

        cands_r1 = extract_candidates(content_r1)
        cands_r2 = extract_candidates(content_r2)

        assert len(cands_r1) > 0
        assert len(cands_r2) > 0
        overlap = set(cands_r1).intersection(set(cands_r2))
        assert len(overlap) == 0

    def test_password_found_creates_round_success_file_and_user_saves(self, tmp_path: Path) -> None:
        """When password is found in round 2, Round_2_SUCCESS.txt is created and kept on save."""
        hints1 = HintModel(name=["Alice"], number=["123"])
        hints2 = HintModel(name=["Alice"], number=["7210"])
        winning_password = "Alice7210"
        console = Console(file=StringIO())
        detected = DetectedFile(path=Path("test.docx"), format_name="Word Document", extension=".docx")

        with patch("main.collect_password_hints", side_effect=[hints1, hints2]), \
             patch("main.prompt_for_additional_hints", side_effect=[True]), \
             patch("main.prompt_save_recovery_history", return_value=True), \
             patch("main.verify", side_effect=lambda f, cand: cand == winning_password), \
             patch("main.RESULTS_DIR", tmp_path), \
             patch("main.display_search_space_analysis"), \
             patch("main.display_recovery_summary"):

            exit_code = _recover_with_hints(detected, console=console)
            assert exit_code == 0

        r1_path = tmp_path / "Round_1.txt"
        r2_success_path = tmp_path / "Round_2_SUCCESS.txt"
        assert r1_path.exists()
        assert r2_success_path.exists()

        r2_content = r2_success_path.read_text(encoding="utf-8")
        assert "RECOVERY ROUND 2" in r2_content
        assert "Status: PASSWORD FOUND" in r2_content
        assert f"Successful Candidate: {winning_password}" in r2_content
        assert winning_password in r2_content

    def test_password_found_user_chooses_delete_history(self, tmp_path: Path) -> None:
        """When password is found and user chooses No, only session round files are deleted."""
        readme = tmp_path / "README.md"
        readme.write_text("Persistent README", encoding="utf-8")

        hints = HintModel(name=["Alice"], number=["7210"])
        winning_password = "Alice7210"
        console = Console(file=StringIO())
        detected = DetectedFile(path=Path("test.docx"), format_name="Word Document", extension=".docx")

        with patch("main.collect_password_hints", return_value=hints), \
             patch("main.prompt_save_recovery_history", return_value=False), \
             patch("main.verify", side_effect=lambda f, cand: cand == winning_password), \
             patch("main.RESULTS_DIR", tmp_path), \
             patch("main.display_search_space_analysis"), \
             patch("main.display_recovery_summary"):

            exit_code = _recover_with_hints(detected, console=console)
            assert exit_code == 0

        round_files = list(tmp_path.glob("Round_*.txt"))
        assert len(round_files) == 0
        assert readme.exists()

    def test_password_not_found_user_chooses_delete_history(self, tmp_path: Path) -> None:
        """When password not found and user chooses No to keep history, round files are deleted."""
        hints = HintModel(name=["Alice"], number=["123"])
        console = Console(file=StringIO())
        detected = DetectedFile(path=Path("test.docx"), format_name="Word Document", extension=".docx")

        with patch("main.collect_password_hints", return_value=hints), \
             patch("main.prompt_for_additional_hints", return_value=False), \
             patch("main.prompt_keep_unsuccessful_history", return_value=False), \
             patch("main.verify", return_value=False), \
             patch("main.RESULTS_DIR", tmp_path), \
             patch("main.display_search_space_analysis"), \
             patch("main.display_recovery_summary"):

            exit_code = _recover_with_hints(detected, console=console)
            assert exit_code == 0

        round_files = list(tmp_path.glob("Round_*.txt"))
        assert len(round_files) == 0

    def test_fresh_session_starts_with_empty_history(self, tmp_path: Path) -> None:
        """Verify two successive sessions start independently without candidate pollution."""
        hints_s1 = HintModel(name=["Alice"], number=["111"])
        hints_s2 = HintModel(name=["Bob"], number=["222"])
        console = Console(file=StringIO())
        detected = DetectedFile(path=Path("test.docx"), format_name="Word Document", extension=".docx")

        # Session 1
        with patch("main.collect_password_hints", return_value=hints_s1), \
             patch("main.prompt_for_additional_hints", return_value=False), \
             patch("main.prompt_keep_unsuccessful_history", return_value=True), \
             patch("main.verify", return_value=False), \
             patch("main.RESULTS_DIR", tmp_path), \
             patch("main.display_search_space_analysis"), \
             patch("main.display_recovery_summary"):
            _recover_with_hints(detected, console=console)

        # Session 2
        with patch("main.collect_password_hints", return_value=hints_s2), \
             patch("main.prompt_for_additional_hints", return_value=False), \
             patch("main.prompt_keep_unsuccessful_history", return_value=True), \
             patch("main.verify", return_value=False), \
             patch("main.RESULTS_DIR", tmp_path), \
             patch("main.display_search_space_analysis"), \
             patch("main.display_recovery_summary"):
            _recover_with_hints(detected, console=console)

        content = (tmp_path / "Round_1.txt").read_text(encoding="utf-8")
        assert "Bob" in content
        assert "Alice" not in content
