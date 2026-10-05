"""
hint_collector.py
Interactive password-hint collection and validation for Version 2 recovery.

Responsibilities
----------------
- Define the structured `HintModel` dataclass.
- Validate and parse user input for 8 distinct hint fields.
- Support "0" as disabled / not supplied for applicable fields.
- Support comma-separated multiple values for hint fields.
- Enforce positive numeric constraints and length consistency (min_length <= max_length).
- Render the interactive CMD hint collection and review screens.
- Support Confirm, Edit, and Cancel actions.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


class HintValidationError(Exception):
    """Raised when hint input fails validation rules."""


@dataclass
class HintModel:
    """
    Structured container for user-supplied password hints.

    Fields set to None represent categories that were not used (user entered "0").
    Length fields set to None represent unconstrained bounds (user entered "0" or omitted).
    """

    name: list[str] | None = None
    word: list[str] | None = None
    number: list[str] | None = None
    special_character: list[str] | None = None
    prefix: list[str] | None = None
    suffix: list[str] | None = None
    min_length: int | None = None
    max_length: int | None = None

    @staticmethod
    def format_field(value: list[str] | None) -> str:
        """Format a list hint field for display."""
        if value is None:
            return "None"
        return ", ".join(value)

    @staticmethod
    def format_length(value: int | None) -> str:
        """Format a length constraint for display."""
        if value is None:
            return "None"
        return str(value)

    @property
    def has_any_hints(self) -> bool:
        """Return True if at least one component field is populated."""
        return any(
            f is not None
            for f in (
                self.name,
                self.word,
                self.number,
                self.special_character,
                self.prefix,
                self.suffix,
            )
        )

    @property
    def active_fields(self) -> dict[str, list[str]]:
        """Return a mapping of field names to non-empty token lists."""
        result: dict[str, list[str]] = {}
        for key in ("name", "word", "number", "special_character", "prefix", "suffix"):
            val = getattr(self, key)
            if val is not None:
                result[key] = val
        return result

    @property
    def total_raw_tokens(self) -> int:
        """Return the sum of token counts across all active fields."""
        return sum(len(tokens) for tokens in self.active_fields.values())

    @property
    def has_explicit_min_length(self) -> bool:
        """Return True if the user explicitly provided a minimum length."""
        return self.min_length is not None

    @property
    def has_explicit_max_length(self) -> bool:
        """Return True if the user explicitly provided a maximum length."""
        return self.max_length is not None


def parse_hint_field(field_name: str, raw_input: str) -> list[str] | None:
    """
    Parse and validate a text hint field.

    Parameters
    ----------
    field_name:
        Human-readable name of the field (for error messages).
    raw_input:
        Raw user input from terminal.

    Returns
    -------
    list[str] | None
        Normalized list of unique, case-sensitive string values, or None if disabled ("NONE").

    Raises
    ------
    HintValidationError
        If input is empty, contains empty items between commas, or mixes "NONE" with other values.
    """
    stripped = raw_input.strip()

    if not stripped:
        raise HintValidationError(
            f"'{field_name}' cannot be blank. Enter 'NONE' if this element was not used, or enter value(s)."
        )

    if stripped.upper() == "NONE":
        return None

    raw_parts = raw_input.split(",")

    # Detect empty tokens caused by duplicate or leading/trailing commas (e.g. "Saniya,,Sakshi")
    for part in raw_parts:
        if not part.strip():
            raise HintValidationError(
                f"'{field_name}': Contains empty item between commas ('{raw_input}'). "
                "Please remove extra commas."
            )

    tokens = [p.strip() for p in raw_parts]

    # Check for invalid combination of "NONE" (case-insensitive) and other values
    has_none = any(t.upper() == "NONE" for t in tokens)
    if has_none and len(tokens) > 1:
        raise HintValidationError(
            f"'{field_name}': Cannot combine 'NONE' (disabled) with other values ('{raw_input}'). "
            "Enter 'NONE' alone if not used, or enter only the valid values."
        )

    # Deduplicate while preserving order and exact casing/symbols
    clean_tokens: list[str] = []
    seen: set[str] = set()

    for token in tokens:
        if token not in seen:
            seen.add(token)
            clean_tokens.append(token)

    return clean_tokens


def parse_length_field(field_name: str, raw_input: str) -> int | None:
    """
    Parse and validate a numeric length field.

    Parameters
    ----------
    field_name:
        Human-readable name of the length field.
    raw_input:
        Raw user input from terminal.

    Returns
    -------
    int | None
        Positive integer value, or None if unconstrained ("NONE" or "0").

    Raises
    ------
    HintValidationError
        If input is not a positive integer or "NONE"/"0".
    """
    stripped = raw_input.strip()

    if not stripped:
        raise HintValidationError(
            f"'{field_name}' cannot be blank. Please enter a positive number or 'NONE' for unconstrained."
        )

    if stripped.upper() == "NONE" or stripped == "0":
        return None

    try:
        val = int(stripped)
    except ValueError as exc:
        raise HintValidationError(
            f"'{field_name}' must be a valid positive integer or 'NONE', not '{stripped}'."
        ) from exc

    if val < 0:
        raise HintValidationError(
            f"'{field_name}' must be greater than or equal to 0, received '{val}'."
        )

    return val


def validate_lengths(min_length: int | None, max_length: int | None) -> None:
    """
    Ensure minimum length is not greater than maximum length when both are specified.

    Raises
    ------
    HintValidationError
        If min_length > max_length.
    """
    if min_length is not None and min_length <= 0:
        raise HintValidationError(f"Minimum Length must be greater than 0, received '{min_length}'.")

    if max_length is not None and max_length <= 0:
        raise HintValidationError(f"Maximum Length must be greater than 0, received '{max_length}'.")

    if min_length is not None and max_length is not None and min_length > max_length:
        raise HintValidationError(
            f"Minimum Length ({min_length}) cannot be greater than Maximum Length ({max_length})."
        )


def _prompt_field(
    prompt_text: str,
    field_name: str,
    parser: Callable[[str, str], list[str] | None],
    example: str,
    console: Console,
    input_func: Callable[[str], str] = input,
) -> list[str] | None:
    """Prompt for a single hint field with retry on validation error."""
    console.print(f"\n[bold cyan]{prompt_text}[/bold cyan]")
    console.print(f"  [dim]Example: {example}[/dim]")

    while True:
        try:
            raw = input_func("  Enter: ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Input cancelled by user.[/yellow]")
            sys.exit(130)

        try:
            return parser(field_name, raw)
        except HintValidationError as exc:
            console.print(f"  [bold red]✗ {exc}[/bold red]")
            console.print("  [dim]Please re-enter value (or 'NONE' if not used):[/dim]")


def _prompt_lengths(
    console: Console,
    input_func: Callable[[str], str] = input,
) -> tuple[int | None, int | None]:
    """Prompt for min_length and max_length with consistency validation."""
    while True:
        console.print("\n[bold cyan][7] Minimum Password Length[/bold cyan]")
        console.print("  [dim]Example: 8 (or 0 for unconstrained)[/dim]")
        while True:
            try:
                raw_min = input_func("  Enter: ")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Input cancelled by user.[/yellow]")
                sys.exit(130)
            try:
                min_len = parse_length_field("Minimum Password Length", raw_min)
                break
            except HintValidationError as exc:
                console.print(f"  [bold red]✗ {exc}[/bold red]")

        console.print("\n[bold cyan][8] Maximum Password Length[/bold cyan]")
        console.print("  [dim]Example: 12 (or 0 for unconstrained)[/dim]")
        while True:
            try:
                raw_max = input_func("  Enter: ")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Input cancelled by user.[/yellow]")
                sys.exit(130)
            try:
                max_len = parse_length_field("Maximum Password Length", raw_max)
                break
            except HintValidationError as exc:
                console.print(f"  [bold red]✗ {exc}[/bold red]")

        try:
            validate_lengths(min_len, max_len)
            return min_len, max_len
        except HintValidationError as exc:
            console.print(f"\n  [bold red]✗ {exc}[/bold red]")
            console.print("  [dim]Please re-enter both minimum and maximum lengths.[/dim]")


def _display_review_screen(hints: HintModel, console: Console) -> None:
    """Display the review screen for collected hints."""
    console.print()
    console.print(
        Panel(
            Text("REVIEW YOUR HINTS", justify="center", style="bold cyan"),
            expand=False,
            border_style="cyan",
            width=50,
        )
    )

    items = [
        ("Name", hints.format_field(hints.name)),
        ("Word", hints.format_field(hints.word)),
        ("Number", hints.format_field(hints.number)),
        ("Special Character", hints.format_field(hints.special_character)),
        ("Known Prefix", hints.format_field(hints.prefix)),
        ("Known Suffix", hints.format_field(hints.suffix)),
        ("Minimum Length", hints.format_length(hints.min_length)),
        ("Maximum Length", hints.format_length(hints.max_length)),
    ]

    for label, val in items:
        val_style = "dim" if val == "None" else "bold yellow"
        console.print(f"  {label:<18} : [{val_style}]{val}[/{val_style}]")

    console.print()
    console.print("  [cyan][1][/cyan] Confirm")
    console.print("  [cyan][2][/cyan] Edit")
    console.print("  [cyan][3][/cyan] Cancel\n")


def collect_password_hints(
    console: Console | None = None,
    input_func: Callable[[str], str] = input,
) -> HintModel | None:
    """
    Interactively collect and review password hints from the user.

    Returns
    -------
    HintModel | None
        Validated HintModel if confirmed, or None if cancelled.
    """
    console = console or Console()

    while True:
        console.print(
            Panel(
                Text("ENTER PASSWORD HINTS", justify="center", style="bold cyan"),
                expand=False,
                border_style="cyan",
                width=50,
            )
        )
        console.print("  [dim]Enter NONE if this element was NOT used in the password.[/dim]")

        name = _prompt_field(
            "[1] Name", "Name", parse_hint_field, "Saniya (or Saniya, Sakshi, or NONE)", console, input_func
        )
        word = _prompt_field(
            "[2] Word", "Word", parse_hint_field, "school (or school, office, or NONE)", console, input_func
        )
        number = _prompt_field(
            "[3] Number", "Number", parse_hint_field, "7070 (or 7070, 0, 123, or NONE)", console, input_func
        )
        special_char = _prompt_field(
            "[4] Special Character", "Special Character", parse_hint_field, "@ (or @, #, $, !, or NONE)", console, input_func
        )
        prefix = _prompt_field(
            "[5] Known Prefix", "Known Prefix", parse_hint_field, "@Sai (or @Sai, My, or NONE)", console, input_func
        )
        suffix = _prompt_field(
            "[6] Known Suffix", "Known Suffix", parse_hint_field, "123@ (or 123@, !, or NONE)", console, input_func
        )

        min_len, max_len = _prompt_lengths(console, input_func)

        hints = HintModel(
            name=name,
            word=word,
            number=number,
            special_character=special_char,
            prefix=prefix,
            suffix=suffix,
            min_length=min_len,
            max_length=max_len,
        )

        # Review Screen
        while True:
            _display_review_screen(hints, console)
            try:
                choice = input_func("Choice: ").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Operation cancelled by user.[/yellow]")
                sys.exit(130)

            if choice in ("1", "[1]"):
                return hints
            elif choice in ("2", "[2]"):
                # Re-enter hints
                break
            elif choice in ("3", "[3]"):
                return None
            else:
                console.print("  [yellow]Please enter 1 (Confirm), 2 (Edit), or 3 (Cancel).[/yellow]")
