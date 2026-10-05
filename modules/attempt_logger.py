"""
attempt_logger.py
Session-based raw attempt logger for Version 2 hint-based password recovery.

Guarantees & Invariants
-----------------------
- Exactly ONE attempts file per recovery session: `results/attempts_YYYYMMDD_HHMMSS.txt`.
- All stages (Stage 1, Stage 2, Stage 3) write to the same session file.
- Logs candidates ONLY at the point of verification (immediately before passing to verifier).
- Preserves exact verification order (one raw candidate string per line, no extra formatting).
- Flushes writes safely on each attempt for exception resilience.
- Context-manager support and clean resource lifecycle (`close()`).
- Pure local file I/O with UTF-8 encoding (zero network calls, zero external APIs).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import TextIO


DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


class AttemptLogger:
    """
    Manages recording of verified candidate passwords during a recovery session.
    """

    def __init__(
        self,
        output_dir: Path | str | None = None,
        timestamp: str | None = None,
        filename: str | None = None,
    ) -> None:
        """
        Initialize the attempt logger for a new recovery session.

        Parameters
        ----------
        output_dir:
            Directory where the attempts file will be saved. Defaults to `results/`.
        timestamp:
            Optional custom timestamp string in format `YYYYMMDD_HHMMSS`. If omitted,
            the current local datetime is formatted.
        filename:
            Optional explicit filename override. If omitted, uses `attempts_{timestamp}.txt`.
        """
        self.output_dir = Path(output_dir) if output_dir is not None else DEFAULT_RESULTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.timestamp = timestamp

        if filename is None:
            filename = f"attempts_{self.timestamp}.txt"
        self.filename = filename

        self.file_path: Path = self.output_dir / self.filename
        self._file: TextIO | None = open(self.file_path, mode="a", encoding="utf-8", newline="\n")
        self.attempts_count: int = 0
        self._closed: bool = False

    def log_attempt(self, candidate: str) -> None:
        """
        Log a candidate password that is being submitted to the verifier.

        Parameters
        ----------
        candidate:
            The raw candidate password string being verified.
        """
        if self._closed or self._file is None:
            raise RuntimeError("Cannot log attempt to a closed AttemptLogger session.")

        self._file.write(f"{candidate}\n")
        self._file.flush()
        self.attempts_count += 1

    def close(self) -> None:
        """Close the attempts file handle safely."""
        if not self._closed and self._file is not None:
            try:
                self._file.flush()
                self._file.close()
            finally:
                self._closed = True
                self._file = None

    def __enter__(self) -> AttemptLogger:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        status = "closed" if self._closed else "open"
        return f"<AttemptLogger path='{self.file_path.name}' attempts={self.attempts_count} status='{status}'>"


class RoundHistoryLogger:
    """
    Manages recording of tested candidates for a specific recovery round in
    a human-readable history file `Round_<round_number>.txt` (or `Round_<round_number>_SUCCESS.txt`).
    """

    def __init__(
        self,
        output_dir: Path | str,
        round_number: int,
        session_timestamp: str | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.round_number = round_number
        self.session_timestamp = session_timestamp

        if session_timestamp:
            self.filename = f"Round_{round_number}_{session_timestamp}.txt"
        else:
            self.filename = f"Round_{round_number}.txt"

        self.file_path: Path = self.output_dir / self.filename
        self.tested_candidates: list[str] = []
        self._finalized: bool = False

        # Ensure file exists at the beginning of the round
        if not self.file_path.exists():
            self.file_path.touch()

    def log_attempt(self, candidate: str) -> None:
        """
        Record a candidate password tested in this round.
        """
        self.tested_candidates.append(candidate)

    def finalize(
        self,
        success: bool,
        found_password: str | None = None,
        successful_stage_name: str | None = None,
        attempt_in_round: int | None = None,
    ) -> Path:
        """
        Write the complete formatted round history to disk.
        If success=True, the round file is named Round_<N>_SUCCESS.txt.
        """
        if self._finalized:
            return self.file_path

        target_path = self.file_path
        if success:
            if self.session_timestamp:
                success_filename = f"Round_{self.round_number}_SUCCESS_{self.session_timestamp}.txt"
            else:
                success_filename = f"Round_{self.round_number}_SUCCESS.txt"

            success_path = self.output_dir / success_filename

            if self.file_path.exists() and self.file_path != success_path:
                try:
                    self.file_path.unlink()
                except OSError:
                    pass

            self.filename = success_filename
            self.file_path = success_path
            target_path = success_path

        lines: list[str] = [
            "=" * 40,
            f"RECOVERY ROUND {self.round_number}",
            "=" * 40,
            "",
        ]

        if success:
            lines.append("Status: PASSWORD FOUND")
            lines.append("")
            lines.append(f"Successful Candidate: {found_password or ''}")
            lines.append(f"Stage: {successful_stage_name or ''}")
            lines.append(
                f"Attempt: {attempt_in_round if attempt_in_round is not None else len(self.tested_candidates)}"
            )
        else:
            lines.append("Status: PASSWORD NOT FOUND")
            lines.append("")
            lines.append(f"Candidates Tested: {len(self.tested_candidates)}")

        lines.append("")
        lines.append("-" * 40)
        lines.append("TESTED PASSWORD CANDIDATES")
        lines.append("-" * 40)
        lines.append("")

        for cand in self.tested_candidates:
            lines.append(cand)

        lines.append("")
        lines.append("-" * 40)
        lines.append(f"END OF ROUND {self.round_number}")
        lines.append("-" * 40)
        lines.append("")

        target_path.write_text("\n".join(lines), encoding="utf-8")
        self._finalized = True
        return self.file_path


class SessionHistoryManager:
    """
    Coordinates round-history loggers and success files for a multi-round recovery session.
    Tracks all files created during the current session to ensure clean, isolated deletion
    if requested by the user.
    """

    def __init__(
        self,
        output_dir: Path | str | None = None,
        session_timestamp: str | None = None,
    ) -> None:
        self.output_dir = Path(output_dir) if output_dir is not None else DEFAULT_RESULTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session_timestamp = session_timestamp
        self.round_loggers: list[RoundHistoryLogger] = []
        self.created_files: list[Path] = []

    def track_file(self, path: Path) -> None:
        """Track a file created during this session for cleanup management."""
        if path not in self.created_files:
            self.created_files.append(path)

    def start_round(self, round_number: int) -> RoundHistoryLogger:
        """
        Start a new round history logger and track its file path.
        """
        logger = RoundHistoryLogger(
            output_dir=self.output_dir,
            round_number=round_number,
            session_timestamp=self.session_timestamp,
        )
        self.round_loggers.append(logger)
        self.track_file(logger.file_path)
        return logger

    def delete_session_files(self) -> list[Path]:
        """
        Delete ONLY the files created during this session.
        Returns the list of deleted paths.
        """
        # Collect all files including finalized round files
        all_targets: list[Path] = list(self.created_files)
        for logger in self.round_loggers:
            if logger.file_path not in all_targets:
                all_targets.append(logger.file_path)

        deleted: list[Path] = []
        for path in all_targets:
            try:
                if path.exists() and path.is_file():
                    path.unlink()
                    deleted.append(path)
            except OSError:
                pass
        return deleted

