"""
tests/test_hint_collector.py
Comprehensive unit tests for password hint data model, validation, multi-value handling,
and interactive UI collection for Version 2 recovery.
"""

from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

from modules.hint_collector import (
    HintModel,
    HintValidationError,
    collect_password_hints,
    parse_hint_field,
    parse_length_field,
    validate_lengths,
)


# ──────────────────────────────────────────────────────────────────────────────
# parse_hint_field Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestParseHintField:
    def test_single_value_parsed(self) -> None:
        assert parse_hint_field("Name", "Saniya") == ["Saniya"]

    def test_none_returns_none_case_insensitive(self) -> None:
        assert parse_hint_field("Word", "NONE") is None
        assert parse_hint_field("Word", "none") is None
        assert parse_hint_field("Word", "None") is None
        assert parse_hint_field("Prefix", "  NONE  ") is None

    def test_zero_is_accepted_as_valid_value(self) -> None:
        assert parse_hint_field("Number", "0") == ["0"]
        assert parse_hint_field("Number", "  0  ") == ["0"]

    def test_zero_in_comma_separated_numbers(self) -> None:
        assert parse_hint_field("Number", "0, 7, 9") == ["0", "7", "9"]
        assert parse_hint_field("Number", "7, 0, 9, 2, 5") == ["7", "0", "9", "2", "5"]

    def test_multiple_comma_separated_values_in_all_fields(self) -> None:
        assert parse_hint_field("Name", "Saniya, Sakshi, Saura") == ["Saniya", "Sakshi", "Saura"]
        assert parse_hint_field("Word", "school, office, home") == ["school", "office", "home"]
        assert parse_hint_field("Number", "123, 7070, 2024") == ["123", "7070", "2024"]
        assert parse_hint_field("Special Character", "@, #, $, !") == ["@", "#", "$", "!"]
        assert parse_hint_field("Prefix", "Pre1, Pre2, @Sai") == ["Pre1", "Pre2", "@Sai"]
        assert parse_hint_field("Suffix", "123@, !2024, #1") == ["123@", "!2024", "#1"]

    def test_preserves_user_order(self) -> None:
        raw = "Zeta, Alpha, Gamma, Beta"
        assert parse_hint_field("Word", raw) == ["Zeta", "Alpha", "Gamma", "Beta"]

    def test_whitespace_trimmed_around_tokens_internal_whitespace_preserved(self) -> None:
        raw = "   hello world  ,  foo bar   ,  single "
        assert parse_hint_field("Word", raw) == ["hello world", "foo bar", "single"]

    def test_exact_duplicate_tokens_removed_preserving_first_occurrence(self) -> None:
        raw = "apple, banana, apple, cherry, banana"
        assert parse_hint_field("Word", raw) == ["apple", "banana", "cherry"]

    def test_case_sensitive_distinction_preserved(self) -> None:
        raw = "Saniya, saniya, SANIYA"
        assert parse_hint_field("Name", raw) == ["Saniya", "saniya", "SANIYA"]

    def test_special_characters_preserved_exactly(self) -> None:
        raw = "@, #, $, !, %, ^, &, *, (_, ), -, +, ="
        assert parse_hint_field("Special Character", raw) == [
            "@", "#", "$", "!", "%", "^", "&", "*", "(_", ")", "-", "+", "="
        ]

    def test_empty_string_raises_validation_error(self) -> None:
        with pytest.raises(HintValidationError, match="cannot be blank"):
            parse_hint_field("Name", "")

    def test_whitespace_only_raises_validation_error(self) -> None:
        with pytest.raises(HintValidationError, match="cannot be blank"):
            parse_hint_field("Name", "   ")

    def test_empty_token_between_commas_raises_validation_error(self) -> None:
        with pytest.raises(HintValidationError, match="Contains empty item between commas"):
            parse_hint_field("Name", "Saniya,,Sakshi")

    def test_trailing_comma_raises_validation_error(self) -> None:
        with pytest.raises(HintValidationError, match="Contains empty item between commas"):
            parse_hint_field("Name", "Saniya, Sakshi,")

    def test_leading_comma_raises_validation_error(self) -> None:
        with pytest.raises(HintValidationError, match="Contains empty item between commas"):
            parse_hint_field("Name", ",Saniya, Sakshi")

    def test_comma_with_spaces_between_raises_validation_error(self) -> None:
        with pytest.raises(HintValidationError, match="Contains empty item between commas"):
            parse_hint_field("Word", "apple,   , banana")

    def test_mixing_none_with_other_values_raises_error(self) -> None:
        with pytest.raises(HintValidationError, match="Cannot combine 'NONE'"):
            parse_hint_field("Name", "Saniya, NONE")

    def test_mixing_none_as_first_token_raises_error(self) -> None:
        with pytest.raises(HintValidationError, match="Cannot combine 'NONE'"):
            parse_hint_field("Number", "NONE, 7070")

    def test_mixing_lowercase_none_in_middle_raises_error(self) -> None:
        with pytest.raises(HintValidationError, match="Cannot combine 'NONE'"):
            parse_hint_field("Prefix", "Pre, none, Suf")


# ──────────────────────────────────────────────────────────────────────────────
# parse_length_field Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestParseLengthField:
    def test_valid_positive_integer(self) -> None:
        assert parse_length_field("Minimum Length", "8") == 8

    def test_whitespace_around_integer(self) -> None:
        assert parse_length_field("Maximum Length", "  16  ") == 16

    def test_none_returns_none_unconstrained(self) -> None:
        assert parse_length_field("Minimum Length", "NONE") is None
        assert parse_length_field("Minimum Length", "none") is None
        assert parse_length_field("Maximum Length", "  None  ") is None

    def test_zero_returns_none_unconstrained(self) -> None:
        assert parse_length_field("Minimum Length", "0") is None
        assert parse_length_field("Maximum Length", "  0  ") is None

    def test_negative_length_raises_error(self) -> None:
        with pytest.raises(HintValidationError, match="greater than or equal to 0"):
            parse_length_field("Minimum Length", "-4")

    def test_non_integer_string_raises_error(self) -> None:
        with pytest.raises(HintValidationError, match="must be a valid positive integer or 'NONE'"):
            parse_length_field("Minimum Length", "eight")

    def test_float_string_raises_error(self) -> None:
        with pytest.raises(HintValidationError, match="must be a valid positive integer or 'NONE'"):
            parse_length_field("Minimum Length", "8.5")

    def test_blank_length_raises_error(self) -> None:
        with pytest.raises(HintValidationError, match="cannot be blank"):
            parse_length_field("Minimum Length", "   ")


# ──────────────────────────────────────────────────────────────────────────────
# validate_lengths Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestValidateLengths:
    def test_min_less_than_max(self) -> None:
        validate_lengths(8, 12)  # Should not raise

    def test_min_equal_to_max(self) -> None:
        validate_lengths(8, 8)  # Should not raise

    def test_both_none(self) -> None:
        validate_lengths(None, None)  # Should not raise

    def test_min_none_max_set(self) -> None:
        validate_lengths(None, 16)  # Should not raise

    def test_min_set_max_none(self) -> None:
        validate_lengths(8, None)  # Should not raise

    def test_min_greater_than_max_raises_error(self) -> None:
        with pytest.raises(HintValidationError, match="cannot be greater than Maximum Length"):
            validate_lengths(12, 8)

    def test_invalid_negative_or_zero_values(self) -> None:
        with pytest.raises(HintValidationError, match="Minimum Length must be greater than 0"):
            validate_lengths(0, 10)
        with pytest.raises(HintValidationError, match="Maximum Length must be greater than 0"):
            validate_lengths(8, 0)


# ──────────────────────────────────────────────────────────────────────────────
# HintModel Structure & Helper Properties Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestHintModelStructure:
    def test_default_values_are_none(self) -> None:
        model = HintModel()
        assert model.name is None
        assert model.word is None
        assert model.number is None
        assert model.special_character is None
        assert model.prefix is None
        assert model.suffix is None
        assert model.min_length is None
        assert model.max_length is None
        assert not model.has_any_hints
        assert model.active_fields == {}
        assert model.total_raw_tokens == 0
        assert not model.has_explicit_min_length
        assert not model.has_explicit_max_length

    def test_active_fields_and_properties_with_populated_values(self) -> None:
        model = HintModel(
            name=["Saniya", "Sakshi"],
            number=["7070", "123"],
            special_character=["@"],
            min_length=8,
            max_length=12,
        )
        assert model.has_any_hints
        assert model.active_fields == {
            "name": ["Saniya", "Sakshi"],
            "number": ["7070", "123"],
            "special_character": ["@"],
        }
        assert model.total_raw_tokens == 5
        assert model.has_explicit_min_length
        assert model.has_explicit_max_length

    def test_format_field_and_format_length(self) -> None:
        model = HintModel(
            name=["Saniya", "Sakshi", "Saura"],
            word=None,
            min_length=8,
            max_length=None,
        )
        assert model.format_field(model.name) == "Saniya, Sakshi, Saura"
        assert model.format_field(model.word) == "None"
        assert model.format_length(model.min_length) == "8"
        assert model.format_length(model.max_length) == "None"


# ──────────────────────────────────────────────────────────────────────────────
# collect_password_hints Interactive Flow Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestCollectPasswordHintsInteractive:
    def test_full_collection_and_confirm(self) -> None:
        inputs = iter([
            "Saniya, Sakshi, Saura",  # Name
            "NONE",                   # Word
            "123, 7070, 2024",        # Number
            "@",                      # Special Char
            "none",                   # Prefix
            "None",                   # Suffix
            "8",                      # Min Length
            "12",                     # Max Length
            "1",                      # Confirm
        ])
        console = Console(file=StringIO())
        hints = collect_password_hints(console=console, input_func=lambda _: next(inputs))

        assert hints is not None
        assert hints.name == ["Saniya", "Sakshi", "Saura"]
        assert hints.word is None
        assert hints.number == ["123", "7070", "2024"]
        assert hints.special_character == ["@"]
        assert hints.prefix is None
        assert hints.suffix is None
        assert hints.min_length == 8
        assert hints.max_length == 12

    def test_number_field_accepts_zero_as_valid_data(self) -> None:
        inputs = iter([
            "NONE",                   # Name
            "NONE",                   # Word
            "0, 7, 9",                # Number with 0
            "NONE",                   # Special Char
            "NONE",                   # Prefix
            "NONE",                   # Suffix
            "NONE",                   # Min Length -> None
            "NONE",                   # Max Length -> None
            "1",                      # Confirm
        ])
        console = Console(file=StringIO())
        hints = collect_password_hints(console=console, input_func=lambda _: next(inputs))

        assert hints is not None
        assert hints.number == ["0", "7", "9"]
        assert hints.name is None
        assert hints.word is None
        assert hints.min_length is None
        assert hints.max_length is None

    def test_unconstrained_lengths_with_zero(self) -> None:
        inputs = iter([
            "Saniya",  # Name
            "NONE",    # Word
            "NONE",    # Number
            "NONE",    # Special Char
            "NONE",    # Prefix
            "NONE",    # Suffix
            "0",       # Min Length -> None
            "0",       # Max Length -> None
            "1",       # Confirm
        ])
        console = Console(file=StringIO())
        hints = collect_password_hints(console=console, input_func=lambda _: next(inputs))

        assert hints is not None
        assert hints.min_length is None
        assert hints.max_length is None
        assert not hints.has_explicit_min_length
        assert not hints.has_explicit_max_length

    def test_cancel_flow_returns_none(self) -> None:
        inputs = iter([
            "Saniya",  # Name
            "school",  # Word
            "123",     # Number
            "!",       # Special Char
            "@Sai",    # Prefix
            "123@",    # Suffix
            "6",       # Min Length
            "10",      # Max Length
            "3",       # Cancel
        ])
        console = Console(file=StringIO())
        hints = collect_password_hints(console=console, input_func=lambda _: next(inputs))
        assert hints is None

    def test_edit_flow_recollects_hints(self) -> None:
        inputs = iter([
            # First pass
            "WrongName",  # Name
            "NONE",       # Word
            "1111",       # Number
            "NONE",       # Special Char
            "NONE",       # Prefix
            "NONE",       # Suffix
            "4",          # Min Length
            "6",          # Max Length
            "2",          # Select [2] Edit

            # Second pass
            "CorrectName, OtherName",  # Name
            "school",                  # Word
            "7070",                    # Number
            "@",                       # Special Char
            "Pre",                     # Prefix
            "Suf",                     # Suffix
            "8",                       # Min Length
            "16",                      # Max Length
            "1",                       # Confirm
        ])
        console = Console(file=StringIO())
        hints = collect_password_hints(console=console, input_func=lambda _: next(inputs))

        assert hints is not None
        assert hints.name == ["CorrectName", "OtherName"]
        assert hints.word == ["school"]
        assert hints.number == ["7070"]
        assert hints.special_character == ["@"]
        assert hints.prefix == ["Pre"]
        assert hints.suffix == ["Suf"]
        assert hints.min_length == 8
        assert hints.max_length == 16

    def test_retry_on_empty_comma_input(self) -> None:
        inputs = iter([
            "Saniya,,Sakshi",  # Invalid empty comma -> retry
            "Saniya, Sakshi",  # Valid
            "NONE",            # Word
            "NONE",            # Number
            "NONE",            # Special Char
            "NONE",            # Prefix
            "NONE",            # Suffix
            "6",               # Min Length
            "10",              # Max Length
            "1",               # Confirm
        ])
        console = Console(file=StringIO())
        hints = collect_password_hints(console=console, input_func=lambda _: next(inputs))
        assert hints is not None
        assert hints.name == ["Saniya", "Sakshi"]

    def test_keyboard_interrupt_exits_gracefully(self) -> None:
        def raise_keyboard_interrupt(_: str) -> str:
            raise KeyboardInterrupt()

        console = Console(file=StringIO())
        with pytest.raises(SystemExit) as exc_info:
            collect_password_hints(console=console, input_func=raise_keyboard_interrupt)
        assert exc_info.value.code == 130
