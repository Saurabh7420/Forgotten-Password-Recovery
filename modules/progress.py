"""
progress.py
Rich-based live terminal progress UI for the recovery process.

Responsibilities
----------------
- Render a live progress bar (spinner + bar + count + elapsed time).
- Expose pure helper methods (``percentage``, ``format_elapsed``) that can be
  tested without any terminal rendering.
- Keep rendering completely separate from business logic.

Usage
-----
    ui = ProgressUI()
    ui.start(total=1500, file_name="report.pdf")

    for i, candidate in enumerate(candidates, start=1):
        ui.update(tested=i)
        if verify(path, candidate):
            break

    ui.stop()
"""

from __future__ import annotations

from rich.console import Console
from rich.live import Live
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)


class ProgressUI:
    """
    Manages the live Rich terminal display during password recovery.

    The class is intentionally thin around Rich so that unit tests can
    exercise the pure-calculation helpers (``percentage``, ``format_elapsed``)
    without starting any live rendering.
    """

    def __init__(self, console: Console | None = None) -> None:
        self._console: Console = console or Console()
        self._progress: Progress | None = None
        self._task_id: int | None = None
        self._live: Live | None = None
        self._total: int = 0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self, total: int, file_name: str = "") -> None:
        """
        Begin the live progress display.

        Parameters
        ----------
        total:
            Total number of candidates to process.
        file_name:
            Optional file name to show in the progress label.
        """
        self._total = total
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=self._console,
            transient=False,
        )
        label = (
            f"Testing [bold]{file_name}[/bold]"
            if file_name
            else "Testing candidates…"
        )
        self._task_id = self._progress.add_task(label, total=total)
        self._live = Live(
            self._progress,
            console=self._console,
            refresh_per_second=10,
        )
        self._live.start()

    def update(self, tested: int) -> None:
        """
        Advance the progress bar to *tested* candidates processed.

        Parameters
        ----------
        tested:
            Cumulative number of candidates tested so far.
        """
        if self._progress is not None and self._task_id is not None:
            self._progress.update(self._task_id, completed=tested)

    def stop(self) -> None:
        """Stop the live display and release the terminal."""
        if self._live is not None:
            self._live.stop()
            self._live = None

    # ── Pure helpers (testable without rendering) ─────────────────────────────

    def percentage(self, tested: int) -> float:
        """
        Return completion percentage in the range ``[0.0, 100.0]``.

        Returns ``0.0`` when :attr:`_total` is zero to avoid division errors.

        Parameters
        ----------
        tested:
            Cumulative number of candidates tested so far.
        """
        if self._total == 0:
            return 0.0
        return min(100.0, (tested / self._total) * 100.0)

    @staticmethod
    def format_elapsed(seconds: float) -> str:
        """
        Format a duration in seconds as ``HH:MM:SS``.

        Negative values are clamped to zero.

        Parameters
        ----------
        seconds:
            Elapsed time in seconds (may be fractional; truncated to int).
        """
        total = max(0, int(seconds))
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
