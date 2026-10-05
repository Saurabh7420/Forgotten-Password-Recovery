"""
candidate_generator.py
Progressive, memory-efficient candidate password generator for Version 2 recovery.

Overview & Guarantees
---------------------
- Lazily generates candidate passwords one-by-one using Python generators (Iterator[str]).
- Implements the exact 3-stage specification defined in `modules/search_space.py`.
- Yields candidates in strict, deterministic stage order: Stage 1 -> Stage 2 -> Stage 3.
- Streams deduplicated candidates on the fly (each distinct password yielded at most once).
- Applies min_length and max_length boundary constraints dynamically.
- Zero network calls, zero disk writes, zero verifier invocations.
"""

from __future__ import annotations

from typing import Iterator, Set

from modules.hint_collector import HintModel
from modules.search_space import _DELIMITERS, _L33T_MAP, _get_unique_bases


def _apply_l33t_list(text: str) -> list[str]:
    """Generate ordered, unique single-character and full l33t variations of text."""
    results: list[str] = []
    seen: set[str] = {text}
    mutated = text

    for orig, sub in _L33T_MAP:
        if orig in text:
            variant = text.replace(orig, sub)
            if variant not in seen:
                seen.add(variant)
                results.append(variant)
            mutated = mutated.replace(orig, sub)

    if mutated not in seen:
        seen.add(mutated)
        results.append(mutated)

    return results


def _yield_affixes(
    candidate: str,
    prefixes: list[str],
    suffixes: list[str],
) -> Iterator[str]:
    """
    Yield candidate itself, followed by prefix/suffix wrappers (including one-character
    boundary overlap) in deterministic order.
    """
    yield candidate

    if prefixes:
        for p in prefixes:
            yield f"{p}{candidate}"
            if candidate and p and p[-1].lower() == candidate[0].lower():
                yield f"{p}{candidate[1:]}"

    if suffixes:
        for u in suffixes:
            yield f"{candidate}{u}"

    if prefixes and suffixes:
        for p in prefixes:
            for u in suffixes:
                yield f"{p}{candidate}{u}"
                if candidate and p and p[-1].lower() == candidate[0].lower():
                    yield f"{p}{candidate[1:]}{u}"


def _is_valid_length(cand: str, min_len: int | None, max_len: int | None) -> bool:
    """Return True if candidate string satisfies length boundaries."""
    length = len(cand)
    if min_len is not None and length < min_len:
        return False
    if max_len is not None and length > max_len:
        return False
    return True


# ──────────────────────────────────────────────────────────────────────────────
# Raw Stage Stream Generators
# ──────────────────────────────────────────────────────────────────────────────


def _stream_stage1_raw(hints: HintModel) -> Iterator[str]:
    """Stream all raw Stage 1 candidates in deterministic order."""
    bases = _get_unique_bases(hints)
    numbers: list[str] = hints.number or []
    specials: list[str] = hints.special_character or []
    prefixes: list[str] = hints.prefix or []
    suffixes: list[str] = hints.suffix or []

    # 1. Base tokens alone
    for b in bases:
        yield from _yield_affixes(b, prefixes, suffixes)

    # 2. Numbers alone
    for d in numbers:
        yield from _yield_affixes(d, prefixes, suffixes)

    # 3. Pairings
    for b in bases:
        for d in numbers:
            yield from _yield_affixes(f"{b}{d}", prefixes, suffixes)
            yield from _yield_affixes(f"{d}{b}", prefixes, suffixes)
        for s in specials:
            yield from _yield_affixes(f"{b}{s}", prefixes, suffixes)
            yield from _yield_affixes(f"{s}{b}", prefixes, suffixes)

    # 4. Triplets
    for b in bases:
        for d in numbers:
            for s in specials:
                yield from _yield_affixes(f"{b}{d}{s}", prefixes, suffixes)
                yield from _yield_affixes(f"{b}{s}{d}", prefixes, suffixes)
                yield from _yield_affixes(f"{s}{b}{d}", prefixes, suffixes)
                yield from _yield_affixes(f"{d}{b}{s}", prefixes, suffixes)


def _stream_stage2_raw(hints: HintModel) -> Iterator[str]:
    """Stream all raw Stage 2 candidates in deterministic order."""
    bases = _get_unique_bases(hints)
    numbers: list[str] = hints.number or []
    specials: list[str] = hints.special_character or []
    prefixes: list[str] = hints.prefix or []
    suffixes: list[str] = hints.suffix or []

    # 1. Casing variations on bases
    cased_bases: list[str] = []
    seen_cased: set[str] = set()
    for b in bases:
        for cased in (b.lower(), b.upper(), b.capitalize(), b.swapcase()):
            if cased not in seen_cased:
                seen_cased.add(cased)
                cased_bases.append(cased)

    for cb in cased_bases:
        yield from _yield_affixes(cb, prefixes, suffixes)
        for d in numbers:
            yield from _yield_affixes(f"{cb}{d}", prefixes, suffixes)
            yield from _yield_affixes(f"{d}{cb}", prefixes, suffixes)
        for s in specials:
            yield from _yield_affixes(f"{cb}{s}", prefixes, suffixes)
            yield from _yield_affixes(f"{s}{cb}", prefixes, suffixes)
        for d in numbers:
            for s in specials:
                yield from _yield_affixes(f"{cb}{d}{s}", prefixes, suffixes)
                yield from _yield_affixes(f"{cb}{s}{d}", prefixes, suffixes)

    # 2. Delimiter insertions
    for b in bases:
        for delim in _DELIMITERS:
            for d in numbers:
                yield from _yield_affixes(f"{b}{delim}{d}", prefixes, suffixes)
                yield from _yield_affixes(f"{d}{delim}{b}", prefixes, suffixes)
                for s in specials:
                    yield from _yield_affixes(f"{b}{delim}{d}{s}", prefixes, suffixes)
                    yield from _yield_affixes(f"{b}{s}{delim}{d}", prefixes, suffixes)
                    yield from _yield_affixes(f"{b}{delim}{s}{delim}{d}", prefixes, suffixes)

    # 3. L33t substitutions
    for b in bases:
        l33t_list = _apply_l33t_list(b)
        for lb in l33t_list:
            yield from _yield_affixes(lb, prefixes, suffixes)
            for d in numbers:
                yield from _yield_affixes(f"{lb}{d}", prefixes, suffixes)
            for s in specials:
                yield from _yield_affixes(f"{lb}{s}", prefixes, suffixes)
            for d in numbers:
                for s in specials:
                    yield from _yield_affixes(f"{lb}{s}{d}", prefixes, suffixes)
                    yield from _yield_affixes(f"{lb}{d}{s}", prefixes, suffixes)


def _stream_stage3_raw(hints: HintModel) -> Iterator[str]:
    """Stream all raw Stage 3 candidates in deterministic order."""
    bases = _get_unique_bases(hints)
    numbers: list[str] = hints.number or []
    specials: list[str] = hints.special_character or []
    prefixes: list[str] = hints.prefix or []
    suffixes: list[str] = hints.suffix or []

    # 1. Compound base combinations (b1 + b2)
    for b1 in bases:
        for b2 in bases:
            if b1 != b2 or len(bases) == 1:
                yield from _yield_affixes(f"{b1}{b2}", prefixes, suffixes)
                for d in numbers:
                    yield from _yield_affixes(f"{b1}{b2}{d}", prefixes, suffixes)
                for delim in _DELIMITERS:
                    yield from _yield_affixes(f"{b1}{delim}{b2}", prefixes, suffixes)
                    for d in numbers:
                        yield from _yield_affixes(f"{b1}{delim}{b2}{delim}{d}", prefixes, suffixes)
                        yield from _yield_affixes(f"{b1}{delim}{b2}{d}", prefixes, suffixes)

    # 2. Reversed tokens
    for b in bases:
        if len(b) > 1:
            rev_b = b[::-1]
            yield from _yield_affixes(rev_b, prefixes, suffixes)
            for d in numbers:
                yield from _yield_affixes(f"{rev_b}{d}", prefixes, suffixes)

    # 3. Repeated / 2-digit numbers
    for d in numbers:
        if len(d) > 1:
            yield from _yield_affixes(f"{d}{d}", prefixes, suffixes)
            for b in bases:
                yield from _yield_affixes(f"{b}{d}{d}", prefixes, suffixes)
        if len(d) == 4 and d.isdigit():
            two_digit = d[2:]
            yield from _yield_affixes(two_digit, prefixes, suffixes)
            for b in bases:
                yield from _yield_affixes(f"{b}{two_digit}", prefixes, suffixes)
                for s in specials:
                    yield from _yield_affixes(f"{b}{s}{two_digit}", prefixes, suffixes)
                    yield from _yield_affixes(f"{b}{two_digit}{s}", prefixes, suffixes)


# ──────────────────────────────────────────────────────────────────────────────
# Public Progressive Generator API
# ──────────────────────────────────────────────────────────────────────────────


def generate_stage1_candidates(
    hints: HintModel,
    seen: set[str] | None = None,
) -> Iterator[str]:
    """
    Yield unique Stage 1 candidates that satisfy length boundaries.
    """
    if seen is None:
        seen = set()

    for cand in _stream_stage1_raw(hints):
        if _is_valid_length(cand, hints.min_length, hints.max_length) and cand not in seen:
            seen.add(cand)
            yield cand


def generate_stage2_candidates(
    hints: HintModel,
    seen: set[str] | None = None,
) -> Iterator[str]:
    """
    Yield unique Stage 2 candidates that satisfy length boundaries and were not in Stage 1.
    """
    if seen is None:
        seen = set()

    for cand in _stream_stage2_raw(hints):
        if _is_valid_length(cand, hints.min_length, hints.max_length) and cand not in seen:
            seen.add(cand)
            yield cand


def generate_stage3_candidates(
    hints: HintModel,
    seen: set[str] | None = None,
) -> Iterator[str]:
    """
    Yield unique Stage 3 candidates that satisfy length boundaries and were not in Stage 1 or 2.
    """
    if seen is None:
        seen = set()

    for cand in _stream_stage3_raw(hints):
        if _is_valid_length(cand, hints.min_length, hints.max_length) and cand not in seen:
            seen.add(cand)
            yield cand


def generate_candidates(hints: HintModel) -> Iterator[str]:
    """
    Progressively generate distinct candidate passwords across all three stages.

    Yields candidates lazily one-by-one in strict stage order (Stage 1 -> Stage 2 -> Stage 3)
    with on-the-fly deduplication and length filtering.

    Parameters
    ----------
    hints:
        The validated HintModel instance containing user hints and optional length limits.

    Yields
    ------
    str
        Unique candidate password string.
    """
    if not hints.has_any_hints:
        return

    seen: set[str] = set()

    # Stage 1 — Direct Hint Search
    yield from generate_stage1_candidates(hints, seen=seen)

    # Stage 2 — Hint Transformation Search
    yield from generate_stage2_candidates(hints, seen=seen)

    # Stage 3 — Expanded Hint Search
    yield from generate_stage3_candidates(hints, seen=seen)
