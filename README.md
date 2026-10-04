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
3. Save candidates → any .txt file inside password_list/
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
#    You can create any .txt file in password_list/
notepad password_list\passwords.txt

# 3. Place your locked file in locked_files/

# 4. Run
python main.py
```

---

## Supported File Formats

All verification is performed 100% locally on your machine.

| Format | Extension(s) | Library Used |
|---|---|---|
| ZIP Archive | `.zip` | `zipfile` (Python standard library) |
| PDF Document | `.pdf` | `pikepdf` |
| Microsoft Word Document | `.docx`, `.doc` | `msoffcrypto-tool` |
| Microsoft Excel Spreadsheet | `.xlsx`, `.xls` | `msoffcrypto-tool` |
| Microsoft PowerPoint Presentation | `.pptx`, `.ppt` | `msoffcrypto-tool` |
| 7-Zip Archive | `.7z` | `py7zr` |

---

## Project Structure

```text
Forgotten-Password-Recovery/
├── main.py                         # Entry point — run this
├── requirements.txt                # Dependencies
├── README.md                       # Documentation
├── LICENSE                         # MIT License
├── .gitignore                      # Prevents sensitive files from being committed
├── conftest.py                     # Pytest configuration
│
├── password_list/
│   └── README.md                   # Instructions for candidate lists
│
├── locked_files/
│   └── README.md                   # Supported formats & usage tips
│
├── results/
│   └── README.md                   # Recovery results — keep private
│
├── modules/                        # Core modular architecture
│   ├── __init__.py
│   ├── candidate_loader.py         # Loads candidate passwords from .txt files
│   ├── file_detector.py            # Detects supported file formats
│   ├── progress.py                 # Rich-based live terminal UI
│   └── verifier.py                 # Format-specific password verification
│
└── tests/                          # Pytest test suite (205 tests)
    ├── __init__.py
    ├── README.md
    ├── test_candidate_loader.py
    ├── test_file_detector.py
    ├── test_progress.py
    └── test_verifier.py
```

---

## Candidate List Format (.txt)

Create any `.txt` file inside `password_list/` (e.g. `passwords.txt` or `my_passwords.txt`):

```
# Lines starting with # are comments — ignored
# Blank lines are ignored
# One password per line, UTF-8 encoding

Summer2019!
MyPet_2018
fluffy@home
correct horse battery staple
```

* If multiple `.txt` files exist in `password_list/`, the tool prompts you to choose which list to test.
* **Tip**: Use an AI assistant (Gemini, ChatGPT) to brainstorm variations based on what you remember — including common substitutions (e→3, a→@, o→0), date variations, and capitalisation.

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

