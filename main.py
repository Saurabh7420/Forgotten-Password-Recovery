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
from typing import Callable

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from modules.attempt_logger import AttemptLogger, RoundHistoryLogger, SessionHistoryManager
from modules.candidate_generator import generate_candidates
from modules.candidate_loader import CandidateLoadError, load_candidates
from modules.file_detector import (
    DetectedFile,
    FileDetectionError,
    detect_file_from_path,
    detect_locked_file,
)
from modules.hint_collector import HintModel, collect_password_hints
from modules.progress import HintProgressUI, ProgressUI
from modules.recovery_summary import display_recovery_summary
from modules.search_space import (
    SearchSpaceResult,
    calculate_search_space,
    display_search_space_analysis,
)
from modules.search_stages import (
    STAGE_NAMES,
    StageRecoveryResult,
    StageStats,
    execute_progressive_recovery,
)
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


def _select_locked_file() -> DetectedFile:
    """
    Prompt the user to select a locked file either from locked_files/ or by
    entering a manual full file path.
    """
    console.print(
        Panel(
            Text("SELECT LOCKED FILE", justify="center", style="bold cyan"),
            expand=False,
            border_style="cyan",
            width=50,
        )
    )
    console.print("  [cyan][1][/cyan] Select file from locked_files/")
    console.print("  [cyan][2][/cyan] Enter full file path\n")

    while True:
        try:
            choice = input("Choice: ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Operation cancelled by user.[/yellow]")
            sys.exit(130)

        if choice in ("1", "[1]"):
            try:
                return detect_locked_file(LOCKED_FILES_DIR)
            except FileDetectionError as exc:
                console.print(f"\n[bold red]✗ File Detection Error[/bold red]\n  {exc}\n")
                console.print("  [dim]Choose [1] to retry locked_files/ or [2] to enter a full file path.[/dim]\n")
                continue

        elif choice in ("2", "[2]"):
            while True:
                try:
                    console.print("\nEnter locked file path:")
                    path_str = input("> ").strip()
                except (KeyboardInterrupt, EOFError):
                    console.print("\n[yellow]Operation cancelled by user.[/yellow]")
                    sys.exit(130)

                try:
                    return detect_file_from_path(path_str)
                except FileDetectionError as exc:
                    console.print(f"\n[bold red]✗ File Detection Error[/bold red]\n  {exc}")
                    console.print("  [dim]Please try again or press Ctrl+C to cancel.[/dim]")
                    continue
        else:
            console.print("[yellow]Please enter 1 or 2.[/yellow]")


def _select_recovery_mode() -> str:
    """
    Prompt the user to select the recovery method:
    [1] Existing Password List
    [2] Generate Passwords from Hints

    Returns
    -------
    str
        '1' for password list, '2' for hint-based generation.
    """
    console.print(
        Panel(
            Text("SELECT RECOVERY METHOD", justify="center", style="bold cyan"),
            expand=False,
            border_style="cyan",
            width=50,
        )
    )
    console.print("  [cyan][1][/cyan] Existing Password List")
    console.print("  [cyan][2][/cyan] Generate Passwords from Hints\n")

    while True:
        try:
            choice = input("Choice: ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Operation cancelled by user.[/yellow]")
            sys.exit(130)

        if choice in ("1", "[1]"):
            return "1"
        elif choice in ("2", "[2]"):
            return "2"
        else:
            console.print("[yellow]Please enter 1 or 2.[/yellow]")


def prompt_for_additional_hints(
    console: Console | None = None,
    input_func: Callable[[str], str] = input,
) -> bool:
    """
    Prompt the user whether they would like to provide additional hints and continue
    when a hint-based recovery attempt exhausts without finding the password.

    Returns
    -------
    bool
        True if user chooses [1] Yes, False if user chooses [2] No or cancels.
    """
    c = console or Console()
    c.print("\n[bold yellow]Password not found using the provided hints and configured rules.[/bold yellow]\n")
    c.print("Would you like to provide additional hints and continue?\n")
    c.print("  [cyan][1][/cyan] Yes")
    c.print("  [cyan][2][/cyan] No\n")

    while True:
        try:
            raw_choice = input_func("Choice [1/2]: ")
            choice = raw_choice.strip().lower()
        except (KeyboardInterrupt, EOFError):
            c.print("\n[yellow]Operation cancelled by user.[/yellow]")
            return False

        if choice in ("1", "[1]", "yes", "y"):
            return True
        elif choice in ("2", "[2]", "no", "n"):
            return False
        else:
            c.print("[yellow]Please enter 1 or 2.[/yellow]")


def prompt_save_recovery_history(
    console: Console | None = None,
    input_func: Callable[[str], str] = input,
) -> bool:
    """
    Prompt the user whether to save the recovery history from all rounds after success.

    Returns
    -------
    bool
        True if user chooses [1] Yes (save), False if [2] No (delete).
    """
    c = console or Console()
    c.print("\nRecovery history from all rounds is currently stored in:\n")
    c.print("    [bold cyan]results/[/bold cyan]\n")
    c.print("Would you like to save the recovery history?\n")
    c.print("  [cyan][1][/cyan] Yes — Save all round files")
    c.print("  [cyan][2][/cyan] No  — Delete all round files\n")

    while True:
        try:
            raw_choice = input_func("Choice [1/2]: ")
            choice = raw_choice.strip().lower()
        except (KeyboardInterrupt, EOFError):
            c.print("\n[yellow]Operation cancelled by user.[/yellow]")
            return False

        if choice in ("1", "[1]", "yes", "y"):
            return True
        elif choice in ("2", "[2]", "no", "n"):
            return False
        else:
            c.print("[yellow]Please enter 1 or 2.[/yellow]")


def prompt_keep_unsuccessful_history(
    console: Console | None = None,
    input_func: Callable[[str], str] = input,
) -> bool:
    """
    Prompt the user whether to keep the tested candidate history when stopping an
    unsuccessful session.

    Returns
    -------
    bool
        True if user chooses [1] Yes (keep), False if [2] No (delete).
    """
    c = console or Console()
    c.print("\nRecovery history from this session is currently stored in:\n")
    c.print("    [bold cyan]results/[/bold cyan]\n")
    c.print("Would you like to keep the tested candidate history?\n")
    c.print("  [cyan][1][/cyan] Yes — Keep history")
    c.print("  [cyan][2][/cyan] No  — Delete history\n")

    while True:
        try:
            raw_choice = input_func("Choice [1/2]: ")
            choice = raw_choice.strip().lower()
        except (KeyboardInterrupt, EOFError):
            c.print("\n[yellow]Operation cancelled by user.[/yellow]")
            return False

        if choice in ("1", "[1]", "yes", "y"):
            return True
        elif choice in ("2", "[2]", "no", "n"):
            return False
        else:
            c.print("[yellow]Please enter 1 or 2.[/yellow]")


def _recover_with_hints(detected: DetectedFile, console: Console | None = None) -> int:
    """
    Execute Version 2 hint-based password recovery.
    - Collect and review password hints.
    - Calculate exact search space.
    - Progressively execute stages with single attempts logger and round history.
    - On exhaustion, prompt user for additional hints to continue.
    - Display clear final recovery summary.
    - Offer to save/delete round history.
    """
    c = console if console is not None else globals()["console"]
    hints = collect_password_hints(console=c)
    if hints is None:
        c.print("\n[yellow]Hint-based recovery cancelled.[/yellow]\n")
        return 0

    if detected.extension not in SUPPORTED_FORMATS:
        c.print(
            f"[bold red]✗ No handler for '{detected.extension}'[/bold red]\n"
            f"  Supported: {', '.join(SUPPORTED_FORMATS)}"
        )
        return 1

    session_manager = SessionHistoryManager(output_dir=RESULTS_DIR)
    seen_candidates: set[str] = set()
    total_session_attempts = 0
    stage_1_total = 0
    stage_2_total = 0
    stage_3_total = 0
    final_result: StageRecoveryResult | None = None
    last_analysis: SearchSpaceResult | None = None
    round_number = 0

    # Execute recovery stages with attempt logging in a single session
    with AttemptLogger(output_dir=RESULTS_DIR) as logger:
        session_manager.track_file(logger.file_path)
        while True:
            round_number += 1
            round_logger = session_manager.start_round(round_number=round_number)

            # Calculate exact search space for current hints
            analysis = calculate_search_space(hints)
            last_analysis = analysis
            display_search_space_analysis(analysis, console=c)

            # Determine candidates for this round (excluding already tested candidates)
            all_generated = set(generate_candidates(hints))
            new_candidates = all_generated - seen_candidates
            round_total = len(new_candidates)

            if round_total == 0 and len(seen_candidates) > 0:
                c.print(
                    "\n[yellow]No new candidate passwords were generated by these hints "
                    "that have not already been tested.[/yellow]"
                )
                round_logger.finalize(success=False)
            else:
                progress_ui = HintProgressUI(
                    total=round_total,
                    console=c,
                )
                progress_ui.start()
                try:
                    result = execute_progressive_recovery(
                        target_file=detected.path,
                        hints=hints,
                        verify_fn=verify,
                        attempt_logger=logger,
                        round_logger=round_logger,
                        progress_ui=progress_ui,
                        seen=seen_candidates,
                    )
                except KeyboardInterrupt:
                    progress_ui.stop()
                    round_logger.finalize(success=False)
                    c.print("\n[yellow]⚠ Recovery interrupted by user.[/yellow]")
                    return 130
                except VerificationError as exc:
                    progress_ui.stop()
                    round_logger.finalize(success=False)
                    c.print(f"\n[bold red]✗ Verification error:[/bold red] {exc}")
                    return 1
                except Exception:
                    progress_ui.stop()
                    round_logger.finalize(success=False)
                    raise

                # Finalize round file
                round_logger.finalize(
                    success=result.success,
                    found_password=result.found_password,
                    successful_stage_name=STAGE_NAMES.get(result.successful_stage, "") if result.successful_stage else None,
                    attempt_in_round=result.total_attempts if result.success else None,
                )

                total_session_attempts += result.total_attempts
                stage_1_total += result.stage_stats.get(1, StageStats(1, "")).candidates_tested
                stage_2_total += result.stage_stats.get(2, StageStats(2, "")).candidates_tested
                stage_3_total += result.stage_stats.get(3, StageStats(3, "")).candidates_tested

                final_result = StageRecoveryResult(
                    success=result.success,
                    found_password=result.found_password,
                    successful_stage=result.successful_stage,
                    total_attempts=total_session_attempts,
                    stage_stats={
                        1: StageStats(1, STAGE_NAMES[1], stage_1_total, result.successful_stage == 1, result.found_password if result.successful_stage == 1 else None),
                        2: StageStats(2, STAGE_NAMES[2], stage_2_total, result.successful_stage == 2, result.found_password if result.successful_stage == 2 else None),
                        3: StageStats(3, STAGE_NAMES[3], stage_3_total, result.successful_stage == 3, result.found_password if result.successful_stage == 3 else None),
                    },
                    stages_executed=result.stages_executed,
                )

                if result.success:
                    break

            # If password not found, prompt for additional hints
            want_more = prompt_for_additional_hints(console=c)
            if not want_more:
                break

            c.print("\n[bold cyan]Enter additional / updated hints:[/bold cyan]")
            new_hints = collect_password_hints(console=c)
            if new_hints is None:
                c.print("\n[yellow]Additional hints cancelled.[/yellow]\n")
                break
            hints = new_hints

        if final_result is not None:
            display_recovery_summary(
                result=final_result,
                search_space=last_analysis,
                attempts_file=logger.file_path,
                console=c,
            )

            if final_result.success:
                # Password Found -> Ask to save all round files
                save_history = prompt_save_recovery_history(console=c)
                if not save_history:
                    session_manager.delete_session_files()
                    c.print(
                        "\n[yellow]Recovery history deleted.[/yellow]\n"
                        "[dim]Only the recovery-history files created during this session were removed.[/dim]\n"
                    )
            else:
                # Password Not Found + Stop -> Ask to keep candidate history
                keep_history = prompt_keep_unsuccessful_history(console=c)
                if not keep_history:
                    session_manager.delete_session_files()
                    c.print(
                        "\n[yellow]Recovery history deleted.[/yellow]\n"
                        "[dim]Only the recovery-history files created during this session were removed.[/dim]\n"
                    )

    return 0


def _recover_with_password_list(detected: DetectedFile) -> int:
    """
    Execute the existing Version 1 manual candidate-list recovery workflow.
    """
    # ── Find and load candidates ──────────────────────────────────────────────
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

    # ── Verify format is supported ────────────────────────────────────────────
    if detected.extension not in SUPPORTED_FORMATS:
        console.print(
            f"[bold red]✗ No handler for "
            f"'{detected.extension}'[/bold red]\n"
            f"  Supported: "
            f"{', '.join(SUPPORTED_FORMATS)}"
        )
        return 1

    # ── Verification loop ─────────────────────────────────────────────────────
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
                    "⚠ Scaffold Notice"
                    "[/bold yellow]\n\n"
                    f"  Verification for "
                    f"[bold]{detected.format_name}[/bold] "
                    f"is not yet implemented.\n"
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

    # ── Show result ───────────────────────────────────────────────────────────
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


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────


def main() -> int:
    """Run the password recovery workflow."""

    _print_banner()

    # ── Step 1: Detect/Select locked file ─────────────────────────────────────

    detected = _select_locked_file()

    console.print(
        f"\n  [green]✓[/green] File detected\n"
        f"  [green]✓[/green] File name : [bold]{detected.path.name}[/bold]\n"
        f"  [green]✓[/green] Format    : [bold]{detected.format_name}[/bold]\n"
    )

    # ── Step 2: Select recovery method ────────────────────────────────────────

    mode = _select_recovery_mode()
    console.print()

    if mode == "1":
        return _recover_with_password_list(detected)
    else:
        return _recover_with_hints(detected)


if __name__ == "__main__":
    sys.exit(main())