"""
tests/test_verifier.py
Unit tests for modules/verifier.py

Tests cover:
- Format registry completeness
- get_handler() dispatch and case-insensitivity
- verify() ZIP verification using standard library zipfile (Phase 2)
- verify() raising NotImplementedError for remaining Phase 1 stubs
- verify() raising UnsupportedFormatError for unknown extensions
- Exception type hierarchy
"""

from __future__ import annotations

import io
import zipfile
import zlib
from pathlib import Path
from unittest.mock import patch

import pytest

from modules.verifier import (
    SUPPORTED_FORMATS,
    UnsupportedFormatError,
    VerificationError,
    get_handler,
    verify,
)


# ──────────────────────────────────────────────────────────────────────────────
# SUPPORTED_FORMATS registry
# ──────────────────────────────────────────────────────────────────────────────


class TestSupportedFormats:
    def test_zip_registered(self) -> None:
        assert ".zip" in SUPPORTED_FORMATS

    def test_pdf_registered(self) -> None:
        assert ".pdf" in SUPPORTED_FORMATS

    def test_docx_registered(self) -> None:
        assert ".docx" in SUPPORTED_FORMATS

    def test_xlsx_registered(self) -> None:
        assert ".xlsx" in SUPPORTED_FORMATS

    def test_pptx_registered(self) -> None:
        assert ".pptx" in SUPPORTED_FORMATS

    def test_doc_registered(self) -> None:
        assert ".doc" in SUPPORTED_FORMATS

    def test_xls_registered(self) -> None:
        assert ".xls" in SUPPORTED_FORMATS

    def test_ppt_registered(self) -> None:
        assert ".ppt" in SUPPORTED_FORMATS

    def test_7z_registered(self) -> None:
        assert ".7z" in SUPPORTED_FORMATS

    def test_exactly_nine_formats(self) -> None:
        assert len(SUPPORTED_FORMATS) == 9

    def test_all_keys_start_with_dot(self) -> None:
        for ext in SUPPORTED_FORMATS:
            assert ext.startswith("."), f"'{ext}' must start with '.'"

    def test_all_format_names_non_empty(self) -> None:
        for ext, name in SUPPORTED_FORMATS.items():
            assert name.strip(), f"Format name for '{ext}' must not be empty"

    def test_exe_not_registered(self) -> None:
        assert ".exe" not in SUPPORTED_FORMATS

    def test_txt_not_registered(self) -> None:
        assert ".txt" not in SUPPORTED_FORMATS


# ──────────────────────────────────────────────────────────────────────────────
# get_handler()
# ──────────────────────────────────────────────────────────────────────────────


class TestGetHandler:
    def test_returns_callable_for_zip(self) -> None:
        handler = get_handler(".zip")
        assert callable(handler)

    def test_returns_callable_for_pdf(self) -> None:
        handler = get_handler(".pdf")
        assert callable(handler)

    def test_returns_callable_for_docx(self) -> None:
        handler = get_handler(".docx")
        assert callable(handler)

    def test_returns_callable_for_7z(self) -> None:
        handler = get_handler(".7z")
        assert callable(handler)

    def test_all_registered_extensions_have_callable_handler(self) -> None:
        for ext in SUPPORTED_FORMATS:
            handler = get_handler(ext)
            assert callable(handler), f"Handler for '{ext}' must be callable"

    def test_uppercase_extension_normalised(self) -> None:
        handler_lower = get_handler(".zip")
        handler_upper = get_handler(".ZIP")
        assert handler_lower is handler_upper

    def test_mixed_case_extension_normalised(self) -> None:
        handler = get_handler(".Pdf")
        assert callable(handler)

    def test_unsupported_extension_raises_unsupported_format_error(self) -> None:
        with pytest.raises(UnsupportedFormatError):
            get_handler(".exe")

    def test_unsupported_txt_raises_error(self) -> None:
        with pytest.raises(UnsupportedFormatError):
            get_handler(".txt")

    def test_empty_extension_raises_error(self) -> None:
        with pytest.raises(UnsupportedFormatError):
            get_handler("")

    def test_error_message_contains_extension(self) -> None:
        with pytest.raises(UnsupportedFormatError, match=r"\.xyz"):
            get_handler(".xyz")


# ──────────────────────────────────────────────────────────────────────────────
# verify() — ZIP verifier (Phase 2)
# ──────────────────────────────────────────────────────────────────────────────


class TestVerifyZip:
    """Tests for standard-library zipfile verification handler."""

    def test_verify_zip_unencrypted_archive(self, tmp_path: Path) -> None:
        unlocked = tmp_path / "plain.zip"
        with zipfile.ZipFile(unlocked, "w") as zf:
            zf.writestr("hello.txt", "plain content")
        assert verify(unlocked, "any_password") is True

    def test_verify_zip_empty_unencrypted_archive(self, tmp_path: Path) -> None:
        empty_zip = tmp_path / "empty.zip"
        with zipfile.ZipFile(empty_zip, "w") as zf:
            pass
        assert verify(empty_zip, "any_pass") is True

    def test_verify_zip_accepts_str_and_path(self, tmp_path: Path) -> None:
        zip_file = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr("doc.txt", "sample data")
        assert verify(str(zip_file), "password1") is True
        assert verify(zip_file, "password1") is True

    def test_verify_zip_nonexistent_file_raises_verification_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.zip"
        with pytest.raises(VerificationError, match="Cannot read"):
            verify(missing, "any")

    def test_verify_zip_corrupt_file_raises_verification_error(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.zip"
        corrupt.write_bytes(b"not a valid zip file at all")
        with pytest.raises(VerificationError, match="Corrupt or invalid ZIP archive"):
            verify(corrupt, "any")

    def test_verify_zip_correct_password_via_zipfile_open(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "protected.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("secret.txt", "confidential")

        expected_pwd = b"secret123"

        def mock_open(member, mode="r", pwd=None):
            if pwd == expected_pwd:
                return io.BytesIO(b"decrypted content")
            raise RuntimeError("Bad password for file")

        with patch("zipfile.ZipFile.infolist") as mock_infolist, patch("zipfile.ZipFile.open", side_effect=mock_open):
            info = zipfile.ZipInfo("secret.txt")
            info.flag_bits = 0x1  # mark as encrypted
            mock_infolist.return_value = [info]

            assert verify(zip_path, "secret123") is True
            assert verify(zip_path, "wrong_pass") is False

    def test_verify_zip_bad_password_runtime_error_returns_false(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "protected.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("secret.txt", "confidential")

        with patch("zipfile.ZipFile.infolist") as mock_infolist, patch(
            "zipfile.ZipFile.open", side_effect=RuntimeError("Bad password for file")
        ):
            info = zipfile.ZipInfo("secret.txt")
            info.flag_bits = 0x1  # encrypted
            mock_infolist.return_value = [info]

            assert verify(zip_path, "incorrect_candidate") is False

    def test_verify_zip_crc_bad_zip_file_returns_false(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "protected.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("secret.txt", "confidential")

        with patch("zipfile.ZipFile.infolist") as mock_infolist, patch(
            "zipfile.ZipFile.open", side_effect=zipfile.BadZipFile("Bad CRC-32 for file")
        ):
            info = zipfile.ZipInfo("secret.txt")
            info.flag_bits = 0x1
            mock_infolist.return_value = [info]

            assert verify(zip_path, "candidate_with_bad_crc") is False

    def test_verify_zip_decompression_error_returns_false(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "protected.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("secret.txt", "confidential")

        with patch("zipfile.ZipFile.infolist") as mock_infolist, patch(
            "zipfile.ZipFile.open", side_effect=zlib.error("Decompression failed")
        ):
            info = zipfile.ZipInfo("secret.txt")
            info.flag_bits = 0x1
            mock_infolist.return_value = [info]

            assert verify(zip_path, "candidate_causing_zlib_error") is False

    def test_verify_zip_integration_with_candidate_loader(self, tmp_path: Path) -> None:
        from modules.candidate_loader import load_candidates

        # Write passwords.txt
        pw_file = tmp_path / "passwords.txt"
        pw_file.write_text("# Clues\nspring2026\n# More clues\nsummer2026\nwinter2026\n", encoding="utf-8")

        zip_path = tmp_path / "archive.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data.txt", "content")

        target_password = b"summer2026"

        def mock_open(member, mode="r", pwd=None):
            if pwd == target_password:
                return io.BytesIO(b"success")
            raise RuntimeError("Bad password for file")

        with patch("zipfile.ZipFile.infolist") as mock_infolist, patch("zipfile.ZipFile.open", side_effect=mock_open):
            info = zipfile.ZipInfo("data.txt")
            info.flag_bits = 0x1
            mock_infolist.return_value = [info]

            candidates, stats = load_candidates(pw_file)
            assert stats.total_usable == 3

            matched = None
            for c in candidates:
                if verify(zip_path, c):
                    matched = c
                    break

            assert matched == "summer2026"


def create_test_encrypted_pdf(
    pdf_path: Path,
    password: str = "pdfpass123",
    owner_password: str = "ownerpass123",
) -> Path:
    """Create a temporary test encrypted PDF using pikepdf."""
    import pikepdf

    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(100, 100))
    enc = pikepdf.Encryption(owner=owner_password, user=password, R=6)
    pdf.save(pdf_path, encryption=enc)
    pdf.close()
    return pdf_path


def create_test_plain_pdf(pdf_path: Path) -> Path:
    """Create a temporary unencrypted PDF using pikepdf."""
    import pikepdf

    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(100, 100))
    pdf.save(pdf_path)
    pdf.close()
    return pdf_path


# ──────────────────────────────────────────────────────────────────────────────
# verify() — PDF verifier (Phase 3)
# ──────────────────────────────────────────────────────────────────────────────


class TestVerifyPdf:
    """Tests for the pikepdf PDF verification handler."""

    def test_verify_pdf_correct_password(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "locked.pdf"
        create_test_encrypted_pdf(pdf_path, password="secret_pdf_pass")
        assert verify(pdf_path, "secret_pdf_pass") is True

    def test_verify_pdf_incorrect_password(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "locked.pdf"
        create_test_encrypted_pdf(pdf_path, password="secret_pdf_pass")
        assert verify(pdf_path, "wrong_password") is False

    def test_verify_pdf_empty_password_fails_for_encrypted(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "locked.pdf"
        create_test_encrypted_pdf(pdf_path, password="secret_pdf_pass")
        assert verify(pdf_path, "") is False

    def test_verify_pdf_case_sensitive(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "locked.pdf"
        create_test_encrypted_pdf(pdf_path, password="CaseSensitivePass")
        assert verify(pdf_path, "casesensitivepass") is False
        assert verify(pdf_path, "CaseSensitivePass") is True

    def test_verify_pdf_unicode_password(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "locked_unicode.pdf"
        create_test_encrypted_pdf(pdf_path, password="pàsswörd_🔒_2026")
        assert verify(pdf_path, "pàsswörd_🔒_2026") is True
        assert verify(pdf_path, "wrong") is False

    def test_verify_pdf_unencrypted_document(self, tmp_path: Path) -> None:
        plain_pdf = tmp_path / "plain.pdf"
        create_test_plain_pdf(plain_pdf)
        assert verify(plain_pdf, "any_password") is True

    def test_verify_pdf_accepts_str_and_path(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "test.pdf"
        create_test_encrypted_pdf(pdf_path, password="my_pdf_pass")
        assert verify(str(pdf_path), "my_pdf_pass") is True
        assert verify(pdf_path, "my_pdf_pass") is True

    def test_verify_pdf_nonexistent_file_raises_verification_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.pdf"
        with pytest.raises(VerificationError, match="Cannot read"):
            verify(missing, "any")

    def test_verify_pdf_corrupt_file_raises_verification_error(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.pdf"
        corrupt.write_bytes(b"not a valid pdf header")
        with pytest.raises(VerificationError, match="Corrupt or invalid PDF document"):
            verify(corrupt, "any")

    def test_verify_pdf_multiple_candidates_finds_match(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "document.pdf"
        create_test_encrypted_pdf(pdf_path, password="correct_candidate")
        candidates = ["wrong1", "wrong2", "correct_candidate", "wrong3"]

        results = [verify(pdf_path, c) for c in candidates]
        assert results == [False, False, True, False]

    def test_verify_pdf_integration_with_candidate_loader(self, tmp_path: Path) -> None:
        from modules.candidate_loader import load_candidates

        pw_file = tmp_path / "passwords.txt"
        pw_file.write_text("# Clues\nspring2026\n# Target\npdf_secure_pass\nwinter2026\n", encoding="utf-8")

        pdf_path = tmp_path / "statement.pdf"
        create_test_encrypted_pdf(pdf_path, password="pdf_secure_pass")

        candidates, stats = load_candidates(pw_file)
        assert stats.total_usable == 3

        matched = None
        for c in candidates:
            if verify(pdf_path, c):
                matched = c
                break

        assert matched == "pdf_secure_pass"


def create_test_plain_ooxml(file_path: Path) -> Path:
    """Create a temporary unencrypted OOXML file (docx, xlsx, or pptx)."""
    with zipfile.ZipFile(file_path, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
        )
    return file_path


def create_test_encrypted_ooxml(
    file_path: Path, password: str = "officepass123"
) -> Path:
    """Create a temporary test encrypted OOXML file using msoffcrypto."""
    import msoffcrypto

    plain_buf = io.BytesIO()
    with zipfile.ZipFile(plain_buf, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
        )
    plain_buf.seek(0)
    office_file = msoffcrypto.OfficeFile(plain_buf)
    with open(file_path, "wb") as f:
        office_file.encrypt(password, f)
    return file_path


# ──────────────────────────────────────────────────────────────────────────────
# verify() — Modern Office (DOCX / XLSX / PPTX) verifiers (Phase 4)
# ──────────────────────────────────────────────────────────────────────────────


class TestVerifyDocx:
    """Tests for DOCX password verification using msoffcrypto-tool."""

    def test_verify_docx_correct_password(self, tmp_path: Path) -> None:
        docx_path = tmp_path / "locked.docx"
        create_test_encrypted_ooxml(docx_path, password="secret_docx_pass")
        assert verify(docx_path, "secret_docx_pass") is True

    def test_verify_docx_incorrect_password(self, tmp_path: Path) -> None:
        docx_path = tmp_path / "locked.docx"
        create_test_encrypted_ooxml(docx_path, password="secret_docx_pass")
        assert verify(docx_path, "wrong_password") is False

    def test_verify_docx_empty_password_fails_for_encrypted(self, tmp_path: Path) -> None:
        docx_path = tmp_path / "locked.docx"
        create_test_encrypted_ooxml(docx_path, password="secret_docx_pass")
        assert verify(docx_path, "") is False

    def test_verify_docx_case_sensitive(self, tmp_path: Path) -> None:
        docx_path = tmp_path / "locked.docx"
        create_test_encrypted_ooxml(docx_path, password="DocxPassword2026")
        assert verify(docx_path, "docxpassword2026") is False
        assert verify(docx_path, "DocxPassword2026") is True

    def test_verify_docx_unicode_password(self, tmp_path: Path) -> None:
        docx_path = tmp_path / "locked_unicode.docx"
        create_test_encrypted_ooxml(docx_path, password="wörd_🔒_2026")
        assert verify(docx_path, "wörd_🔒_2026") is True
        assert verify(docx_path, "wrong") is False

    def test_verify_docx_unencrypted_document(self, tmp_path: Path) -> None:
        plain_docx = tmp_path / "plain.docx"
        create_test_plain_ooxml(plain_docx)
        assert verify(plain_docx, "any_password") is True

    def test_verify_docx_accepts_str_and_path(self, tmp_path: Path) -> None:
        docx_path = tmp_path / "test.docx"
        create_test_encrypted_ooxml(docx_path, password="my_docx_pass")
        assert verify(str(docx_path), "my_docx_pass") is True
        assert verify(docx_path, "my_docx_pass") is True

    def test_verify_docx_nonexistent_file_raises_verification_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.docx"
        with pytest.raises(VerificationError, match="Cannot read"):
            verify(missing, "any")

    def test_verify_docx_corrupt_file_raises_verification_error(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.docx"
        corrupt.write_bytes(b"not a valid docx file content")
        with pytest.raises(VerificationError, match="Corrupt or invalid Office document"):
            verify(corrupt, "any")

    def test_verify_docx_multiple_candidates_finds_match(self, tmp_path: Path) -> None:
        docx_path = tmp_path / "document.docx"
        create_test_encrypted_ooxml(docx_path, password="correct_candidate")
        candidates = ["wrong1", "wrong2", "correct_candidate", "wrong3"]

        results = [verify(docx_path, c) for c in candidates]
        assert results == [False, False, True, False]

    def test_verify_docx_integration_with_candidate_loader(self, tmp_path: Path) -> None:
        from modules.candidate_loader import load_candidates

        pw_file = tmp_path / "passwords.txt"
        pw_file.write_text("# Clues\nspring2026\n# Target\ndocx_secure_pass\nwinter2026\n", encoding="utf-8")

        docx_path = tmp_path / "report.docx"
        create_test_encrypted_ooxml(docx_path, password="docx_secure_pass")

        candidates, stats = load_candidates(pw_file)
        assert stats.total_usable == 3

        matched = None
        for c in candidates:
            if verify(docx_path, c):
                matched = c
                break

        assert matched == "docx_secure_pass"


class TestVerifyXlsx:
    """Tests for XLSX password verification using msoffcrypto-tool."""

    def test_verify_xlsx_correct_password(self, tmp_path: Path) -> None:
        xlsx_path = tmp_path / "locked.xlsx"
        create_test_encrypted_ooxml(xlsx_path, password="secret_xlsx_pass")
        assert verify(xlsx_path, "secret_xlsx_pass") is True

    def test_verify_xlsx_incorrect_password(self, tmp_path: Path) -> None:
        xlsx_path = tmp_path / "locked.xlsx"
        create_test_encrypted_ooxml(xlsx_path, password="secret_xlsx_pass")
        assert verify(xlsx_path, "wrong_password") is False

    def test_verify_xlsx_unencrypted_spreadsheet(self, tmp_path: Path) -> None:
        plain_xlsx = tmp_path / "plain.xlsx"
        create_test_plain_ooxml(plain_xlsx)
        assert verify(plain_xlsx, "any_password") is True

    def test_verify_xlsx_accepts_str_and_path(self, tmp_path: Path) -> None:
        xlsx_path = tmp_path / "test.xlsx"
        create_test_encrypted_ooxml(xlsx_path, password="my_xlsx_pass")
        assert verify(str(xlsx_path), "my_xlsx_pass") is True
        assert verify(xlsx_path, "my_xlsx_pass") is True

    def test_verify_xlsx_multiple_candidates_finds_match(self, tmp_path: Path) -> None:
        xlsx_path = tmp_path / "data.xlsx"
        create_test_encrypted_ooxml(xlsx_path, password="correct_candidate")
        candidates = ["wrong1", "wrong2", "correct_candidate", "wrong3"]

        results = [verify(xlsx_path, c) for c in candidates]
        assert results == [False, False, True, False]

    def test_verify_xlsx_integration_with_candidate_loader(self, tmp_path: Path) -> None:
        from modules.candidate_loader import load_candidates

        pw_file = tmp_path / "passwords.txt"
        pw_file.write_text("# Clues\nspring2026\n# Target\nxlsx_secure_pass\nwinter2026\n", encoding="utf-8")

        xlsx_path = tmp_path / "finances.xlsx"
        create_test_encrypted_ooxml(xlsx_path, password="xlsx_secure_pass")

        candidates, stats = load_candidates(pw_file)
        assert stats.total_usable == 3

        matched = None
        for c in candidates:
            if verify(xlsx_path, c):
                matched = c
                break

        assert matched == "xlsx_secure_pass"


class TestVerifyPptx:
    """Tests for PPTX password verification using msoffcrypto-tool."""

    def test_verify_pptx_correct_password(self, tmp_path: Path) -> None:
        pptx_path = tmp_path / "locked.pptx"
        create_test_encrypted_ooxml(pptx_path, password="secret_pptx_pass")
        assert verify(pptx_path, "secret_pptx_pass") is True

    def test_verify_pptx_incorrect_password(self, tmp_path: Path) -> None:
        pptx_path = tmp_path / "locked.pptx"
        create_test_encrypted_ooxml(pptx_path, password="secret_pptx_pass")
        assert verify(pptx_path, "wrong_password") is False

    def test_verify_pptx_unencrypted_presentation(self, tmp_path: Path) -> None:
        plain_pptx = tmp_path / "plain.pptx"
        create_test_plain_ooxml(plain_pptx)
        assert verify(plain_pptx, "any_password") is True

    def test_verify_pptx_accepts_str_and_path(self, tmp_path: Path) -> None:
        pptx_path = tmp_path / "test.pptx"
        create_test_encrypted_ooxml(pptx_path, password="my_pptx_pass")
        assert verify(str(pptx_path), "my_pptx_pass") is True
        assert verify(pptx_path, "my_pptx_pass") is True

    def test_verify_pptx_multiple_candidates_finds_match(self, tmp_path: Path) -> None:
        pptx_path = tmp_path / "deck.pptx"
        create_test_encrypted_ooxml(pptx_path, password="correct_candidate")
        candidates = ["wrong1", "wrong2", "correct_candidate", "wrong3"]

        results = [verify(pptx_path, c) for c in candidates]
        assert results == [False, False, True, False]

    def test_verify_pptx_integration_with_candidate_loader(self, tmp_path: Path) -> None:
        from modules.candidate_loader import load_candidates

        pw_file = tmp_path / "passwords.txt"
        pw_file.write_text("# Clues\nspring2026\n# Target\npptx_secure_pass\nwinter2026\n", encoding="utf-8")

        pptx_path = tmp_path / "slides.pptx"
        create_test_encrypted_ooxml(pptx_path, password="pptx_secure_pass")

        candidates, stats = load_candidates(pw_file)
        assert stats.total_usable == 3

        matched = None
        for c in candidates:
            if verify(pptx_path, c):
                matched = c
                break

        assert matched == "pptx_secure_pass"


# ──────────────────────────────────────────────────────────────────────────────
# verify() — Phase 1 stubs (remaining formats)
# ──────────────────────────────────────────────────────────────────────────────


class TestVerifyPhase1Stubs:
    """Remaining Phase 1 handlers must raise NotImplementedError."""

    def _make_fake_file(self, tmp_path: Path, extension: str) -> Path:
        f = tmp_path / f"test{extension}"
        f.write_bytes(b"")
        return f

    @pytest.mark.parametrize(
        "extension",
        [".doc", ".xls", ".ppt", ".7z"],
    )
    def test_stub_raises_not_implemented(
        self, tmp_path: Path, extension: str
    ) -> None:
        fake = self._make_fake_file(tmp_path, extension)
        with pytest.raises(NotImplementedError):
            verify(fake, "any_password")

    def test_verify_accepts_string_path(self, tmp_path: Path) -> None:
        fake = tmp_path / "test.doc"
        fake.write_bytes(b"")
        with pytest.raises(NotImplementedError):
            verify(str(fake), "password")

    def test_verify_accepts_path_object(self, tmp_path: Path) -> None:
        fake = tmp_path / "test.7z"
        fake.write_bytes(b"")
        with pytest.raises(NotImplementedError):
            verify(fake, "password")


# ──────────────────────────────────────────────────────────────────────────────
# verify() — unsupported format
# ──────────────────────────────────────────────────────────────────────────────


class TestVerifyUnsupportedFormat:
    def test_unsupported_extension_raises_unsupported_format_error(
        self, tmp_path: Path
    ) -> None:
        fake = tmp_path / "test.exe"
        fake.write_bytes(b"")
        with pytest.raises(UnsupportedFormatError):
            verify(fake, "password")

    def test_unsupported_format_error_is_subclass_of_verification_error(
        self,
    ) -> None:
        assert issubclass(UnsupportedFormatError, VerificationError)

    def test_verification_error_is_subclass_of_exception(self) -> None:
        assert issubclass(VerificationError, Exception)


# ──────────────────────────────────────────────────────────────────────────────
# Exception hierarchy
# ──────────────────────────────────────────────────────────────────────────────


class TestExceptionHierarchy:
    def test_unsupported_format_error_is_verification_error(self) -> None:
        exc = UnsupportedFormatError("test")
        assert isinstance(exc, VerificationError)

    def test_verification_error_is_exception(self) -> None:
        exc = VerificationError("test")
        assert isinstance(exc, Exception)
