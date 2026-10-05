"""
recovery_summary.py
Summary formatter and display component for Version 2 hint-based recovery sessions.

Overview
--------
Presents a clear, structured summary after a hint-based recovery execution finishes,
covering both SUCCESS and EXHAUSTION / FAILURE outcomes.

Invariants:
- Uses actual attempt counts from `StageRecoveryResult`, distinct from search-space available counts.
- Displays exact stage names (Stage 1 — Direct Hint Search, etc.).
- Displays path to the session's single attempts file.
- Preserves the exact message: "Password not found using the provided hints and configured rules." on exhaustion.
- Never prints the password multiple times or creates new summary files.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from modules.search_space import SearchSpaceResult
from modules.search_stages import STAGE_NAMES, StageRecoveryResult

if TYPE_CHECKING:
    pass


EXHAUSTION_MESSAGE = "Password not found using the provided hints and configured rules."


def get_stage_attempt_counts(result: StageRecoveryResult) -> tuple[int, int, int]:
    """
    Extract (stage_1_attempts, stage_2_attempts, stage_3_attempts) from result.
    """
    s1 = result.stage_stats[1].candidates_tested if 1 in result.stage_stats else 0
    s2 = result.stage_stats[2].candidates_tested if 2 in result.stage_stats else 0
    s3 = result.stage_stats[3].candidates_tested if 3 in result.stage_stats else 0
    return s1, s2, s3


def format_recovery_summary(
    result: StageRecoveryResult,
    search_space: SearchSpaceResult | None = None,
    attempts_file: Path | str | None = None,
) -> str:
    """
    Format the recovery execution summary as a plaintext string.

    Parameters
    ----------
    result:
        StageRecoveryResult returned by `execute_progressive_recovery`.
    search_space:
        Optional theoretical SearchSpaceResult from `calculate_search_space`.
    attempts_file:
        Optional path to the session attempts file.

    Returns
    -------
    str
        Human-readable summary text.
    """
    s1_attempts, s2_attempts, s3_attempts = get_stage_attempt_counts(result)
    attempts_path_str = str(attempts_file) if attempts_file is not None else "None"

    lines: list[str] = []

    if result.success:
        lines.append("==================================================")
        lines.append("                 PASSWORD FOUND")
        lines.append("==================================================")
        lines.append(f"Password: {result.found_password}")
        stage_name = STAGE_NAMES.get(result.successful_stage or 1, f"Stage {result.successful_stage}")
        lines.append(f"Stage: {stage_name}")
        lines.append(f"Attempts: {result.total_attempts:,}")
        lines.append(f"Attempts File: {attempts_path_str}")
        lines.append("")
        lines.append("Stage Attempts Breakdown:")
        lines.append(f"  Stage 1 Attempts: {s1_attempts:,}")
        lines.append(f"  Stage 2 Attempts: {s2_attempts:,}")
        lines.append(f"  Stage 3 Attempts: {s3_attempts:,}")
    else:
        lines.append("==================================================")
        lines.append("               PASSWORD NOT FOUND")
        lines.append("==================================================")
        lines.append(EXHAUSTION_MESSAGE)
        lines.append("")
        lines.append(f"Attempts: {result.total_attempts:,}")
        lines.append(f"Attempts File: {attempts_path_str}")
        lines.append("")
        lines.append("Stage Attempts Breakdown:")
        lines.append(f"  Stage 1 Attempts: {s1_attempts:,}")
        lines.append(f"  Stage 2 Attempts: {s2_attempts:,}")
        lines.append(f"  Stage 3 Attempts: {s3_attempts:,}")

    if search_space is not None:
        lines.append("")
        lines.append("Configured Search Space:")
        lines.append(f"  Stage 1 Candidates Available: {search_space.stage1_count:,}")
        lines.append(f"  Stage 2 Candidates Available: {search_space.stage2_count:,}")
        lines.append(f"  Stage 3 Candidates Available: {search_space.stage3_count:,}")
        lines.append(f"  Total Distinct Candidates Available: {search_space.total_distinct_count:,}")

    return "\n".join(lines)


def display_recovery_summary(
    result: StageRecoveryResult,
    search_space: SearchSpaceResult | None = None,
    attempts_file: Path | str | None = None,
    console: Console | None = None,
) -> None:
    """
    Render and print the formatted recovery summary to console.

    Parameters
    ----------
    result:
        StageRecoveryResult returned by `execute_progressive_recovery`.
    search_space:
        Optional SearchSpaceResult from `calculate_search_space`.
    attempts_file:
        Optional path to the session attempts file.
    console:
        Rich Console instance. If None, creates a default Console.
    """
    if console is None:
        console = Console()

    s1_attempts, s2_attempts, s3_attempts = get_stage_attempt_counts(result)
    attempts_path_str = str(attempts_file) if attempts_file is not None else "None"

    if result.success:
        stage_name = STAGE_NAMES.get(result.successful_stage or 1, f"Stage {result.successful_stage}")
        content = (
            f"[bold green]✓ Password Found[/bold green]\n\n"
            f"  Password      : [bold cyan]{result.found_password}[/bold cyan]\n"
            f"  Stage         : [bold]{stage_name}[/bold]\n"
            f"  Attempts      : [bold yellow]{result.total_attempts:,}[/bold yellow]\n"
            f"  Attempts File : [dim]{attempts_path_str}[/dim]\n\n"
            f"[bold]Actual Stage Attempts:[/bold]\n"
            f"  Stage 1 Attempts : {s1_attempts:,}\n"
            f"  Stage 2 Attempts : {s2_attempts:,}\n"
            f"  Stage 3 Attempts : {s3_attempts:,}\n"
        )
        if search_space is not None:
            content += (
                f"\n[bold]Configured Search Space:[/bold]\n"
                f"  Stage 1 Candidates Available       : {search_space.stage1_count:,}\n"
                f"  Stage 2 Candidates Available       : {search_space.stage2_count:,}\n"
                f"  Stage 3 Candidates Available       : {search_space.stage3_count:,}\n"
                f"  Total Distinct Candidates Available : {search_space.total_distinct_count:,}\n"
            )

        console.print(
            Panel(
                content.strip(),
                title="✓ Recovery Summary",
                border_style="green",
                expand=False,
            )
        )
    else:
        content = (
            f"[bold red]✗ {EXHAUSTION_MESSAGE}[/bold red]\n\n"
            f"  Attempts      : [bold yellow]{result.total_attempts:,}[/bold yellow]\n"
            f"  Attempts File : [dim]{attempts_path_str}[/dim]\n\n"
            f"[bold]Actual Stage Attempts:[/bold]\n"
            f"  Stage 1 Attempts : {s1_attempts:,}\n"
            f"  Stage 2 Attempts : {s2_attempts:,}\n"
            f"  Stage 3 Attempts : {s3_attempts:,}\n"
        )
        if search_space is not None:
            content += (
                f"\n[bold]Configured Search Space:[/bold]\n"
                f"  Stage 1 Candidates Available       : {search_space.stage1_count:,}\n"
                f"  Stage 2 Candidates Available       : {search_space.stage2_count:,}\n"
                f"  Stage 3 Candidates Available       : {search_space.stage3_count:,}\n"
                f"  Total Distinct Candidates Available : {search_space.total_distinct_count:,}\n"
            )

        console.print(
            Panel(
                content.strip(),
                title="✗ Recovery Summary",
                border_style="red",
                expand=False,
            )
        )
