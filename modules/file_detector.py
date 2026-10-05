"""
file_detector.py
Scans the ``locked_files/`` directory for a supported password-protected file.

Responsibilities
----------------
- Enumerate all files in the target directory (non-recursive).
- Classify each file as supported (by extension) or unsupported.
- Skip hidden files, Word temporary ``~$`` lock files, ``README.md``,
  and ``.gitkeep`` sentinels silently.
- Return a single :class:`DetectedFile` for processing, or show an
  interactive Rich picker when multiple supported files are present.

Raises
------
FileDetectionError
    Whenever the directory is missing, not a directory, or contains no
    supported files.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple


# ──────────────────────────────────────────────────────────────────────────────
# Public exceptions
# ──────────────────────────────────────────────────────────────────────────────


class FileDetectionError(Exception):
    """Raised when the locked file cannot be detected."""


# ──────────────────────────────────────────────────────────────────────────────
# Supported extension registry
# ──────────────────────────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".zip": "ZIP Archive",
    ".pdf": "PDF Document",
    ".docx": "Word Document (OOXML)",
    ".xlsx": "Excel Spreadsheet (OOXML)",
    ".pptx": "PowerPoint Presentation (OOXML)",
    ".doc": "Word Document (Legacy)",
    ".xls": "Excel Spreadsheet (Legacy)",
    ".ppt": "PowerPoint Presentation (Legacy)",
    ".7z": "7-Zip Archive",
}


# File names (lowercase) silently skipped during scanning
_SKIP_NAMES: frozenset[str] = frozenset(
    {
        "readme.md",
        ".gitkeep",
        ".gitignore",
    }
)


# ──────────────────────────────────────────────────────────────────────────────
# Result type
# ──────────────────────────────────────────────────────────────────────────────


class DetectedFile(NamedTuple):
    """Represents a successfully detected locked file."""

    path: Path
    format_name: str
    extension: str


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────


def _is_supported(path: Path) -> bool:
    """Return True when the file has a supported extension."""
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def _is_temporary_word_file(path: Path) -> bool:
    """
    Return True for Microsoft Word temporary/owner files.

    Word commonly creates files such as:

        ~$document.docx

    These are temporary lock/owner files, not actual user documents,
    and should never be offered as recovery targets.
    """
    return path.name.startswith("~$")


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def scan_locked_files(
    directory: str | Path,
) -> tuple[list[DetectedFile], list[str]]:
    """
    Scan *directory* for supported locked files (non-recursive).

    Parameters
    ----------
    directory:
        The directory to scan (typically ``locked_files/``).

    Returns
    -------
    supported:
        :class:`DetectedFile` entries for every recognised file found.

    unsupported:
        Plain file-name strings for every file that was found but whose
        extension is not in :data:`SUPPORTED_EXTENSIONS`.

    Raises
    ------
    FileDetectionError
        If *directory* does not exist or is not a directory.
    """

    directory = Path(directory)

    if not directory.exists():
        raise FileDetectionError(
            f"Directory not found: '{directory}'\n"
            "  → The 'locked_files/' directory is missing from the project."
        )

    if not directory.is_dir():
        raise FileDetectionError(
            f"'{directory}' is not a directory."
        )

    supported: list[DetectedFile] = []
    unsupported: list[str] = []

    for item in sorted(directory.iterdir()):

        # Only process regular files.
        if not item.is_file():
            continue

        # Skip hidden OS artefacts and known sentinel files.
        if item.name.startswith("."):
            continue

        if item.name.lower() in _SKIP_NAMES:
            continue

        # IMPORTANT:
        # Ignore Microsoft's temporary Word lock/owner files.
        if _is_temporary_word_file(item):
            continue

        if _is_supported(item):
            ext = item.suffix.lower()

            supported.append(
                DetectedFile(
                    path=item,
                    format_name=SUPPORTED_EXTENSIONS[ext],
                    extension=ext,
                )
            )
        else:
            unsupported.append(item.name)

    return supported, unsupported


def detect_locked_file(
    directory: str | Path,
) -> DetectedFile:
    """
    Detect a single locked file, prompting the user if multiple are found.

    Parameters
    ----------
    directory:
        The directory to scan (typically ``locked_files/``).

    Returns
    -------
    DetectedFile
        The file chosen for processing.

    Raises
    ------
    FileDetectionError
        If no supported file is found or the directory is missing.
    """

    supported, unsupported = scan_locked_files(directory)

    if not supported:

        ext_list = "  ".join(
            SUPPORTED_EXTENSIONS.keys()
        )

        msg = (
            f"No supported files found in '{directory}'.\n"
            f"  → Supported extensions: {ext_list}"
        )

        if unsupported:
            msg += (
                f"\n  → Unsupported file(s) also found: "
                f"{', '.join(unsupported)}"
            )

        raise FileDetectionError(msg)

    # Exactly one valid file.
    if len(supported) == 1:
        return supported[0]

    # ── Interactive picker for multiple files ─────────────────────────────────

    from rich.console import Console
    from rich.table import Table
    from rich.prompt import IntPrompt

    console = Console()

    console.print(
        "\n"
        "[bold yellow]"
        "Multiple locked files detected — please pick one:"
        "[/bold yellow]\n"
    )

    table = Table(
        show_lines=True,
        expand=False,
    )

    table.add_column(
        "#",
        style="bold cyan",
        width=4,
    )

    table.add_column(
        "Filename",
        style="white",
    )

    table.add_column(
        "Format",
        style="green",
    )

    for i, df in enumerate(supported, start=1):
        table.add_row(
            str(i),
            df.path.name,
            df.format_name,
        )

    console.print(table)

    choice = IntPrompt.ask(
        "\nEnter the number of the file to process",
        choices=[
            str(i)
            for i in range(1, len(supported) + 1)
        ],
    )

    return supported[choice - 1]


def detect_file_from_path(file_path: str | Path) -> DetectedFile:
    """
    Validate and detect a locked file from an explicit file path provided by the user.

    Parameters
    ----------
    file_path:
        Path to the locked file (may include surrounding quotes or whitespace).

    Returns
    -------
    DetectedFile
        The detected file details (path, format_name, extension).

    Raises
    ------
    FileDetectionError
        If the file does not exist, is not a regular file, is a temporary file,
        or has an unsupported file format.
    """
    raw_str = str(file_path).strip()
    # Strip quotes that might be added when paths are copied in terminal / file explorers
    if (raw_str.startswith('"') and raw_str.endswith('"')) or (
        raw_str.startswith("'") and raw_str.endswith("'")
    ):
        raw_str = raw_str[1:-1].strip()

    if not raw_str:
        raise FileDetectionError("No file path provided. Please enter a valid file path.")

    target_path = Path(raw_str)

    if not target_path.exists():
        raise FileDetectionError(
            f"File not found: '{raw_str}'\n"
            "  → Please check the path and ensure the file exists."
        )

    if not target_path.is_file():
        raise FileDetectionError(
            f"'{raw_str}' is a directory, not a regular file.\n"
            "  → Please specify the path to a specific locked file."
        )

    if _is_temporary_word_file(target_path):
        raise FileDetectionError(
            f"'{target_path.name}' is a Microsoft Word temporary lock file (~$), not a valid document."
        )

    if not _is_supported(target_path):
        ext_list = "  ".join(SUPPORTED_EXTENSIONS.keys())
        raise FileDetectionError(
            f"Unsupported file format '{target_path.suffix}' for '{target_path.name}'.\n"
            f"  → Supported extensions: {ext_list}"
        )

    ext = target_path.suffix.lower()
    return DetectedFile(
        path=target_path,
        format_name=SUPPORTED_EXTENSIONS[ext],
        extension=ext,
    )