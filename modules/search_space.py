"""
search_space.py
Exact, deterministic search-space calculator for Version 2 hint-based recovery.

Overview & Rules Specification
------------------------------
This module defines and computes the exact candidate search space produced by the
three-stage progressive hint recovery model without guessing or approximation.

Rules Specification:
--------------------
1. Token Categories:
   - Base tokens (B): user's `name` and `word` entries.
   - Number tokens (D): user's `number` entries.
   - Special characters (S): user's `special_character` entries.
   - Prefix tokens (P): user's `prefix` entries.
   - Suffix tokens (U): user's `suffix` entries.

2. Stage 1 — Direct Hint Search:
   Direct, canonical concatenations of remembered components:
   - Single tokens: each base `b`, each number `d`.
   - Direct pairings & triplets:
     - `b + d`, `d + b`, `b + s`, `s + b`
     - `b + d + s`, `b + s + d`, `s + b + d`, `d + b + s`
   - Prefix and suffix wrappers:
     - `p + cand`, `cand + u`, `p + cand + u` for all `p in P`, `u in U`.

3. Stage 2 — Hint Transformation Search:
   Standard case variations, memorable l33t substitutions, and standard delimiters:
   - Case variants on bases: `lower()`, `upper()`, `capitalize()`, `swapcase()`.
   - Standard delimiter insertions between components: `_`, `-`, `.`, ` `
     (e.g. `b + delim + d`, `b + delim + d + s`, `b + s + delim + d`).
   - Single-character memorable substitutions on text:
     `a/A -> @`, `e/E -> 3`, `i/I -> 1`, `o/O -> 0`, `s/S -> $`.
   - Prefix and suffix wrappers on all Stage 2 transformed patterns.

4. Stage 3 — Expanded Hint Search:
   Cross-product permutations, compound tokens, and expansions:
   - Compound base pairings: `b1 + b2`, `b1 + b2 + d`, `b1 + delim + b2`, `b1 + delim + b2 + d`.
   - Reversed tokens: `b[::-1]`, `d[::-1]`.
   - Repeated number sequences: `d + d`.
   - 2-digit expansions for 4-digit years (e.g. `2024 -> 24`).
   - Prefix and suffix wrappers on all Stage 3 compound patterns.

Deduplication & Length Filtering:
---------------------------------
- Every distinct string is attributed strictly to its earliest stage (Stage 1 -> Stage 2 -> Stage 3).
- Strings not satisfying `min_length <= len(string) <= max_length` are excluded.
- Duplicate generation paths produce a count of 1 for that distinct string.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Set

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from modules.hint_collector import HintModel


# ──────────────────────────────────────────────────────────────────────────────
# Result Model
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SearchSpaceResult:
    """
    Detailed search space metrics computed from a HintModel.
    """

    stage1_count: int
    stage2_count: int
    stage3_count: int
    total_distinct_count: int
    is_finite: bool
    is_unbounded: bool
    active_categories: list[str]
    min_length: int | None
    max_length: int | None


# ──────────────────────────────────────────────────────────────────────────────
# Transformation Helpers
# ──────────────────────────────────────────────────────────────────────────────

_DELIMITERS: tuple[str, ...] = ("_", "-", ".", " ")

_L33T_MAP: tuple[tuple[str, str], ...] = (
    ("a", "@"),
    ("A", "@"),
    ("e", "3"),
    ("E", "3"),
    ("i", "1"),
    ("I", "1"),
    ("o", "0"),
    ("O", "0"),
    ("s", "$"),
    ("S", "$"),
)


def _apply_l33t(text: str) -> set[str]:
    """Generate simple single-character and full l33t variations of text."""
    results: set[str] = set()
    mutated = text
    for orig, sub in _L33T_MAP:
        if orig in text:
            results.add(text.replace(orig, sub))
            mutated = mutated.replace(orig, sub)
    if mutated != text:
        results.add(mutated)
    return results


def _apply_affixes(
    candidates: set[str],
    prefixes: list[str],
    suffixes: list[str],
) -> set[str]:
    """Apply prefix and suffix wrappers (including one-character boundary overlap) to a set of candidates."""
    wrapped: set[str] = set(candidates)

    if prefixes:
        for p in prefixes:
            for c in candidates:
                wrapped.add(f"{p}{c}")
                if c and p and p[-1].lower() == c[0].lower():
                    wrapped.add(f"{p}{c[1:]}")

    if suffixes:
        for u in suffixes:
            for c in candidates:
                wrapped.add(f"{c}{u}")

    if prefixes and suffixes:
        for p in prefixes:
            for u in suffixes:
                for c in candidates:
                    wrapped.add(f"{p}{c}{u}")
                    if c and p and p[-1].lower() == c[0].lower():
                        wrapped.add(f"{p}{c[1:]}{u}")

    return wrapped


def _filter_by_length(
    candidates: set[str],
    min_len: int | None,
    max_len: int | None,
) -> set[str]:
    """Filter candidates to satisfy min_length and max_length bounds."""
    return {
        c
        for c in candidates
        if (min_len is None or len(c) >= min_len)
        and (max_len is None or len(c) <= max_len)
    }


def _get_unique_bases(hints: HintModel) -> list[str]:
    """Return ordered, unique base tokens across name and word categories."""
    bases: list[str] = []
    seen: set[str] = set()
    for b in (hints.name or []) + (hints.word or []):
        if b not in seen:
            seen.add(b)
            bases.append(b)
    return bases


# ──────────────────────────────────────────────────────────────────────────────
# Stage Enumeration Logic (Canonical Definitions)
# ──────────────────────────────────────────────────────────────────────────────


def enumerate_stage1_candidates(hints: HintModel) -> set[str]:
    """Generate all raw Stage 1 candidate strings."""
    bases = _get_unique_bases(hints)
    numbers: list[str] = hints.number or []
    specials: list[str] = hints.special_character or []
    prefixes: list[str] = hints.prefix or []
    suffixes: list[str] = hints.suffix or []

    s1_raw: set[str] = set()

    # 1. Base tokens alone
    for b in bases:
        s1_raw.add(b)

    # 2. Numbers alone
    for d in numbers:
        s1_raw.add(d)

    # 3. Pairings
    for b in bases:
        for d in numbers:
            s1_raw.add(f"{b}{d}")
            s1_raw.add(f"{d}{b}")
        for s in specials:
            s1_raw.add(f"{b}{s}")
            s1_raw.add(f"{s}{b}")

    # 4. Triplets
    for b in bases:
        for d in numbers:
            for s in specials:
                s1_raw.add(f"{b}{d}{s}")
                s1_raw.add(f"{b}{s}{d}")
                s1_raw.add(f"{s}{b}{d}")
                s1_raw.add(f"{d}{b}{s}")

    # 5. Affix applications
    return _apply_affixes(s1_raw, prefixes, suffixes)


def enumerate_stage2_candidates(hints: HintModel) -> set[str]:
    """Generate all raw Stage 2 candidate strings."""
    bases = _get_unique_bases(hints)
    numbers: list[str] = hints.number or []
    specials: list[str] = hints.special_character or []
    prefixes: list[str] = hints.prefix or []
    suffixes: list[str] = hints.suffix or []

    s2_raw: set[str] = set()

    # 1. Casing variations on bases
    cased_bases: set[str] = set()
    for b in bases:
        cased_bases.add(b.lower())
        cased_bases.add(b.upper())
        cased_bases.add(b.capitalize())
        cased_bases.add(b.swapcase())

    for cb in cased_bases:
        s2_raw.add(cb)
        for d in numbers:
            s2_raw.add(f"{cb}{d}")
            s2_raw.add(f"{d}{cb}")
        for s in specials:
            s2_raw.add(f"{cb}{s}")
            s2_raw.add(f"{s}{cb}")
        for d in numbers:
            for s in specials:
                s2_raw.add(f"{cb}{d}{s}")
                s2_raw.add(f"{cb}{s}{d}")

    # 2. Delimiter insertions
    for b in bases:
        for delim in _DELIMITERS:
            for d in numbers:
                s2_raw.add(f"{b}{delim}{d}")
                s2_raw.add(f"{d}{delim}{b}")
                for s in specials:
                    s2_raw.add(f"{b}{delim}{d}{s}")
                    s2_raw.add(f"{b}{s}{delim}{d}")
                    s2_raw.add(f"{b}{delim}{s}{delim}{d}")

    # 3. L33t substitutions
    l33t_bases: set[str] = set()
    for b in bases:
        l33t_bases.update(_apply_l33t(b))

    for lb in l33t_bases:
        s2_raw.add(lb)
        for d in numbers:
            s2_raw.add(f"{lb}{d}")
        for s in specials:
            s2_raw.add(f"{lb}{s}")
        for d in numbers:
            for s in specials:
                s2_raw.add(f"{lb}{s}{d}")
                s2_raw.add(f"{lb}{d}{s}")

    return _apply_affixes(s2_raw, prefixes, suffixes)


def enumerate_stage3_candidates(hints: HintModel) -> set[str]:
    """Generate all raw Stage 3 candidate strings."""
    bases = _get_unique_bases(hints)
    numbers: list[str] = hints.number or []
    specials: list[str] = hints.special_character or []
    prefixes: list[str] = hints.prefix or []
    suffixes: list[str] = hints.suffix or []

    s3_raw: set[str] = set()

    # 1. Compound base combinations (b1 + b2)
    for b1 in bases:
        for b2 in bases:
            if b1 != b2 or len(bases) == 1:
                s3_raw.add(f"{b1}{b2}")
                for d in numbers:
                    s3_raw.add(f"{b1}{b2}{d}")
                for delim in _DELIMITERS:
                    s3_raw.add(f"{b1}{delim}{b2}")
                    for d in numbers:
                        s3_raw.add(f"{b1}{delim}{b2}{delim}{d}")
                        s3_raw.add(f"{b1}{delim}{b2}{d}")

    # 2. Reversed tokens
    for b in bases:
        if len(b) > 1:
            rev_b = b[::-1]
            s3_raw.add(rev_b)
            for d in numbers:
                s3_raw.add(f"{rev_b}{d}")

    # 3. Repeated / 2-digit numbers
    for d in numbers:
        if len(d) > 1:
            s3_raw.add(f"{d}{d}")
            for b in bases:
                s3_raw.add(f"{b}{d}{d}")
        if len(d) == 4 and d.isdigit():
            two_digit = d[2:]
            s3_raw.add(two_digit)
            for b in bases:
                s3_raw.add(f"{b}{two_digit}")
                for s in specials:
                    s3_raw.add(f"{b}{s}{two_digit}")
                    s3_raw.add(f"{b}{two_digit}{s}")

    return _apply_affixes(s3_raw, prefixes, suffixes)


# ──────────────────────────────────────────────────────────────────────────────
# Public Search Space Calculation API
# ──────────────────────────────────────────────────────────────────────────────


def calculate_search_space(hints: HintModel) -> SearchSpaceResult:
    """
    Calculate the exact, non-overlapping search space across all three stages.

    Parameters
    ----------
    hints:
        The validated HintModel instance containing user-supplied hints and lengths.

    Returns
    -------
    SearchSpaceResult
        Exact counts for Stage 1, Stage 2, Stage 3, and total distinct count.
    """
    if not hints.has_any_hints:
        return SearchSpaceResult(
            stage1_count=0,
            stage2_count=0,
            stage3_count=0,
            total_distinct_count=0,
            is_finite=True,
            is_unbounded=False,
            active_categories=[],
            min_length=hints.min_length,
            max_length=hints.max_length,
        )

    # 1. Enumerate and length-filter Stage 1
    raw_s1 = enumerate_stage1_candidates(hints)
    s1 = _filter_by_length(raw_s1, hints.min_length, hints.max_length)

    # 2. Enumerate and length-filter Stage 2 (excluding existing S1)
    raw_s2 = enumerate_stage2_candidates(hints)
    filtered_s2 = _filter_by_length(raw_s2, hints.min_length, hints.max_length)
    s2 = filtered_s2 - s1

    # 3. Enumerate and length-filter Stage 3 (excluding existing S1 & S2)
    raw_s3 = enumerate_stage3_candidates(hints)
    filtered_s3 = _filter_by_length(raw_s3, hints.min_length, hints.max_length)
    s3 = filtered_s3 - s1 - s2

    total_distinct = len(s1) + len(s2) + len(s3)

    return SearchSpaceResult(
        stage1_count=len(s1),
        stage2_count=len(s2),
        stage3_count=len(s3),
        total_distinct_count=total_distinct,
        is_finite=True,
        is_unbounded=False,
        active_categories=list(hints.active_fields.keys()),
        min_length=hints.min_length,
        max_length=hints.max_length,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Display Helper
# ──────────────────────────────────────────────────────────────────────────────


def display_search_space_analysis(
    result: SearchSpaceResult,
    console: Console | None = None,
) -> None:
    """Render the search space analysis to the terminal."""
    console = console or Console()

    console.print()
    console.print(
        Panel(
            Text("SEARCH SPACE ANALYSIS", justify="center", style="bold cyan"),
            expand=False,
            border_style="cyan",
            width=50,
        )
    )

    if result.is_unbounded:
        console.print(
            Panel(
                "[bold red]Total search space: UNBOUNDED[/bold red]\n\n"
                "Additional constraints are required before\n"
                "the complete search space can be calculated.",
                border_style="red",
                expand=False,
            )
        )
        return

    console.print("[bold cyan]Stage 1 — Direct Hint Search[/bold cyan]")
    console.print(f"  Candidates : [bold green]{result.stage1_count:,}[/bold green]\n")

    console.print("[bold cyan]Stage 2 — Hint Transformation Search[/bold cyan]")
    console.print(f"  Candidates : [bold green]{result.stage2_count:,}[/bold green]\n")

    console.print("[bold cyan]Stage 3 — Expanded Hint Search[/bold cyan]")
    console.print(f"  Candidates : [bold green]{result.stage3_count:,}[/bold green]\n")

    console.print(f"{'─' * 50}\n")
    console.print(
        f"  Total distinct candidates : [bold yellow]{result.total_distinct_count:,}[/bold yellow]\n"
    )
    console.print(f"{'═' * 50}\n")
