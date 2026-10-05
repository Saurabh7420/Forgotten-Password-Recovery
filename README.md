# Forgotten Password Recovery Assistant

> **Purpose**: A local, authorized password-recovery assistant designed to help you recover access to your **own** password-protected files when you have forgotten or misplaced your password.
>
> ⚠️ **Scope Notice**: This tool is designed strictly for local files owned or authorized by the user. It does **not** support online accounts, cloud services, email accounts, social media platforms, Wi-Fi networks, or remote systems. It does not guarantee recovery of arbitrary or unknown passwords.

---

## Important Security and Privacy Notice

- **100% Local Execution**: All operations run entirely on your local computer. No network connections, internet requests, or external API calls are made at any point.
- **Local File Access**: Protected files are read directly from your local filesystem path. Files are **never** uploaded to any external server or cloud service.
- **Git and GitHub Safety**: Actual password-protected files, candidate lists, passwords, and recovery history files must **never** be committed to Git or pushed to GitHub. The repository includes a configured `.gitignore` to keep user data private.
- **Session Privacy**: Password candidates and recovery logs are stored only on your local machine and can be deleted immediately upon session completion.

---

## Supported File Formats

Verification handlers run locally using established Python libraries:

| Format Name | File Extension(s) | Underlying Library |
|---|---|---|
| ZIP Archive | `.zip` | `zipfile` (Python Standard Library) |
| PDF Document | `.pdf` | `pikepdf` |
| Microsoft Word Document | `.docx`, `.doc` | `msoffcrypto-tool` |
| Microsoft Excel Spreadsheet | `.xlsx`, `.xls` | `msoffcrypto-tool` |
| Microsoft PowerPoint Presentation | `.pptx`, `.ppt` | `msoffcrypto-tool` |
| 7-Zip Archive | `.7z` | `py7zr` |

---

## Requirements and Installation

### Prerequisites
- Python 3.10 or newer (tested on Python 3.14 on Windows)

### Installation

```bash
# Clone or download the repository
git clone https://github.com/Saurabh7420/Forgotten-Password-Recovery.git
cd Forgotten-Password-Recovery

# Install dependencies
pip install -r requirements.txt
```

---

## Running the Program

Launch the recovery assistant:

```bash
python main.py
```

### Locked File Selection
The application prompts you to select the target file:
- **`[1] Select file from locked_files/`**: Automatically detects a supported file placed in the `locked_files/` directory.
- **`[2] Enter full file path`**: Allows entering an absolute or relative path to a local file anywhere on your machine (e.g., `C:\Users\Username\Documents\protected.docx`).

> **Note**: Entering a full file path does **not** upload the file anywhere. The assistant opens and verifies the file entirely on your local machine.

---

## Recovery Modes

After selecting the target file, choose your preferred recovery method:

```text
Select recovery method:
  [1] Existing Password List
  [2] Generate Passwords from Hints
```

### Mode 1: Existing Password List
Tests candidate passwords loaded from a plain text (`.txt`) file in `password_list/` (one candidate per line). Ideal when you already have a predefined wordlist or candidate export.

### Mode 2: Generate Passwords from Hints
An interactive generator that builds focused candidate passwords based on fragments and patterns you remember.

---

## Hint-Based Recovery

When using **Mode 2**, the assistant collects hints across the following fields:

1. **Name**: Names, nicknames, or personal keywords (e.g., `ayush`, `saniya`). Multiple entries can be comma-separated.
2. **Word**: Memorable dictionary words, pet names, or places (e.g., `admin`, `welcome`).
3. **Number**: Numbers, years, dates, or PINs (e.g., `7210`, `123`, `0`). Multiple entries can be comma-separated.
4. **Special Character**: Symbols used in the password (e.g., `@`, `#`, `*`, `!`).
5. **Known Prefix**: Leading characters or symbols you know the password begins with (e.g., `@A`, `Pass`).
6. **Known Suffix**: Trailing characters or symbols you know the password ends with (e.g., `10`, `!`).
7. **Minimum Password Length**: Optional minimum character limit (e.g., `8`).
8. **Maximum Password Length**: Optional maximum character limit (e.g., `12`).

### Hint Conventions:
- **`NONE`**: Enter `NONE` to disable or skip any hint category (case-insensitive).
- **`0`**: Treated as a **valid numeric value** (e.g., PINs, year digits, single digits), not as a disabled marker.

---

## Progressive Search Process

Hint-based candidate generation operates across three progressive stages:

- **Stage 1 — Direct Hint Search**: Generates direct combinations of your base tokens, numbers, special characters, prefixes, and suffixes.
- **Stage 2 — Hint Transformation Search (Ranked Combinations)**: Applies common casing transformations (lowercase, uppercase, title case, swap case), delimiter insertions, and standard substitutions.
- **Stage 3 — Extended Search**: Evaluates compound pairings, reversed tokens, repeated numbers, and 2-digit/4-digit patterns.

Candidates are generated lazily, ranked deterministically based on hint fidelity, filtered by length boundaries, and tested sequentially. Verification terminates immediately upon finding the correct password.

---

## Live Progress Display

During hint-based verification, the terminal displays real-time progress metrics updated live:

```text
╭────────────────────────────────────────────╮
│ Testing candidate passwords...             │
│                                            │
│ Tested          : 110 / 884                │
│ Progress        : 12.44%                   │
│ Remaining       : 774                      │
│ Elapsed Time    : 00:18                    │
│ Estimated Left  : 02:06                    │
│ Status          : Testing candidate...     │
╰────────────────────────────────────────────╯
```

---

## Additional Hints & Multi-Round Recovery

If all generated candidates in a round are tested and the password is not found, the application does not immediately terminate:

```text
Password not found using the provided hints and configured rules.

Would you like to provide additional hints and continue?

  [1] Yes
  [2] No
```

- **`[1] Yes`**: Enter updated or additional hints to generate new candidate variations.
- **Deduplication Invariant**: Candidates tested in earlier rounds are tracked in a persistent set (`seen_candidates`). The assistant automatically skips any candidate already tested, ensuring zero redundant attempts across rounds.
- **`[2] No`**: Ends the session and displays the final recovery summary.

---

## Round-Wise Recovery History

Each recovery round maintains its own isolated, human-readable history file in the `results/` folder:

### File Naming
- **Unsuccessful Round**: `results/Round_1.txt`, `results/Round_2.txt`, `results/Round_3.txt`
- **Successful Round**: `results/Round_4_SUCCESS.txt` (contains only candidates tested in Round 4, ending with the winning password).

### File Contents
Each round file contains only the candidates actually tested during that specific round, in exact test order:

```text
========================================
RECOVERY ROUND 1
========================================

Status: PASSWORD NOT FOUND

Candidates Tested: 606

----------------------------------------
TESTED PASSWORD CANDIDATES
----------------------------------------

Jito_@_7
Jito_#_7
...

----------------------------------------
END OF ROUND 1
----------------------------------------
```

### Save / Delete Prompt
At the end of a session, the user is prompted whether to keep or delete the session history:

```text
Would you like to save the recovery history?

  [1] Yes — Save all round files
  [2] No  — Delete all round files
```

- **Choosing `[1] Yes`**: Retains the separate round files in `results/`.
- **Choosing `[2] No`**: Deletes **only** the history files created during the current session. Files from other sessions, `results/README.md`, and unrelated files are preserved.

---

## Local Directory Structure

```text
Forgotten-Password-Recovery/
├── main.py                     # Application entry point
├── requirements.txt            # Python package dependencies
├── README.md                   # Project documentation
├── LICENSE                     # MIT License
├── .gitignore                  # Git privacy rules
├── conftest.py                 # Pytest configuration
│
├── locked_files/               # Directory to place locked target files
│   └── README.md
│
├── password_list/              # Directory for Mode 1 .txt password lists
│   └── README.md
│
├── results/                    # Output directory for round histories and results
│   └── README.md
│
├── modules/                    # Core modular application logic
│   ├── __init__.py
│   ├── attempt_logger.py       # Session attempt & round history management
│   ├── candidate_generator.py  # 3-stage progressive candidate generator
│   ├── candidate_loader.py     # Password list parser (Mode 1)
│   ├── candidate_ranker.py     # Deterministic candidate scoring & ranking
│   ├── file_detector.py        # File format detection and validation
│   ├── hint_collector.py       # Interactive hint collection & validation
│   ├── progress.py             # Live Rich progress terminal UI
│   ├── recovery_summary.py     # Formatted recovery summary display
│   ├── search_space.py         # Search-space calculation & analysis
│   ├── search_stages.py        # Progressive recovery execution engine
│   └── verifier.py             # Format-specific password verifiers
│
└── tests/                      # Comprehensive test suite (486 tests)
    ├── __init__.py
    ├── README.md
    ├── test_additional_hints.py
    ├── test_attempt_logger.py
    ├── test_candidate_generator.py
    ├── test_candidate_loader.py
    ├── test_candidate_ranker.py
    ├── test_end_to_end_v2.py
    ├── test_file_detector.py
    ├── test_file_selection_ui.py
    ├── test_hint_collector.py
    ├── test_hint_progress.py
    ├── test_password_not_found.py
    ├── test_progress.py
    ├── test_recovery_mode_ui.py
    ├── test_recovery_summary.py
    ├── test_round_history.py
    ├── test_search_space.py
    ├── test_search_stages.py
    └── test_verifier.py
```

> **Reminder**: Keep personal files in `locked_files/`, `password_list/`, and `results/` local. Do not commit personal data.

---

## Automated Testing

The project includes an automated test suite verifying all components, generators, rankers, search-space calculations, multi-round continuation, round-history logging, and format verifiers.

Run all tests:

```bash
python -m pytest -q
```

**Test Suite Status**: `486 passed` (0 failures, 100% deterministic local execution).

---

## License

This project is licensed under the [MIT License](LICENSE). See the LICENSE file for details.
