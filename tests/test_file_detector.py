"""
tests/test_file_detector.py
Unit tests for modules/file_detector.py
"""

from pathlib import Path

import pytest

from modules.file_detector import (
    SUPPORTED_EXTENSIONS,
    DetectedFile,
    FileDetectionError,
    detect_file_from_path,
    detect_locked_file,
    scan_locked_files,
)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Extension registry sanity checks
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestSupportedExtensions:
    def test_zip_is_supported(self) -> None:
        assert ".zip" in SUPPORTED_EXTENSIONS

    def test_pdf_is_supported(self) -> None:
        assert ".pdf" in SUPPORTED_EXTENSIONS

    def test_docx_is_supported(self) -> None:
        assert ".docx" in SUPPORTED_EXTENSIONS

    def test_xlsx_is_supported(self) -> None:
        assert ".xlsx" in SUPPORTED_EXTENSIONS

    def test_pptx_is_supported(self) -> None:
        assert ".pptx" in SUPPORTED_EXTENSIONS

    def test_doc_is_supported(self) -> None:
        assert ".doc" in SUPPORTED_EXTENSIONS

    def test_xls_is_supported(self) -> None:
        assert ".xls" in SUPPORTED_EXTENSIONS

    def test_ppt_is_supported(self) -> None:
        assert ".ppt" in SUPPORTED_EXTENSIONS

    def test_7z_is_supported(self) -> None:
        assert ".7z" in SUPPORTED_EXTENSIONS

    def test_nine_formats_total(self) -> None:
        assert len(SUPPORTED_EXTENSIONS) == 9

    def test_exe_is_not_supported(self) -> None:
        assert ".exe" not in SUPPORTED_EXTENSIONS

    def test_txt_is_not_supported(self) -> None:
        assert ".txt" not in SUPPORTED_EXTENSIONS

    def test_mp4_is_not_supported(self) -> None:
        assert ".mp4" not in SUPPORTED_EXTENSIONS

    def test_all_extensions_start_with_dot(self) -> None:
        for ext in SUPPORTED_EXTENSIONS:
            assert ext.startswith("."), f"Extension '{ext}' must start with '.'"

    def test_all_extensions_are_lowercase(self) -> None:
        for ext in SUPPORTED_EXTENSIONS:
            assert ext == ext.lower(), f"Extension '{ext}' must be lowercase"

    def test_all_format_names_are_non_empty_strings(self) -> None:
        for ext, name in SUPPORTED_EXTENSIONS.items():
            assert isinstance(name, str) and name.strip(), (
                f"Format name for '{ext}' must be a non-empty string"
            )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# scan_locked_files â€” happy path
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestScanLockedFilesHappyPath:
    def test_empty_directory_returns_empty_lists(self, tmp_path: Path) -> None:
        supported, unsupported = scan_locked_files(tmp_path)
        assert supported == []
        assert unsupported == []

    def test_single_supported_file_detected(self, tmp_path: Path) -> None:
        (tmp_path / "archive.zip").write_bytes(b"")
        supported, _ = scan_locked_files(tmp_path)
        assert len(supported) == 1

    def test_detected_file_has_correct_extension(self, tmp_path: Path) -> None:
        (tmp_path / "doc.pdf").write_bytes(b"")
        supported, _ = scan_locked_files(tmp_path)
        assert supported[0].extension == ".pdf"

    def test_detected_file_has_correct_format_name(self, tmp_path: Path) -> None:
        (tmp_path / "doc.pdf").write_bytes(b"")
        supported, _ = scan_locked_files(tmp_path)
        assert supported[0].format_name == "PDF Document"

    def test_detected_file_has_correct_path(self, tmp_path: Path) -> None:
        f = tmp_path / "archive.zip"
        f.write_bytes(b"")
        supported, _ = scan_locked_files(tmp_path)
        assert supported[0].path == f

    def test_returns_detected_file_named_tuple(self, tmp_path: Path) -> None:
        (tmp_path / "archive.zip").write_bytes(b"")
        supported, _ = scan_locked_files(tmp_path)
        assert isinstance(supported[0], DetectedFile)

    def test_multiple_supported_files_all_detected(self, tmp_path: Path) -> None:
        (tmp_path / "a.zip").write_bytes(b"")
        (tmp_path / "b.pdf").write_bytes(b"")
        (tmp_path / "c.docx").write_bytes(b"")
        supported, _ = scan_locked_files(tmp_path)
        assert len(supported) == 3

    def test_unsupported_file_in_unsupported_list(self, tmp_path: Path) -> None:
        (tmp_path / "video.mp4").write_bytes(b"")
        _, unsupported = scan_locked_files(tmp_path)
        assert "video.mp4" in unsupported

    def test_unsupported_file_not_in_supported_list(self, tmp_path: Path) -> None:
        (tmp_path / "video.mp4").write_bytes(b"")
        supported, _ = scan_locked_files(tmp_path)
        assert supported == []

    def test_mixed_supported_and_unsupported(self, tmp_path: Path) -> None:
        (tmp_path / "locked.zip").write_bytes(b"")
        (tmp_path / "notes.txt").write_bytes(b"")
        supported, unsupported = scan_locked_files(tmp_path)
        assert len(supported) == 1
        assert "notes.txt" in unsupported


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# scan_locked_files â€” skipped files
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestScanLockedFilesSkippedFiles:
    def test_readme_md_is_silently_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("info", encoding="utf-8")
        supported, unsupported = scan_locked_files(tmp_path)
        assert supported == []
        assert "README.md" not in unsupported

    def test_hidden_dot_files_are_silently_ignored(self, tmp_path: Path) -> None:
        (tmp_path / ".gitkeep").write_bytes(b"")
        (tmp_path / ".DS_Store").write_bytes(b"")
        supported, unsupported = scan_locked_files(tmp_path)
        assert supported == []
        assert unsupported == []

    def test_subdirectories_are_not_counted(self, tmp_path: Path) -> None:
        (tmp_path / "subdir").mkdir()
        supported, unsupported = scan_locked_files(tmp_path)
        assert supported == []
        assert unsupported == []


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# scan_locked_files â€” extension case sensitivity
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestScanLockedFilesExtensionCase:
    def test_uppercase_extension_normalised_to_lowercase(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "archive.ZIP").write_bytes(b"")
        supported, _ = scan_locked_files(tmp_path)
        assert len(supported) == 1
        assert supported[0].extension == ".zip"

    def test_mixed_case_extension_detected(self, tmp_path: Path) -> None:
        (tmp_path / "doc.Pdf").write_bytes(b"")
        supported, _ = scan_locked_files(tmp_path)
        assert len(supported) == 1


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# scan_locked_files â€” error conditions
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestScanLockedFilesErrors:
    def test_missing_directory_raises_file_detection_error(
        self, tmp_path: Path
    ) -> None:
        missing = tmp_path / "nonexistent_dir"
        with pytest.raises(FileDetectionError, match="not found"):
            scan_locked_files(missing)

    def test_file_path_instead_of_dir_raises_error(self, tmp_path: Path) -> None:
        f = tmp_path / "not_a_dir.txt"
        f.write_bytes(b"")
        with pytest.raises(FileDetectionError):
            scan_locked_files(f)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# detect_locked_file â€” single file (no interactive picker)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestDetectLockedFileSingleFile:
    def test_returns_detected_file_for_single_supported_file(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "locked.zip").write_bytes(b"")
        result = detect_locked_file(tmp_path)
        assert isinstance(result, DetectedFile)
        assert result.extension == ".zip"

    def test_correct_path_returned(self, tmp_path: Path) -> None:
        f = tmp_path / "locked.pdf"
        f.write_bytes(b"")
        result = detect_locked_file(tmp_path)
        assert result.path == f

    def test_unsupported_only_raises_no_supported_error(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "video.mp4").write_bytes(b"")
        with pytest.raises(FileDetectionError, match="No supported"):
            detect_locked_file(tmp_path)

    def test_empty_directory_raises_file_detection_error(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(FileDetectionError):
            detect_locked_file(tmp_path)

    def test_readme_only_directory_raises_error(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("hi", encoding="utf-8")
        with pytest.raises(FileDetectionError):
            detect_locked_file(tmp_path)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# detect_file_from_path â€” manual file path detection
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestDetectFileFromPath:
    @pytest.mark.parametrize(
        ("filename", "expected_ext", "expected_format"),
        [
            ("archive.zip", ".zip", "ZIP Archive"),
            ("document.pdf", ".pdf", "PDF Document"),
            ("doc.docx", ".docx", "Word Document (OOXML)"),
            ("legacy.doc", ".doc", "Word Document (Legacy)"),
            ("sheet.xlsx", ".xlsx", "Excel Spreadsheet (OOXML)"),
            ("legacy.xls", ".xls", "Excel Spreadsheet (Legacy)"),
            ("slides.pptx", ".pptx", "PowerPoint Presentation (OOXML)"),
            ("legacy.ppt", ".ppt", "PowerPoint Presentation (Legacy)"),
            ("bundle.7z", ".7z", "7-Zip Archive"),
        ],
    )
    def test_all_supported_formats_detected(
        self,
        tmp_path: Path,
        filename: str,
        expected_ext: str,
        expected_format: str,
    ) -> None:
        target = tmp_path / filename
        target.write_bytes(b"dummy content")
        result = detect_file_from_path(target)
        assert isinstance(result, DetectedFile)
        assert result.path == target
        assert result.extension == expected_ext
        assert result.format_name == expected_format

    def test_string_path_input(self, tmp_path: Path) -> None:
        target = tmp_path / "test.docx"
        target.write_bytes(b"content")
        result = detect_file_from_path(str(target))
        assert result.path == target
        assert result.extension == ".docx"

    def test_path_with_spaces(self, tmp_path: Path) -> None:
        target = tmp_path / "My Important File.docx"
        target.write_bytes(b"content")
        result = detect_file_from_path(target)
        assert result.path == target
        assert result.extension == ".docx"

    def test_path_enclosed_in_double_quotes(self, tmp_path: Path) -> None:
        target = tmp_path / "My Doc.pdf"
        target.write_bytes(b"content")
        quoted_str = f'"{target}"'
        result = detect_file_from_path(quoted_str)
        assert result.path == target
        assert result.extension == ".pdf"

    def test_path_enclosed_in_single_quotes(self, tmp_path: Path) -> None:
        target = tmp_path / "My Doc.xlsx"
        target.write_bytes(b"content")
        quoted_str = f"'{target}'"
        result = detect_file_from_path(quoted_str)
        assert result.path == target
        assert result.extension == ".xlsx"

    def test_path_with_surrounding_whitespace(self, tmp_path: Path) -> None:
        target = tmp_path / "test.zip"
        target.write_bytes(b"content")
        padded_str = f"   {target}   "
        result = detect_file_from_path(padded_str)
        assert result.path == target
        assert result.extension == ".zip"

    def test_uppercase_extension(self, tmp_path: Path) -> None:
        target = tmp_path / "archive.ZIP"
        target.write_bytes(b"content")
        result = detect_file_from_path(target)
        assert result.extension == ".zip"
        assert result.format_name == "ZIP Archive"

    def test_empty_string_raises_error(self) -> None:
        with pytest.raises(FileDetectionError, match="No file path provided"):
            detect_file_from_path("")

    def test_whitespace_only_string_raises_error(self) -> None:
        with pytest.raises(FileDetectionError, match="No file path provided"):
            detect_file_from_path("   ")

    def test_nonexistent_file_raises_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist.docx"
        with pytest.raises(FileDetectionError, match="File not found"):
            detect_file_from_path(missing)

    def test_directory_path_raises_error(self, tmp_path: Path) -> None:
        with pytest.raises(FileDetectionError, match="directory, not a regular file"):
            detect_file_from_path(tmp_path)

    def test_unsupported_format_raises_error(self, tmp_path: Path) -> None:
        unsupported = tmp_path / "audio.mp3"
        unsupported.write_bytes(b"content")
        with pytest.raises(FileDetectionError, match="Unsupported file format"):
            detect_file_from_path(unsupported)

    def test_word_temporary_lock_file_raises_error(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "~$Important.docx"
        lock_file.write_bytes(b"lock")
        with pytest.raises(FileDetectionError, match=r"temporary lock file"):
            detect_file_from_path(lock_file)
