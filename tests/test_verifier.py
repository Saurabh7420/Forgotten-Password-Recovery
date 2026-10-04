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


def create_test_plain_doc(file_path: Path) -> Path:
    """Create a temporary valid unencrypted legacy Word (.doc) OLE document."""
    import struct
    from msoffcrypto.format.doc97 import FibBase, _packFibBase

    fibbase = FibBase(
        wIdent=0xA5EC, nFib=0x00C1, unused=0, lid=0x0409, pnNext=0,
        fDot=0, fGlsy=0, fComplex=0, fHasPic=0, cQuickSaves=0,
        fEncrypted=0, fWhichTblStm=1, fReadOnlyRecommended=0, fWriteReservation=0,
        fExtChar=0, fLoadOverride=0, fFarEast=0, nFibBack=0x00C1, fObfuscation=0,
        IKey=0, envr=0, fMac=0, fEmptySpecial=0, fLoadOverridePage=0,
        reserved1=0, reserved2=0, fSpare0=0, reserved3=0, reserved4=0,
        reserved5=0, reserved6=0,
    )
    fib_bytes = _packFibBase(fibbase).getvalue()
    word_doc_data = fib_bytes.ljust(4096, b"\x00")
    table_data = b"\x00" * 4096

    def dir_entry(name, entry_type, color, left, right, child, clsid, user_flags, time1, time2, start_sect, size_low, size_high):
        name_utf16 = name.encode("utf-16-le") + b"\x00\x00"
        name_buf = name_utf16.ljust(64, b"\x00")
        return struct.pack(
            "<64sHBBIII16sIQQIII",
            name_buf,
            len(name_utf16),
            entry_type,
            color,
            left,
            right,
            child,
            clsid,
            user_flags,
            time1,
            time2,
            start_sect,
            size_low,
            size_high,
        )

    root_ent = dir_entry("Root Entry", 5, 1, 0xFFFFFFFF, 0xFFFFFFFF, 1, b"\x00"*16, 0, 0, 0, 0xFFFFFFFE, 0, 0)
    word_ent = dir_entry("wordDocument", 2, 1, 0xFFFFFFFF, 2, 0xFFFFFFFF, b"\x00"*16, 0, 0, 0, 1, 4096, 0)
    tbl_ent = dir_entry("1Table", 2, 1, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, b"\x00"*16, 0, 0, 0, 9, 4096, 0)
    empty_ent = b"\x00" * 128
    dir_sector = root_ent + word_ent + tbl_ent + empty_ent

    fat = [0xFFFFFFFE]
    fat += list(range(2, 9)) + [0xFFFFFFFE]
    fat += list(range(10, 17)) + [0xFFFFFFFE]
    fat += [0xFFFFFFFD]
    fat += [0xFFFFFFFF] * (128 - len(fat))
    fat_sector = struct.pack("<128I", *fat)

    msat = [17] + [0xFFFFFFFF] * 108
    header = struct.pack(
        "<8s16sHHHHHHIIIIIIIIII109I",
        b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1",
        b"\x00"*16,
        0x003E,
        0x0003,
        0xFFFE,
        0x0009,
        0x0006,
        0, 0, 0,
        1,
        0,
        0,
        4096,
        0xFFFFFFFE,
        0,
        0xFFFFFFFE,
        0,
        *msat,
    )

    with open(file_path, "wb") as f:
        f.write(header)
        f.write(dir_sector)
        f.write(word_doc_data)
        f.write(table_data)
        f.write(fat_sector)
    return file_path


# ──────────────────────────────────────────────────────────────────────────────
# verify() — Legacy Word (.doc) verifier
# ──────────────────────────────────────────────────────────────────────────────


class TestVerifyDoc:
    """Tests for legacy Microsoft Word (.doc) verification."""

    def test_verify_doc_unencrypted_document(self, tmp_path: Path) -> None:
        doc_path = tmp_path / "unencrypted.doc"
        create_test_plain_doc(doc_path)
        assert verify(doc_path, "any_password") is True

    def test_verify_doc_correct_password(self, tmp_path: Path) -> None:
        doc_path = tmp_path / "locked.doc"
        create_test_plain_doc(doc_path)

        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            def mock_load_key(password):
                if password == "secret_doc_pass":
                    return True
                raise msoffcrypto.exceptions.InvalidKeyError("Invalid password")
            mock.load_key.side_effect = mock_load_key
            return mock

        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            assert verify(doc_path, "secret_doc_pass") is True

    def test_verify_doc_incorrect_password(self, tmp_path: Path) -> None:
        doc_path = tmp_path / "locked.doc"
        create_test_plain_doc(doc_path)

        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            mock.load_key.side_effect = msoffcrypto.exceptions.InvalidKeyError("Bad password")
            return mock

        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            assert verify(doc_path, "wrong_password") is False

    def test_verify_doc_case_sensitive(self, tmp_path: Path) -> None:
        doc_path = tmp_path / "locked.doc"
        create_test_plain_doc(doc_path)

        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            def mock_load_key(password):
                if password == "DocCasePass2026":
                    return True
                raise msoffcrypto.exceptions.InvalidKeyError("Bad password")
            mock.load_key.side_effect = mock_load_key
            return mock

        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            assert verify(doc_path, "doccasepass2026") is False
            assert verify(doc_path, "DocCasePass2026") is True

    def test_verify_doc_unicode_password(self, tmp_path: Path) -> None:
        doc_path = tmp_path / "locked.doc"
        create_test_plain_doc(doc_path)

        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            def mock_load_key(password):
                if password == "döc_🔒_pass":
                    return True
                raise msoffcrypto.exceptions.InvalidKeyError("Bad password")
            mock.load_key.side_effect = mock_load_key
            return mock

        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            assert verify(doc_path, "döc_🔒_pass") is True
            assert verify(doc_path, "wrong") is False

    def test_verify_doc_accepts_str_and_path(self, tmp_path: Path) -> None:
        doc_path = tmp_path / "test.doc"
        create_test_plain_doc(doc_path)
        assert verify(str(doc_path), "password") is True
        assert verify(doc_path, "password") is True

    def test_verify_doc_nonexistent_file_raises_verification_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.doc"
        with pytest.raises(VerificationError, match="Cannot read"):
            verify(missing, "any")

    def test_verify_doc_corrupt_file_raises_verification_error(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.doc"
        corrupt.write_bytes(b"not a valid doc file")
        with pytest.raises(VerificationError, match="Corrupt or invalid legacy Word document"):
            verify(corrupt, "any")

    def test_verify_doc_multiple_candidates_finds_match(self, tmp_path: Path) -> None:
        doc_path = tmp_path / "document.doc"
        create_test_plain_doc(doc_path)

        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            def mock_load_key(password):
                if password == "correct_candidate":
                    return True
                raise msoffcrypto.exceptions.InvalidKeyError("Bad password")
            mock.load_key.side_effect = mock_load_key
            return mock

        candidates = ["wrong1", "wrong2", "correct_candidate", "wrong3"]
        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            results = [verify(doc_path, c) for c in candidates]
            assert results == [False, False, True, False]

    def test_verify_doc_integration_with_candidate_loader(self, tmp_path: Path) -> None:
        from modules.candidate_loader import load_candidates
        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        pw_file = tmp_path / "passwords.txt"
        pw_file.write_text("# Clues\nspring2026\n# Target\ndoc_target_pass\nwinter2026\n", encoding="utf-8")

        doc_path = tmp_path / "legacy_report.doc"
        create_test_plain_doc(doc_path)

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            def mock_load_key(password):
                if password == "doc_target_pass":
                    return True
                raise msoffcrypto.exceptions.InvalidKeyError("Bad password")
            mock.load_key.side_effect = mock_load_key
            return mock

        candidates, stats = load_candidates(pw_file)
        assert stats.total_usable == 3

        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            matched = None
            for c in candidates:
                if verify(doc_path, c):
                    matched = c
                    break

            assert matched == "doc_target_pass"


def create_test_plain_xls(file_path: Path) -> Path:
    """Create a temporary valid unencrypted legacy Excel (.xls) OLE document."""
    import struct

    bof_content = struct.pack("<HHHHII", 0x0600, 0x0005, 0x0DBB, 0x0CC0, 0x00000000, 0x00000000)
    bof_record = struct.pack("<HH", 2057, len(bof_content)) + bof_content
    eof_record = struct.pack("<HH", 10, 0)
    workbook_data = (bof_record + eof_record).ljust(4096, b"\x00")

    def dir_entry(name, entry_type, color, left, right, child, clsid, user_flags, time1, time2, start_sect, size_low, size_high):
        name_utf16 = name.encode("utf-16-le") + b"\x00\x00"
        name_buf = name_utf16.ljust(64, b"\x00")
        return struct.pack(
            "<64sHBBIII16sIQQIII",
            name_buf,
            len(name_utf16),
            entry_type,
            color,
            left,
            right,
            child,
            clsid,
            user_flags,
            time1,
            time2,
            start_sect,
            size_low,
            size_high,
        )

    root_ent = dir_entry("Root Entry", 5, 1, 0xFFFFFFFF, 0xFFFFFFFF, 1, b"\x00"*16, 0, 0, 0, 0xFFFFFFFE, 0, 0)
    wb_ent = dir_entry("Workbook", 2, 1, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, b"\x00"*16, 0, 0, 0, 1, 4096, 0)
    empty_ent = b"\x00" * 128
    dir_sector = root_ent + wb_ent + empty_ent + empty_ent

    fat = [0xFFFFFFFE]
    fat += list(range(2, 9)) + [0xFFFFFFFE]
    fat += [0xFFFFFFFD]
    fat += [0xFFFFFFFF] * (128 - len(fat))
    fat_sector = struct.pack("<128I", *fat)

    msat = [9] + [0xFFFFFFFF] * 108
    header = struct.pack(
        "<8s16sHHHHHHIIIIIIIIII109I",
        b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1",
        b"\x00"*16,
        0x003E,
        0x0003,
        0xFFFE,
        0x0009,
        0x0006,
        0, 0, 0,
        1,
        0,
        0,
        4096,
        0xFFFFFFFE,
        0,
        0xFFFFFFFE,
        0,
        *msat,
    )

    with open(file_path, "wb") as f:
        f.write(header)
        f.write(dir_sector)
        f.write(workbook_data)
        f.write(fat_sector)
    return file_path


# ──────────────────────────────────────────────────────────────────────────────
# verify() — Legacy Excel (.xls) verifier
# ──────────────────────────────────────────────────────────────────────────────


class TestVerifyLegacyXls:
    """Tests for legacy Microsoft Excel (.xls) verification."""

    def test_verify_xls_unencrypted_document(self, tmp_path: Path) -> None:
        xls_path = tmp_path / "unencrypted.xls"
        create_test_plain_xls(xls_path)
        assert verify(xls_path, "any_password") is True

    def test_verify_xls_correct_password(self, tmp_path: Path) -> None:
        xls_path = tmp_path / "locked.xls"
        create_test_plain_xls(xls_path)

        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            def mock_load_key(password):
                if password == "secret_xls_pass":
                    return True
                raise msoffcrypto.exceptions.InvalidKeyError("Invalid password")
            mock.load_key.side_effect = mock_load_key
            return mock

        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            assert verify(xls_path, "secret_xls_pass") is True

    def test_verify_xls_incorrect_password(self, tmp_path: Path) -> None:
        xls_path = tmp_path / "locked.xls"
        create_test_plain_xls(xls_path)

        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            mock.load_key.side_effect = msoffcrypto.exceptions.InvalidKeyError("Bad password")
            return mock

        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            assert verify(xls_path, "wrong_password") is False

    def test_verify_xls_case_sensitive(self, tmp_path: Path) -> None:
        xls_path = tmp_path / "locked.xls"
        create_test_plain_xls(xls_path)

        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            def mock_load_key(password):
                if password == "XlsCasePass2026":
                    return True
                raise msoffcrypto.exceptions.InvalidKeyError("Bad password")
            mock.load_key.side_effect = mock_load_key
            return mock

        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            assert verify(xls_path, "xlscasepass2026") is False
            assert verify(xls_path, "XlsCasePass2026") is True

    def test_verify_xls_unicode_password(self, tmp_path: Path) -> None:
        xls_path = tmp_path / "locked.xls"
        create_test_plain_xls(xls_path)

        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            def mock_load_key(password):
                if password == "xlş_🔒_pass":
                    return True
                raise msoffcrypto.exceptions.InvalidKeyError("Bad password")
            mock.load_key.side_effect = mock_load_key
            return mock

        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            assert verify(xls_path, "xlş_🔒_pass") is True
            assert verify(xls_path, "wrong") is False

    def test_verify_xls_accepts_str_and_path(self, tmp_path: Path) -> None:
        xls_path = tmp_path / "test.xls"
        create_test_plain_xls(xls_path)
        assert verify(str(xls_path), "password") is True
        assert verify(xls_path, "password") is True

    def test_verify_xls_nonexistent_file_raises_verification_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.xls"
        with pytest.raises(VerificationError, match="Cannot read"):
            verify(missing, "any")

    def test_verify_xls_corrupt_file_raises_verification_error(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.xls"
        corrupt.write_bytes(b"not a valid xls file")
        with pytest.raises(VerificationError, match="Corrupt or invalid legacy Excel spreadsheet"):
            verify(corrupt, "any")

    def test_verify_xls_multiple_candidates_finds_match(self, tmp_path: Path) -> None:
        xls_path = tmp_path / "sheet.xls"
        create_test_plain_xls(xls_path)

        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            def mock_load_key(password):
                if password == "correct_candidate":
                    return True
                raise msoffcrypto.exceptions.InvalidKeyError("Bad password")
            mock.load_key.side_effect = mock_load_key
            return mock

        candidates = ["wrong1", "wrong2", "correct_candidate", "wrong3"]
        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            results = [verify(xls_path, c) for c in candidates]
            assert results == [False, False, True, False]

    def test_verify_xls_integration_with_candidate_loader(self, tmp_path: Path) -> None:
        from modules.candidate_loader import load_candidates
        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        pw_file = tmp_path / "passwords.txt"
        pw_file.write_text("# Clues\nspring2026\n# Target\nxls_target_pass\nwinter2026\n", encoding="utf-8")

        xls_path = tmp_path / "legacy_finances.xls"
        create_test_plain_xls(xls_path)

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            def mock_load_key(password):
                if password == "xls_target_pass":
                    return True
                raise msoffcrypto.exceptions.InvalidKeyError("Bad password")
            mock.load_key.side_effect = mock_load_key
            return mock

        candidates, stats = load_candidates(pw_file)
        assert stats.total_usable == 3

        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            matched = None
            for c in candidates:
                if verify(xls_path, c):
                    matched = c
                    break

            assert matched == "xls_target_pass"


def create_test_plain_ppt(file_path: Path) -> Path:
    """Create a temporary valid unencrypted legacy PowerPoint (.ppt) OLE document."""
    import struct

    rh_cu = struct.pack("<HHI", 0x0000, 0x0FF6, 20)
    cu_body = struct.pack("<IIIHHBB2sI", 0x00000014, 0xE391C05F, 0, 0, 0x03F4, 3, 0, b"\x00\x00", 8)
    current_user_data = (rh_cu + cu_body).ljust(4096, b"\x00")

    rh_ue = struct.pack("<HHI", 0x0000, 0x0FF5, 28)
    ue_body = struct.pack("<IHBBIIIIH2s", 1, 0, 0, 3, 0, 0, 1, 1, 1, b"\x00\x00")
    ppt_doc_data = (rh_ue + ue_body).ljust(4096, b"\x00")

    def dir_entry(name, entry_type, color, left, right, child, clsid, user_flags, time1, time2, start_sect, size_low, size_high):
        name_utf16 = name.encode("utf-16-le") + b"\x00\x00"
        name_buf = name_utf16.ljust(64, b"\x00")
        return struct.pack(
            "<64sHBBIII16sIQQIII",
            name_buf,
            len(name_utf16),
            entry_type,
            color,
            left,
            right,
            child,
            clsid,
            user_flags,
            time1,
            time2,
            start_sect,
            size_low,
            size_high,
        )

    root_ent = dir_entry("Root Entry", 5, 1, 0xFFFFFFFF, 0xFFFFFFFF, 1, b"\x00"*16, 0, 0, 0, 0xFFFFFFFE, 0, 0)
    cu_ent = dir_entry("Current User", 2, 1, 0xFFFFFFFF, 2, 0xFFFFFFFF, b"\x00"*16, 0, 0, 0, 1, 4096, 0)
    ppt_ent = dir_entry("PowerPoint Document", 2, 1, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, b"\x00"*16, 0, 0, 0, 9, 4096, 0)
    empty_ent = b"\x00" * 128
    dir_sector = root_ent + cu_ent + ppt_ent + empty_ent

    fat = [0xFFFFFFFE]
    fat += list(range(2, 9)) + [0xFFFFFFFE]
    fat += list(range(10, 17)) + [0xFFFFFFFE]
    fat += [0xFFFFFFFD]
    fat += [0xFFFFFFFF] * (128 - len(fat))
    fat_sector = struct.pack("<128I", *fat)

    msat = [17] + [0xFFFFFFFF] * 108
    header = struct.pack(
        "<8s16sHHHHHHIIIIIIIIII109I",
        b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1",
        b"\x00"*16,
        0x003E,
        0x0003,
        0xFFFE,
        0x0009,
        0x0006,
        0, 0, 0,
        1,
        0,
        0,
        4096,
        0xFFFFFFFE,
        0,
        0xFFFFFFFE,
        0,
        *msat,
    )

    with open(file_path, "wb") as f:
        f.write(header)
        f.write(dir_sector)
        f.write(current_user_data)
        f.write(ppt_doc_data)
        f.write(fat_sector)
    return file_path


# ──────────────────────────────────────────────────────────────────────────────
# verify() — Legacy PowerPoint (.ppt) verifier
# ──────────────────────────────────────────────────────────────────────────────


class TestVerifyLegacyPpt:
    """Tests for legacy Microsoft PowerPoint (.ppt) verification."""

    def test_verify_ppt_unencrypted_document(self, tmp_path: Path) -> None:
        ppt_path = tmp_path / "unencrypted.ppt"
        create_test_plain_ppt(ppt_path)
        assert verify(ppt_path, "any_password") is True

    def test_verify_ppt_correct_password(self, tmp_path: Path) -> None:
        ppt_path = tmp_path / "locked.ppt"
        create_test_plain_ppt(ppt_path)

        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            def mock_load_key(password):
                if password == "secret_ppt_pass":
                    return True
                raise msoffcrypto.exceptions.InvalidKeyError("Invalid password")
            mock.load_key.side_effect = mock_load_key
            return mock

        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            assert verify(ppt_path, "secret_ppt_pass") is True

    def test_verify_ppt_incorrect_password(self, tmp_path: Path) -> None:
        ppt_path = tmp_path / "locked.ppt"
        create_test_plain_ppt(ppt_path)

        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            mock.load_key.side_effect = msoffcrypto.exceptions.InvalidKeyError("Bad password")
            return mock

        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            assert verify(ppt_path, "wrong_password") is False

    def test_verify_ppt_case_sensitive(self, tmp_path: Path) -> None:
        ppt_path = tmp_path / "locked.ppt"
        create_test_plain_ppt(ppt_path)

        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            def mock_load_key(password):
                if password == "PptCasePass2026":
                    return True
                raise msoffcrypto.exceptions.InvalidKeyError("Bad password")
            mock.load_key.side_effect = mock_load_key
            return mock

        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            assert verify(ppt_path, "pptcasepass2026") is False
            assert verify(ppt_path, "PptCasePass2026") is True

    def test_verify_ppt_unicode_password(self, tmp_path: Path) -> None:
        ppt_path = tmp_path / "locked.ppt"
        create_test_plain_ppt(ppt_path)

        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            def mock_load_key(password):
                if password == "ppt_🔒_pass":
                    return True
                raise msoffcrypto.exceptions.InvalidKeyError("Bad password")
            mock.load_key.side_effect = mock_load_key
            return mock

        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            assert verify(ppt_path, "ppt_🔒_pass") is True
            assert verify(ppt_path, "wrong") is False

    def test_verify_ppt_accepts_str_and_path(self, tmp_path: Path) -> None:
        ppt_path = tmp_path / "test.ppt"
        create_test_plain_ppt(ppt_path)
        assert verify(str(ppt_path), "password") is True
        assert verify(ppt_path, "password") is True

    def test_verify_ppt_nonexistent_file_raises_verification_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.ppt"
        with pytest.raises(VerificationError, match="Cannot read"):
            verify(missing, "any")

    def test_verify_ppt_corrupt_file_raises_verification_error(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.ppt"
        corrupt.write_bytes(b"not a valid ppt file")
        with pytest.raises(VerificationError, match="Corrupt or invalid legacy PowerPoint presentation"):
            verify(corrupt, "any")

    def test_verify_ppt_multiple_candidates_finds_match(self, tmp_path: Path) -> None:
        ppt_path = tmp_path / "deck.ppt"
        create_test_plain_ppt(ppt_path)

        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            def mock_load_key(password):
                if password == "correct_candidate":
                    return True
                raise msoffcrypto.exceptions.InvalidKeyError("Bad password")
            mock.load_key.side_effect = mock_load_key
            return mock

        candidates = ["wrong1", "wrong2", "correct_candidate", "wrong3"]
        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            results = [verify(ppt_path, c) for c in candidates]
            assert results == [False, False, True, False]

    def test_verify_ppt_integration_with_candidate_loader(self, tmp_path: Path) -> None:
        from modules.candidate_loader import load_candidates
        from unittest.mock import MagicMock, patch
        import msoffcrypto.exceptions

        pw_file = tmp_path / "passwords.txt"
        pw_file.write_text("# Clues\nspring2026\n# Target\nppt_target_pass\nwinter2026\n", encoding="utf-8")

        ppt_path = tmp_path / "legacy_slides.ppt"
        create_test_plain_ppt(ppt_path)

        def mock_office_file(f):
            mock = MagicMock()
            mock.is_encrypted.return_value = True
            def mock_load_key(password):
                if password == "ppt_target_pass":
                    return True
                raise msoffcrypto.exceptions.InvalidKeyError("Bad password")
            mock.load_key.side_effect = mock_load_key
            return mock

        candidates, stats = load_candidates(pw_file)
        assert stats.total_usable == 3

        with patch("msoffcrypto.OfficeFile", side_effect=mock_office_file):
            matched = None
            for c in candidates:
                if verify(ppt_path, c):
                    matched = c
                    break

            assert matched == "ppt_target_pass"


def create_test_plain_7z(file_path: Path) -> Path:
    """Create a temporary unencrypted 7-Zip archive using py7zr."""
    import py7zr

    with py7zr.SevenZipFile(file_path, "w") as archive:
        archive.writestr("plain.txt", "Sample unencrypted 7z content")
    return file_path


def create_test_encrypted_7z(
    file_path: Path, password: str = "sevenzippass123", header_encryption: bool = True
) -> Path:
    """Create a temporary encrypted 7-Zip archive using py7zr."""
    import py7zr

    with py7zr.SevenZipFile(
        file_path, "w", password=password, header_encryption=header_encryption
    ) as archive:
        archive.writestr("secret.txt", "Sample confidential 7z payload")
    return file_path


# ──────────────────────────────────────────────────────────────────────────────
# verify() — 7-Zip Archive (.7z) verifier
# ──────────────────────────────────────────────────────────────────────────────


class TestVerify7z:
    """Tests for 7-Zip (.7z) archive verification using py7zr."""

    def test_verify_7z_encrypted_header_correct_password(self, tmp_path: Path) -> None:
        archive_path = tmp_path / "locked_header.7z"
        create_test_encrypted_7z(archive_path, password="secret_7z_pass", header_encryption=True)
        assert verify(archive_path, "secret_7z_pass") is True

    def test_verify_7z_encrypted_header_incorrect_password(self, tmp_path: Path) -> None:
        archive_path = tmp_path / "locked_header.7z"
        create_test_encrypted_7z(archive_path, password="secret_7z_pass", header_encryption=True)
        assert verify(archive_path, "wrong_password") is False

    def test_verify_7z_encrypted_payload_correct_password(self, tmp_path: Path) -> None:
        archive_path = tmp_path / "locked_payload.7z"
        create_test_encrypted_7z(archive_path, password="secret_7z_pass", header_encryption=False)
        assert verify(archive_path, "secret_7z_pass") is True

    def test_verify_7z_encrypted_payload_incorrect_password(self, tmp_path: Path) -> None:
        archive_path = tmp_path / "locked_payload.7z"
        create_test_encrypted_7z(archive_path, password="secret_7z_pass", header_encryption=False)
        assert verify(archive_path, "wrong_password") is False

    def test_verify_7z_unencrypted_archive(self, tmp_path: Path) -> None:
        archive_path = tmp_path / "unencrypted.7z"
        create_test_plain_7z(archive_path)
        assert verify(archive_path, "any_password") is True

    def test_verify_7z_case_sensitive(self, tmp_path: Path) -> None:
        archive_path = tmp_path / "locked.7z"
        create_test_encrypted_7z(archive_path, password="SevenZipPass2026")
        assert verify(archive_path, "sevenzippass2026") is False
        assert verify(archive_path, "SevenZipPass2026") is True

    def test_verify_7z_unicode_password(self, tmp_path: Path) -> None:
        archive_path = tmp_path / "locked.7z"
        create_test_encrypted_7z(archive_path, password="7z_🔒_pass")
        assert verify(archive_path, "7z_🔒_pass") is True
        assert verify(archive_path, "wrong") is False

    def test_verify_7z_accepts_str_and_path(self, tmp_path: Path) -> None:
        archive_path = tmp_path / "test.7z"
        create_test_plain_7z(archive_path)
        assert verify(str(archive_path), "password") is True
        assert verify(archive_path, "password") is True

    def test_verify_7z_nonexistent_file_raises_verification_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.7z"
        with pytest.raises(VerificationError, match="Cannot read"):
            verify(missing, "any")

    def test_verify_7z_corrupt_file_raises_verification_error(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.7z"
        corrupt.write_bytes(b"not a valid 7z archive header")
        with pytest.raises(VerificationError, match="Corrupt or invalid 7-Zip archive"):
            verify(corrupt, "any")

    def test_verify_7z_multiple_candidates_finds_match(self, tmp_path: Path) -> None:
        archive_path = tmp_path / "archive.7z"
        create_test_encrypted_7z(archive_path, password="correct_candidate")
        candidates = ["wrong1", "wrong2", "correct_candidate", "wrong3"]

        results = [verify(archive_path, c) for c in candidates]
        assert results == [False, False, True, False]

    def test_verify_7z_integration_with_candidate_loader(self, tmp_path: Path) -> None:
        from modules.candidate_loader import load_candidates

        pw_file = tmp_path / "passwords.txt"
        pw_file.write_text("# Clues\nspring2026\n# Target\n7z_target_pass\nwinter2026\n", encoding="utf-8")

        archive_path = tmp_path / "backup.7z"
        create_test_encrypted_7z(archive_path, password="7z_target_pass")

        candidates, stats = load_candidates(pw_file)
        assert stats.total_usable == 3

        matched = None
        for c in candidates:
            if verify(archive_path, c):
                matched = c
                break

        assert matched == "7z_target_pass"


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
