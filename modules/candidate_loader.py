"""
candidate_loader.py
Loads, cleans, and deduplicates password candidates from a text file.

File format
-----------
- One candidate password per line.
- Lines whose first non-whitespace character is ``#`` are treated as comments
  and are silently skipped.
- Blank / whitespace-only lines are silently skipped.
- Duplicate candidates (after stripping surrounding whitespace) are removed
  while preserving the original first-occurrence order.
- File must be UTF-8 encoded. Characters that cannot be decoded are replaced
  with the Unicode replacement character (U+FFFD) rather than raising an error,
  and a warning is printed so the user can fix their file.

Raises
------
CandidateLoadError
    If the file is missing, unreadable at the OS level, or contains zero
    usable candidates after all filtering.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────────────
# Public exceptions
# ──────────────────────────────────────────────────────────────────────────────


class CandidateLoadError(Exception):
    """Raised when the candidate list cannot be loaded or is unusable."""


# ──────────────────────────────────────────────────────────────────────────────
# Stats dataclass
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class CandidateStats:
    """Counts collected while loading the candidate file."""

    total_raw: int = 0          # Total lines in the file (including blanks/comments)
    blank_lines: int = 0        # Lines that were blank or whitespace-only
    comment_lines: int = 0      # Lines whose first character was '#'
    duplicates_removed: int = 0 # Candidates removed because they appeared before
    total_usable: int = 0       # Final count of unique, non-blank, non-comment candidates


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def load_candidates(path: str | Path) -> tuple[list[str], CandidateStats]:
    """
    Load and validate the password candidate list.

    Parameters
    ----------
    path:
        Path to the ``passwords.txt`` file.

    Returns
    -------
    candidates:
        Ordered, deduplicated list of candidate password strings.
    stats:
        A :class:`CandidateStats` instance summarising the load operation.

    Raises
    ------
    CandidateLoadError
        If the file is missing, cannot be read, or contains no usable
        candidates after filtering blanks, comments, and duplicates.
    """
    path = Path(path)

    # ── Existence check ───────────────────────────────────────────────────────
    if not path.exists():
        raise CandidateLoadError(
            f"Password list not found: '{path}'\n"
            "  → Create 'password_list/passwords.txt' with one candidate per line.\n"
            "  → See the sample template in passwords.txt at the project root."
        )

    # ── Read file ─────────────────────────────────────────────────────────────
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise CandidateLoadError(
            f"Cannot read '{path}': {exc}"
        ) from exc

    # Warn if replacement characters were introduced (indicates encoding issues)
    if "\ufffd" in content:
        warnings.warn(
            f"'{path}' contains bytes that are not valid UTF-8. "
            "Affected characters have been replaced with '?'. "
            "Re-save the file as UTF-8 for best results.",
            UserWarning,
            stacklevel=2,
        )

    raw_lines = content.splitlines()
    stats = CandidateStats(total_raw=len(raw_lines))

    candidates: list[str] = []
    seen: set[str] = set()

    for line in raw_lines:
        stripped = line.strip()

        if not stripped:
            stats.blank_lines += 1
            continue

        if stripped.startswith("#"):
            stats.comment_lines += 1
            continue

        if stripped in seen:
            stats.duplicates_removed += 1
            continue

        seen.add(stripped)
        candidates.append(stripped)

    stats.total_usable = len(candidates)

    if stats.total_usable == 0:
        raise CandidateLoadError(
            f"'{path}' contains no usable candidates after removing blanks "
            "and comments.\n"
            "  → Add at least one password candidate (one per line)."
        )

    return candidates, stats
