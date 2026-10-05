"""
tests/test_file_selection_ui.py
Unit tests for locked file selection interaction in main.py.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from main import _select_locked_file
from modules.file_detector import DetectedFile


class TestSelectLockedFileUI:
    def test_choose_option_1_calls_detect_locked_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        expected = DetectedFile(path=tmp_path / "test.zip", format_name="ZIP Archive", extension=".zip")
        with patch("main.detect_locked_file", return_value=expected) as mock_detect:
            monkeypatch.setattr("builtins.input", lambda prompt="": "1")
            result = _select_locked_file()
            assert result == expected
            mock_detect.assert_called_once()

    def test_choose_option_2_with_valid_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target_file = tmp_path / "Important.docx"
        target_file.write_bytes(b"content")

        inputs = iter(["2", str(target_file)])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

        result = _select_locked_file()
        assert result.path == target_file
        assert result.extension == ".docx"
        assert result.format_name == "Word Document (OOXML)"

    def test_retry_on_invalid_choice(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        expected = DetectedFile(path=tmp_path / "test.pdf", format_name="PDF Document", extension=".pdf")
        with patch("main.detect_locked_file", return_value=expected):
            inputs = iter(["invalid", "5", "1"])
            monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
            result = _select_locked_file()
            assert result == expected

    def test_retry_on_invalid_manual_path_then_valid(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        valid_file = tmp_path / "valid.xlsx"
        valid_file.write_bytes(b"content")

        inputs = iter(["2", "non_existent_file.docx", str(valid_file)])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

        result = _select_locked_file()
        assert result.path == valid_file
        assert result.extension == ".xlsx"

    def test_keyboard_interrupt_exits_gracefully(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def raise_keyboard_interrupt(prompt=""):
            raise KeyboardInterrupt()

        monkeypatch.setattr("builtins.input", raise_keyboard_interrupt)
        with pytest.raises(SystemExit) as exc_info:
            _select_locked_file()
        assert exc_info.value.code == 130
