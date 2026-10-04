"""
tests/test_candidate_loader.py
Unit tests for modules/candidate_loader.py
"""

import warnings
from pathlib import Path

import pytest

from modules.candidate_loader import (
    CandidateLoadError,
    CandidateStats,
    load_candidates,
)


# ──────────────────────────────────────────────────────────────────────────────
# Happy-path tests
# ──────────────────────────────────────────────────────────────────────────────


class TestLoadCandidatesHappyPath:
    def test_loads_simple_valid_file(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
        candidates, stats = load_candidates(f)
        assert candidates == ["alpha", "beta", "gamma"]

    def test_returns_candidate_stats_instance(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("one\n", encoding="utf-8")
        _, stats = load_candidates(f)
        assert isinstance(stats, CandidateStats)

    def test_total_usable_matches_candidate_count(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("a\nb\nc\n", encoding="utf-8")
        candidates, stats = load_candidates(f)
        assert stats.total_usable == len(candidates) == 3

    def test_accepts_path_as_string(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("hello\n", encoding="utf-8")
        candidates, _ = load_candidates(str(f))
        assert candidates == ["hello"]


# ──────────────────────────────────────────────────────────────────────────────
# Blank-line handling
# ──────────────────────────────────────────────────────────────────────────────


class TestBlankLineHandling:
    def test_blank_lines_are_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("alpha\n\n\nbeta\n", encoding="utf-8")
        candidates, _ = load_candidates(f)
        assert candidates == ["alpha", "beta"]

    def test_blank_line_count_tracked(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("alpha\n\n\nbeta\n", encoding="utf-8")
        _, stats = load_candidates(f)
        assert stats.blank_lines == 2

    def test_whitespace_only_lines_counted_as_blank(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("alpha\n   \n\t\nbeta\n", encoding="utf-8")
        candidates, stats = load_candidates(f)
        assert candidates == ["alpha", "beta"]
        assert stats.blank_lines == 2

    def test_leading_trailing_whitespace_stripped_from_candidates(
        self, tmp_path: Path
    ) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("  alpha  \n  beta\ngamma   \n", encoding="utf-8")
        candidates, _ = load_candidates(f)
        assert candidates == ["alpha", "beta", "gamma"]


# ──────────────────────────────────────────────────────────────────────────────
# Comment handling
# ──────────────────────────────────────────────────────────────────────────────


class TestCommentHandling:
    def test_comment_lines_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("# This is a comment\nalpha\n# Another\nbeta\n", encoding="utf-8")
        candidates, _ = load_candidates(f)
        assert candidates == ["alpha", "beta"]

    def test_comment_line_count_tracked(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("# c1\nalpha\n# c2\nbeta\n", encoding="utf-8")
        _, stats = load_candidates(f)
        assert stats.comment_lines == 2

    def test_inline_hash_not_treated_as_comment(self, tmp_path: Path) -> None:
        """Only lines whose first char is '#' are comments."""
        f = tmp_path / "passwords.txt"
        f.write_text("pass#word\n", encoding="utf-8")
        candidates, _ = load_candidates(f)
        assert candidates == ["pass#word"]

    def test_indented_hash_treated_as_comment(self, tmp_path: Path) -> None:
        """After stripping, a leading '#' is a comment regardless of indentation."""
        f = tmp_path / "passwords.txt"
        f.write_text("  # indented comment\nalpha\n", encoding="utf-8")
        candidates, stats = load_candidates(f)
        assert candidates == ["alpha"]
        assert stats.comment_lines == 1


# ──────────────────────────────────────────────────────────────────────────────
# Deduplication
# ──────────────────────────────────────────────────────────────────────────────


class TestDeduplication:
    def test_duplicates_removed(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("alpha\nbeta\nalpha\ngamma\nbeta\n", encoding="utf-8")
        candidates, _ = load_candidates(f)
        assert candidates == ["alpha", "beta", "gamma"]

    def test_first_occurrence_order_preserved(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("charlie\nalpha\nbeta\nalpha\ncharlie\n", encoding="utf-8")
        candidates, _ = load_candidates(f)
        assert candidates == ["charlie", "alpha", "beta"]

    def test_duplicate_count_tracked(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("a\nb\na\na\nb\n", encoding="utf-8")
        _, stats = load_candidates(f)
        assert stats.duplicates_removed == 3

    def test_no_duplicates_zero_removed(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("x\ny\nz\n", encoding="utf-8")
        _, stats = load_candidates(f)
        assert stats.duplicates_removed == 0


# ──────────────────────────────────────────────────────────────────────────────
# Stats completeness
# ──────────────────────────────────────────────────────────────────────────────


class TestStats:
    def test_total_raw_counts_all_lines(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("alpha\n# comment\n\nbeta\nalpha\n", encoding="utf-8")
        _, stats = load_candidates(f)
        assert stats.total_raw == 5

    def test_all_stat_fields_consistent(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        # 1 comment, 1 blank, 2 unique, 1 duplicate
        f.write_text("# comment\n\nalpha\nbeta\nalpha\n", encoding="utf-8")
        _, stats = load_candidates(f)
        assert stats.total_raw == 5
        assert stats.comment_lines == 1
        assert stats.blank_lines == 1
        assert stats.duplicates_removed == 1
        assert stats.total_usable == 2


# ──────────────────────────────────────────────────────────────────────────────
# Error conditions
# ──────────────────────────────────────────────────────────────────────────────


class TestErrorConditions:
    def test_missing_file_raises_candidate_load_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.txt"
        with pytest.raises(CandidateLoadError, match="not found"):
            load_candidates(missing)

    def test_empty_file_raises_candidate_load_error(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("", encoding="utf-8")
        with pytest.raises(CandidateLoadError):
            load_candidates(f)

    def test_only_blank_lines_raises_error(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("\n\n\n", encoding="utf-8")
        with pytest.raises(CandidateLoadError):
            load_candidates(f)

    def test_only_comments_raises_error(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("# comment 1\n# comment 2\n", encoding="utf-8")
        with pytest.raises(CandidateLoadError):
            load_candidates(f)

    def test_only_blanks_and_comments_raises_error(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("# comment\n\n# another\n   \n", encoding="utf-8")
        with pytest.raises(CandidateLoadError):
            load_candidates(f)


# ──────────────────────────────────────────────────────────────────────────────
# Encoding
# ──────────────────────────────────────────────────────────────────────────────


class TestEncoding:
    def test_utf8_special_characters_loaded(self, tmp_path: Path) -> None:
        f = tmp_path / "passwords.txt"
        f.write_text("pässwörd\nñoño\n中文密码\n", encoding="utf-8")
        candidates, stats = load_candidates(f)
        assert len(candidates) == 3
        assert "pässwörd" in candidates
        assert "中文密码" in candidates

    def test_invalid_bytes_replaced_not_raised(self, tmp_path: Path) -> None:
        """Invalid UTF-8 bytes should produce a warning, not an exception."""
        f = tmp_path / "passwords.txt"
        f.write_bytes(b"valid\xff\xfeinvalid\n")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            candidates, _ = load_candidates(f)
        # Should not raise; a UserWarning should be emitted
        assert any(issubclass(warning.category, UserWarning) for warning in w)
        assert len(candidates) >= 1
