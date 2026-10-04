"""
main.py — Forgotten Password Recovery Assistant
================================================
Entry point. Run with:  python main.py

Workflow
--------
1. Print the application banner.
2. Detect the user's locked file in locked_files/.
3. Find and select a candidate list from password_list/.
4. Load and validate the selected candidate list.
5. Dispatch to the format-specific verifier for each candidate.
6. Show live Rich progress while testing.
7. On success: mask the password, auto-save to results/, offer to reveal.
8. On failure: clearly report that no candidate matched.

All processing is local — no network calls are made.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from modules.candidate_loader import CandidateLoadError, load_candidates
from modules.file_detector import FileDetectionError, detect_locked_file
from modules.progress import ProgressUI
from modules.verifier import (
    SUPPORTED_FORMATS,
    UnsupportedFormatError,
    VerificationError,
    verify,
)


# ──────────────────────────────────────────────────────────────────────────────
# Directory layout
# ──────────────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent

LOCKED_FILES_DIR = BASE_DIR / "locked_files"
PASSWORD_LIST_DIR = BASE_DIR / "password_list"
RESULTS_DIR = BASE_DIR / "results"


# ──────────────────────────────────────────────────────────────────────────────
# Ensure standard streams handle UTF-8 symbols reliably on Windows
# ──────────────────────────────────────────────────────────────────────────────

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


console = Console(
    legacy_windows=False if sys.platform == "win32" else None
)


# ──────────────────────────────────────────────────────────────────────────────
# UI helpers
# ──────────────────────────────────────────────────────────────────────────────


def _print_banner() -> None:
    """Print the application banner."""

    text = Text()

    text.append(
        "Forgotten Password Recovery Assistant\n",
        style="bold cyan",
    )

    text.append(
        "For authorised recovery of your own password-protected files.",
        style="dim",
    )

    console.print(
        Panel(
            text,
            expand=False,
            border_style="cyan",
        )
    )

    console.print()


def _select_password_list() -> Path:
    """
    Find and select a candidate password list from password_list/.

    Behavior:
    - If there is exactly one .txt file, use it automatically.
    - If there are multiple .txt files, ask the user to choose one.
    - If there are no .txt files, raise CandidateLoadError.
    """

    if not PASSWORD_LIST_DIR.exists():
        raise CandidateLoadError(
            f"Password list directory not found: "
            f"'{PASSWORD_LIST_DIR}'"
        )

    txt_files = sorted(
        path
        for path in PASSWORD_LIST_DIR.iterdir()
        if path.is_file()
        and path.suffix.lower() == ".txt"
    )

    if not txt_files:
        raise CandidateLoadError(
            f"No .txt password list found in "
            f"'{PASSWORD_LIST_DIR}'.\n"
            f"Create a .txt file with one candidate per line."
        )

    # Only one candidate list exists.
    if len(txt_files) == 1:
        return txt_files[0]

    # Multiple candidate lists exist.
    console.print(
        "\n[bold yellow]Multiple password lists detected "
        "— please pick one:[/bold yellow]\n"
    )

    for index, path in enumerate(txt_files, start=1):
        console.print(
            f"  [cyan]{index}[/cyan]. {path.name}"
        )

    while True:
        try:
            choice = input(
                f"\nEnter the number of the password list "
                f"[1-{len(txt_files)}]: "
            ).strip()

            selected_index = int(choice)

            if 1 <= selected_index <= len(txt_files):
                return txt_files[selected_index - 1]

        except (ValueError, EOFError):
            pass

        console.print(
            f"[yellow]Please enter a number between "
            f"1 and {len(txt_files)}.[/yellow]"
        )


def _save_result(
    file_path: Path,
    password: str,
    attempts: int,
    elapsed: float,
) -> Path:
    """Write the recovery result to a timestamped file in results/."""

    RESULTS_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    result_file = RESULTS_DIR / f"recovery_{timestamp}.txt"

    content = (
        "Forgotten Password Recovery Assistant — Result\n"
        f"{'=' * 50}\n"
        f"Date/Time : "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"File      : {file_path.name}\n"
        f"Attempts  : {attempts:,}\n"
        f"Elapsed   : {elapsed:.1f}s\n"
        f"Password  : {password}\n"
        "\n"
        "IMPORTANT: Keep this file private and delete it after use.\n"
    )

    result_file.write_text(
        content,
        encoding="utf-8",
    )

    return result_file


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────


def main() -> int:
    """Run the password recovery workflow."""

    _print_banner()

    # ── Step 1: Detect locked file ────────────────────────────────────────────

    try:
        detected = detect_locked_file(LOCKED_FILES_DIR)

    except FileDetectionError as exc:
        console.print(
            f"[bold red]✗ File Detection Error[/bold red]\n"
            f"  {exc}"
        )
        return 1

    console.print(
        f"  [green]✓[/green] Locked file  : "
        f"[bold]{detected.path.name}[/bold]"
    )

    console.print(
        f"  [green]✓[/green] Format       : "
        f"[bold]{detected.format_name}[/bold]"
    )

    console.print()

    # ── Step 2: Find and load candidates ──────────────────────────────────────

    try:
        password_list_path = _select_password_list()

        console.print(
            f"  [green]✓[/green] Password list : "
            f"[bold]{password_list_path.name}[/bold]"
        )

        candidates, stats = load_candidates(
            password_list_path
        )

    except CandidateLoadError as exc:
        console.print(
            f"[bold red]✗ Candidate Load Error[/bold red]\n"
            f"  {exc}"
        )
        return 1

    console.print(
        f"  [green]✓[/green] Candidates   : "
        f"[bold]{stats.total_usable:,}[/bold] usable",
        end="",
    )

    if stats.duplicates_removed:
        console.print(
            f"  "
            f"([yellow]"
            f"{stats.duplicates_removed:,} duplicate(s) removed"
            f"[/yellow])",
            end="",
        )

    console.print()

    skipped: list[str] = []

    if stats.comment_lines:
        skipped.append(
            f"{stats.comment_lines} comment line(s)"
        )

    if stats.blank_lines:
        skipped.append(
            f"{stats.blank_lines} blank line(s)"
        )

    if skipped:
        console.print(
            f"  [dim]   Skipped: "
            f"{', '.join(skipped)}[/dim]"
        )

    console.print()

    # ── Step 3: Verify format is supported ────────────────────────────────────

    if detected.extension not in SUPPORTED_FORMATS:
        console.print(
            f"[bold red]✗ No handler for "
            f"'{detected.extension}'[/bold red]\n"
            f"  Supported: "
            f"{', '.join(SUPPORTED_FORMATS)}"
        )
        return 1

    # ── Step 4: Verification loop ────────────────────────────────────────────

    ui = ProgressUI(console=console)

    ui.start(
        total=stats.total_usable,
        file_name=detected.path.name,
    )

    found_password: str | None = None
    attempts = 0

    start_time = time.monotonic()

    try:
        for candidate in candidates:
            attempts += 1

            ui.update(
                tested=attempts
            )

            try:
                if verify(
                    detected.path,
                    candidate,
                ):
                    found_password = candidate
                    break

            except NotImplementedError:
                ui.stop()

                console.print(
                    "\n"
                    "[bold yellow]"
                    "⚠ Phase 1 Scaffold Notice"
                    "[/bold yellow]\n\n"
                    f"  Verification for "
                    f"[bold]{detected.format_name}[/bold] "
                    f"is not yet implemented.\n"
                    "  The scaffold is wired correctly — "
                    "actual checking will be added in Phase 2.\n"
                )

                return 0

            except VerificationError as exc:
                ui.stop()

                console.print(
                    "\n"
                    "[bold red]✗ Verification error:[/bold red] "
                    f"{exc}"
                )

                return 1

    except KeyboardInterrupt:
        ui.stop()

        elapsed = time.monotonic() - start_time

        console.print(
            f"\n"
            f"[yellow]⚠ Interrupted after "
            f"{attempts:,} attempt(s) "
            f"({elapsed:.1f}s).[/yellow]"
        )

        return 130

    elapsed = time.monotonic() - start_time

    ui.stop()

    # ── Step 5: Show result ───────────────────────────────────────────────────

    console.print()

    if found_password is not None:

        masked = "●" * len(found_password)

        console.print(
            Panel(
                f"[bold green]PASSWORD FOUND[/bold green] "
                f"after [bold]{attempts:,}[/bold] attempt(s) "
                f"({elapsed:.1f}s)\n\n"
                f"  Recovered  : "
                f"[bold yellow]{masked}[/bold yellow]  "
                f"(hidden)",
                title="✓ Recovery Successful",
                border_style="green",
                expand=False,
            )
        )

        result_path = _save_result(
            detected.path,
            found_password,
            attempts,
            elapsed,
        )

        console.print(
            f"\n  [dim]Result auto-saved → "
            f"{result_path}[/dim]"
        )

        try:
            input(
                "\n  Press ENTER to reveal the password "
                "(or Ctrl+C to skip): "
            )

            console.print(
                f"\n  [bold cyan]Password:[/bold cyan] "
                f"{found_password}\n"
            )

        except (KeyboardInterrupt, EOFError):
            console.print(
                "\n  [dim]"
                "(Password reveal skipped.)"
                "[/dim]\n"
            )

    else:

        console.print(
            Panel(
                f"Tested [bold]{attempts:,}[/bold] candidate(s) "
                f"in {elapsed:.1f}s — none matched.\n\n"
                "  [dim]→ Try expanding your candidate list.[/dim]\n"
                "  [dim]→ Check the file is the correct one.[/dim]",
                title="✗ Password Not Found",
                border_style="red",
                expand=False,
            )
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())