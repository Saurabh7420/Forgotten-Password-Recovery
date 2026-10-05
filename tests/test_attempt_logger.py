"""
test_attempt_logger.py
Automated test suite for single session attempts file logging in Version 2.
"""

from __future__ import annotations

import re
from pathlib import Path
import pytest

from modules.attempt_logger import AttemptLogger
from modules.hint_collector import HintModel
from modules.search_stages import execute_progressive_recovery


# ──────────────────────────────────────────────────────────────────────────────
# 1. Filename & Directory Creation Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_attempts_file_naming_convention(tmp_path):
    """Filename must match attempts_YYYYMMDD_HHMMSS.txt."""
    fixed_ts = "20261005_120000"
    logger = AttemptLogger(output_dir=tmp_path, timestamp=fixed_ts)
    logger.close()

    expected_file = tmp_path / "attempts_20261005_120000.txt"
    assert logger.file_path == expected_file
    assert expected_file.exists()


def test_default_timestamp_format_regex(tmp_path):
    """Default timestamp generated at runtime must match regex format."""
    with AttemptLogger(output_dir=tmp_path) as logger:
        logger.log_attempt("TestCandidate1")

    filename = logger.file_path.name
    match = re.match(r"^attempts_\d{8}_\d{6}\.txt$", filename)
    assert match is not None, f"Filename '{filename}' does not match expected format"


def test_creates_output_directory_if_missing(tmp_path):
    """AttemptLogger ensures parent output directory exists."""
    nested_dir = tmp_path / "deeply" / "nested" / "results"
    assert not nested_dir.exists()

    with AttemptLogger(output_dir=nested_dir, timestamp="20261005_120100") as logger:
        logger.log_attempt("Cand1")

    assert nested_dir.exists()
    assert logger.file_path.exists()


def test_two_separate_sessions_create_distinct_files(tmp_path):
    """Two distinct recovery sessions create separate timestamped files."""
    session1 = AttemptLogger(output_dir=tmp_path, timestamp="20261005_100000")
    session1.log_attempt("CandA")
    session1.close()

    session2 = AttemptLogger(output_dir=tmp_path, timestamp="20261005_200000")
    session2.log_attempt("CandB")
    session2.close()

    files = sorted([f.name for f in tmp_path.iterdir() if f.is_file()])
    assert files == ["attempts_20261005_100000.txt", "attempts_20261005_200000.txt"]


# ──────────────────────────────────────────────────────────────────────────────
# 2. Content, Formatting & UTF-8 Encoding Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_attempts_written_one_per_line(tmp_path):
    """Multiple logged attempts are written exactly one candidate per line."""
    candidates = ["Saniya123", "Saniya@123", "Saniya_123", "saniya123"]

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_120200") as logger:
        for c in candidates:
            logger.log_attempt(c)

    content = logger.file_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    assert lines == candidates
    assert logger.attempts_count == 4


def test_utf8_encoding_supported(tmp_path):
    """Unicode candidates (accents, symbols, emojis) are encoded cleanly in UTF-8."""
    candidates = ["P@sswørd_123", "München!2024", "Saniya🌟7070", "日本Tokyo#"]

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_120300") as logger:
        for c in candidates:
            logger.log_attempt(c)

    content = logger.file_path.read_text(encoding="utf-8")
    assert content.splitlines() == candidates


def test_no_extra_decorations_or_labels(tmp_path):
    """The attempts file contains only raw candidate strings without stage labels or metadata."""
    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_120400") as logger:
        logger.log_attempt("Alpha1")
        logger.log_attempt("Beta2")

    content = logger.file_path.read_text(encoding="utf-8")
    assert content == "Alpha1\nBeta2\n"


# ──────────────────────────────────────────────────────────────────────────────
# 3. Lifecycle, Exceptions & Flush Safety Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_logger_context_manager_auto_closes(tmp_path):
    """Context manager properly flushes and closes the file handle upon exit."""
    logger_ref = None
    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_120500") as logger:
        logger_ref = logger
        logger.log_attempt("Testing123")
        assert not logger._closed

    assert logger_ref._closed
    assert logger_ref._file is None


def test_logging_to_closed_logger_raises_runtime_error(tmp_path):
    """Logging to a closed logger raises RuntimeError."""
    logger = AttemptLogger(output_dir=tmp_path, timestamp="20261005_120600")
    logger.close()

    with pytest.raises(RuntimeError, match="Cannot log attempt to a closed AttemptLogger"):
        logger.log_attempt("TooLate")


def test_exception_during_session_preserves_flushed_attempts(tmp_path):
    """Already-written attempts remain safely persisted even if an exception interrupts the session."""
    logger = AttemptLogger(output_dir=tmp_path, timestamp="20261005_120700")

    try:
        logger.log_attempt("AttemptOne")
        logger.log_attempt("AttemptTwo")
        raise ValueError("Simulated unexpected crash during verification")
    except ValueError:
        logger.close()

    lines = logger.file_path.read_text(encoding="utf-8").splitlines()
    assert lines == ["AttemptOne", "AttemptTwo"]


# ──────────────────────────────────────────────────────────────────────────────
# 4. Pipeline Integration & Stage Behavior Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_progressive_recovery_writes_exactly_one_file_across_all_stages(tmp_path):
    """All 3 stages append to the SAME single attempts file in the session."""
    hints = HintModel(
        name=["Saniya"],
        number=["7070"],
        special_character=["@"],
    )

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_120800") as logger:
        res = execute_progressive_recovery(
            target_file="test.docx",
            hints=hints,
            verify_fn=lambda f, p: False,  # Exhaust all 3 stages
            attempt_logger=logger,
        )

    # Exactly 1 file in the results directory
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    assert files[0] == logger.file_path

    # File contains attempts matching total_attempts
    logged_lines = logger.file_path.read_text(encoding="utf-8").splitlines()
    assert len(logged_lines) == res.total_attempts
    assert len(logged_lines) > 0


def test_order_of_attempts_matches_verifier_invocation_order(tmp_path):
    """The order in the attempts file must exactly mirror the order received by the verifier."""
    hints = HintModel(
        name=["Alice"],
        number=["100"],
    )

    verifier_received: list[str] = []

    def mock_verify(target_file, cand):
        verifier_received.append(cand)
        return False

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_120900") as logger:
        execute_progressive_recovery(
            target_file="test.pdf",
            hints=hints,
            verify_fn=mock_verify,
            attempt_logger=logger,
        )

    logged_attempts = logger.file_path.read_text(encoding="utf-8").splitlines()
    assert logged_attempts == verifier_received


def test_successful_candidate_is_logged_and_no_candidates_logged_after_success(tmp_path):
    """The winning candidate is logged in the file, and no candidates after success are logged."""
    hints = HintModel(
        name=["Saniya"],
        number=["7070"],
        special_character=["@"],
    )
    target_pwd = "Saniya7070@"

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_121000") as logger:
        res = execute_progressive_recovery(
            target_file="test.zip",
            hints=hints,
            verify_fn=lambda f, p: p == target_pwd,
            attempt_logger=logger,
        )

    assert res.success is True
    assert res.found_password == target_pwd

    logged_lines = logger.file_path.read_text(encoding="utf-8").splitlines()
    assert len(logged_lines) == res.total_attempts
    # Winning candidate must be the last entry in the attempts file
    assert logged_lines[-1] == target_pwd


def test_no_candidate_logged_if_hints_are_empty(tmp_path):
    """Empty hint model yields 0 attempts and creates no logged attempts."""
    hints = HintModel()

    with AttemptLogger(output_dir=tmp_path, timestamp="20261005_121100") as logger:
        res = execute_progressive_recovery(
            target_file="test.zip",
            hints=hints,
            verify_fn=lambda f, p: True,
            attempt_logger=logger,
        )

    assert res.total_attempts == 0
    logged_lines = logger.file_path.read_text(encoding="utf-8").splitlines()
    assert logged_lines == []
