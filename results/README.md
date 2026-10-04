# Recovery Results

When a password is successfully recovered, the result is **automatically saved** here  
as a timestamped plain-text file (e.g. `recovery_20260925_173012.txt`).

## Result File Contents

Each file contains:

```
Forgotten Password Recovery Assistant — Result
==================================================
Date/Time : 2026-09-25 17:30:12
File      : report_2019.pdf
Attempts  : 918
Elapsed   : 103.4s
Password  : YourRecoveredPassword

IMPORTANT: Keep this file private and delete it after use.
```

## ⚠️ Important Security Notes

- **Keep this directory private.** Do not share or commit result files.
- **Delete result files immediately after use** — they contain your recovered password in plain text.
- Result files are excluded from Git via `.gitignore`.

## Permissions

You may need to restrict folder permissions on shared machines:

```bash
# Windows (PowerShell)
icacls results /inheritance:d /grant:r "$env:USERNAME:(OI)(CI)F"
```
