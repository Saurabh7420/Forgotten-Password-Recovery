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

import time
from typing import Callable

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.text import Text


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


class HintProgressUI:
    """
    Manages the continuous live progress display during hint-based password generation recovery.

    Displays:
    - Tested candidates out of total
    - Percentage completed
    - Remaining candidate count
    - Elapsed time (MM:SS or HH:MM:SS)
    - Estimated time remaining (ETA) based on measured attempt rate
    - Current status message
    """

    def __init__(
        self,
        total: int,
        console: Console | None = None,
        time_func: Callable[[], float] = time.monotonic,
    ) -> None:
        self.total: int = max(0, total)
        self.tested: int = 0
        self.console: Console = console or Console()
        self.time_func: Callable[[], float] = time_func
        self.start_time: float | None = None
        self._live: Live | None = None
        self.status: str = "Testing candidate..."
        self.header: str | None = None
        self.found: bool | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Begin live terminal display."""
        self.start_time = self.time_func()
        self.tested = 0
        self.status = "Testing candidate..."
        self.header = None
        self.found = None
        self._live = Live(
            self._build_renderable(),
            console=self.console,
            auto_refresh=False,
            transient=False,
        )
        self._live.start()

    def update(self, tested: int, status: str = "Testing candidate...") -> None:
        """Update tested count and status, refreshing the live display."""
        self.tested = tested
        self.status = status
        if self._live is not None:
            self._live.update(self._build_renderable(), refresh=True)

    def finish(self, success: bool, tested: int | None = None) -> None:
        """Finish recovery display with success or exhaustion status."""
        if tested is not None:
            self.tested = tested
        self.found = success
        if success:
            self.header = "PASSWORD FOUND"
            self.status = "Password found"
        else:
            self.header = "PASSWORD NOT FOUND"
            self.status = "All candidates exhausted"
            self.tested = self.total

        if self._live is not None:
            self._live.update(self._build_renderable(), refresh=True)
            self._live.stop()
            self._live = None

    def stop(self) -> None:
        """Stop the live display without final finish state."""
        if self._live is not None:
            self._live.stop()
            self._live = None

    # ── Rendering helper ──────────────────────────────────────────────────────

    def _build_renderable(self) -> Panel:
        elapsed = (self.time_func() - self.start_time) if self.start_time is not None else 0.0
        display_text = self.get_display_text(
            tested=self.tested,
            total=self.total,
            elapsed_seconds=elapsed,
            status=self.status,
            header=self.header,
        )
        border_style = "cyan"
        if self.found is True:
            border_style = "green"
        elif self.found is False:
            border_style = "yellow"

        return Panel(
            Text(display_text),
            border_style=border_style,
            expand=False,
        )

    # ── Pure calculation helpers (testable without Rich) ───────────────────────

    def percentage(self, tested: int) -> float:
        """Return completion percentage in [0.0, 100.0]."""
        if self.total == 0:
            return 0.0
        return min(100.0, (tested / self.total) * 100.0)

    def remaining(self, tested: int) -> int:
        """Return remaining candidates count."""
        return max(0, self.total - tested)

    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format seconds into MM:SS (or HH:MM:SS if >= 1 hour)."""
        total = max(0, int(seconds))
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    @classmethod
    def calculate_eta(cls, tested: int, total: int, elapsed_seconds: float) -> str:
        """
        Calculate estimated remaining time based on actual measured attempt rate.

        Returns 'Calculating...' at start or when rate cannot be computed.
        """
        if tested <= 0 or elapsed_seconds <= 0:
            return "Calculating..."
        rate = tested / elapsed_seconds
        if rate <= 0:
            return "Calculating..."
        rem = max(0, total - tested)
        if rem == 0:
            return "00:00"
        est_sec = rem / rate
        return cls.format_duration(est_sec)

    @classmethod
    def get_display_text(
        cls,
        tested: int,
        total: int,
        elapsed_seconds: float,
        status: str = "Testing candidate...",
        header: str | None = None,
    ) -> str:
        """Generate the exact formatted text block for the progress display."""
        pct = (tested / total * 100.0) if total > 0 else 0.0
        pct = min(100.0, pct)
        rem = max(0, total - tested)
        elapsed_str = cls.format_duration(elapsed_seconds)

        lines: list[str] = []
        if header:
            lines.append(header)
            lines.append("")

        lines.append(f"{'Tested':<16}: {tested} / {total}")
        lines.append(f"{'Progress':<16}: {pct:.2f}%")
        lines.append(f"{'Remaining':<16}: {rem}")
        lines.append(f"{'Elapsed Time':<16}: {elapsed_str}")

        if header is None:
            eta_str = cls.calculate_eta(tested, total, elapsed_seconds)
            lines.append(f"{'Estimated Left':<16}: {eta_str}")

        lines.append(f"{'Status':<16}: {status}")
        return "\n".join(lines)
