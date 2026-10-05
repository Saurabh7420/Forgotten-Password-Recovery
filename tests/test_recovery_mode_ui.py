"""
tests/test_recovery_mode_ui.py
Unit tests for recovery mode selection and routing in main.py.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from main import _recover_with_hints, _select_recovery_mode, main
from modules.file_detector import DetectedFile
from modules.hint_collector import HintModel


class TestSelectRecoveryModeUI:
    def test_choose_option_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("builtins.input", lambda prompt="": "1")
        assert _select_recovery_mode() == "1"

    def test_choose_option_1_with_brackets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("builtins.input", lambda prompt="": "[1]")
        assert _select_recovery_mode() == "1"

    def test_choose_option_2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("builtins.input", lambda prompt="": "2")
        assert _select_recovery_mode() == "2"

    def test_choose_option_2_with_brackets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("builtins.input", lambda prompt="": "[2]")
        assert _select_recovery_mode() == "2"

    def test_retry_on_invalid_choice_then_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        inputs = iter(["0", "invalid", "3", "2"])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
        assert _select_recovery_mode() == "2"

    def test_keyboard_interrupt_exits_gracefully(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def raise_keyboard_interrupt(prompt=""):
            raise KeyboardInterrupt()

        monkeypatch.setattr("builtins.input", raise_keyboard_interrupt)
        with pytest.raises(SystemExit) as exc_info:
            _select_recovery_mode()
        assert exc_info.value.code == 130


class TestRecoverWithHintsPlaceholder:
    def test_placeholder_returns_zero_when_confirmed(self, tmp_path: Path) -> None:
        detected = DetectedFile(
            path=tmp_path / "test.docx",
            format_name="Word Document (OOXML)",
            extension=".docx",
        )
        fake_hints = HintModel(name=["Saniya"], min_length=8, max_length=12)
        with patch("main.collect_password_hints", return_value=fake_hints), \
             patch("main.verify", return_value=False), \
             patch("main.prompt_for_additional_hints", return_value=False), \
             patch("main.prompt_keep_unsuccessful_history", return_value=True):
            exit_code = _recover_with_hints(detected)
            assert exit_code == 0

    def test_placeholder_returns_zero_when_cancelled(self, tmp_path: Path) -> None:
        detected = DetectedFile(
            path=tmp_path / "test.docx",
            format_name="Word Document (OOXML)",
            extension=".docx",
        )
        with patch("main.collect_password_hints", return_value=None):
            exit_code = _recover_with_hints(detected)
            assert exit_code == 0


class TestMainRouting:
    def test_main_routes_to_password_list_when_option_1(self, tmp_path: Path) -> None:
        detected = DetectedFile(
            path=tmp_path / "test.pdf",
            format_name="PDF Document",
            extension=".pdf",
        )
        with (
            patch("main._select_locked_file", return_value=detected),
            patch("main._select_recovery_mode", return_value="1"),
            patch("main._recover_with_password_list", return_value=0) as mock_list_flow,
        ):
            code = main()
            assert code == 0
            mock_list_flow.assert_called_once_with(detected)

    def test_main_routes_to_hints_when_option_2(self, tmp_path: Path) -> None:
        detected = DetectedFile(
            path=tmp_path / "test.xlsx",
            format_name="Excel Spreadsheet (OOXML)",
            extension=".xlsx",
        )
        with (
            patch("main._select_locked_file", return_value=detected),
            patch("main._select_recovery_mode", return_value="2"),
            patch("main._recover_with_hints", return_value=0) as mock_hints_flow,
        ):
            code = main()
            assert code == 0
            mock_hints_flow.assert_called_once_with(detected)
