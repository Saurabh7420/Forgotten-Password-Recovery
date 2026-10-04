# Forgotten Password Recovery Assistant

> **Purpose**: A fully-local, open-source Python tool that helps you recover access  
> to your **own** password-protected files by testing a user-supplied candidate list.
>
> ⚠️ This tool does **not** support online accounts, email, social media, or Wi-Fi passwords.

---

## How It Works

```
1. Clone/download this repository
2. Create your candidate list with help from memory or an AI assistant
3. Save candidates → password_list/passwords.txt
4. Place your locked file → locked_files/
5. Run: python main.py
6. Watch live progress in the terminal
7. If found: password is shown (masked) and auto-saved to results/
```

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your candidate passwords (one per line)
#    See password_list/README.md for format details
notepad password_list\passwords.txt

# 3. Place your locked file in locked_files/

# 4. Run
python main.py
```

---

## Supported File Formats (Phase 1)

| Format | Extension(s) | Library Used |
|---|---|---|
| ZIP Archive | `.zip` | `zipfile` (stdlib) |
| PDF Document | `.pdf` | `pikepdf` |
| Word Document | `.docx`, `.doc` | `msoffcrypto-tool` |
| Excel Spreadsheet | `.xlsx`, `.xls` | `msoffcrypto-tool` |
| PowerPoint | `.pptx`, `.ppt` | `msoffcrypto-tool` |
| 7-Zip Archive | `.7z` | `py7zr` |

---

## Directory Layout

```
├── main.py                        # Entry point — run this
├── passwords.txt                  # Sample template (copy to password_list/)
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
│
├── password_list/
│   ├── README.md                  # Instructions for the candidate list
│   └── passwords.txt              # ← YOUR candidate list goes here (not in Git)
│
├── locked_files/
│   ├── README.md                  # Supported formats & tips
│   └── your_locked_file.zip       # ← YOUR locked file goes here (not in Git)
│
├── results/
│   └── README.md                  # Auto-saved recovery results (keep private!)
│
├── modules/                       # Core logic — modular, one concern per file
│   ├── __init__.py
│   ├── candidate_loader.py        # Reads, strips, deduplicates passwords.txt
│   ├── file_detector.py           # Scans locked_files/, detects format
│   ├── progress.py                # Rich-based live terminal UI
│   └── verifier.py                # Dispatcher: routes to format handlers
│
└── tests/                         # pytest unit tests
    ├── test_candidate_loader.py
    ├── test_file_detector.py
    ├── test_progress.py
    └── test_verifier.py
```

---

## passwords.txt Format

```
# Lines starting with # are comments — ignored
# Blank lines are ignored
# One password per line, UTF-8 encoding

Summer2019!
MyPet_2018
fluffy@home
correct horse battery staple
```

**Tip**: Use an AI assistant (Gemini, ChatGPT) to brainstorm variations — include  
common substitutions (e→3, a→@, o→0), date variations, and capitalisation.

---

## Terminal UI

```
╔══════════════════════════════════════════════════════╗
║    Forgotten Password Recovery Assistant             ║
╚══════════════════════════════════════════════════════╝

  ✓ Locked file  : report_2019.pdf
  ✓ Format       : PDF Document
  ✓ Candidates   : 1,482 usable (3 duplicates removed)

  Testing report_2019.pdf ████████████░░░░  62% • 918/1482 • 0:01:43

  ╔═══════════════════════════════════════╗
  ║  ✓ Recovery Successful                ║
  ║  PASSWORD FOUND after 918 attempts    ║
  ║  Recovered : ●●●●●●●●●  (hidden)     ║
  ╚═══════════════════════════════════════╝

  Result auto-saved → results/recovery_20260925_173012.txt
  Press ENTER to reveal the password (or Ctrl+C to skip):
```

---

## Privacy & Security

| Guarantee | How |
|---|---|
| ✅ Fully local | No network calls at any point |
| ✅ Passwords never printed | Candidates are never echoed to the terminal |
| ✅ Password masked on success | Revealed only by explicit ENTER |
| ✅ Sensitive paths excluded from Git | `.gitignore` covers passwords, locked files, results |
| ✅ Delete results after use | `results/` files contain the recovered password |

---

## Running Tests

```bash
pytest tests/ -v
```

---

## License

[MIT](LICENSE) — see the LICENSE file for details.
