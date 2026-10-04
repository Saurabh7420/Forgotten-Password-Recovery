# Password Candidate List

Place your candidate passwords in a file named **`passwords.txt`** inside this directory.

## Format

```
# Lines starting with # are comments — ignored by the tool
# Blank lines are also ignored
# One password per line
# File must be saved as UTF-8 (default for most text editors)

Summer2019!
mydog_fluffy
Fluffy@2018
correct horse battery staple
```

## Tips for Building Your Candidate List

Use an AI assistant such as **Gemini** or **ChatGPT** and prompt it with clues from your memory:

> *"I need a list of possible passwords. I remember it had my dog's name 'Fluffy', a year around 2018–2020, and possibly a special character. Generate 50 variations."*

Common patterns to cover:

| Pattern | Examples |
|---|---|
| Base word + year | `fluffy2019`, `fluffy2019!` |
| Capitalised | `Fluffy2019`, `FLUFFY2019` |
| Letter substitutions | `flu77y`, `fl@ffy`, `f1uffy` |
| Symbols appended | `fluffy!`, `fluffy#1` |
| Combined words | `fluffyhome`, `myfluffy` |

## Privacy

`passwords.txt` is listed in `.gitignore` and will **never** be committed to Git.  
Your candidates stay on your machine at all times.
