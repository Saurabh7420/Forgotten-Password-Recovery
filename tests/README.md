# Tests

Unit tests for the Forgotten Password Recovery Assistant, using `pytest`.

## Running All Tests

```bash
# From the project root directory
pytest tests/ -v
```

## Test Files

| File | What It Tests |
|---|---|
| `test_candidate_loader.py` | Loading, blank stripping, comment skipping, deduplication, edge cases |
| `test_file_detector.py` | Directory scanning, extension classification, error handling, extension case-sensitivity |
| `test_progress.py` | Percentage calculation, time formatting (pure functions, no rendering) |
| `test_verifier.py` | Dispatcher routing, stub behaviour, format registry completeness |

## Design Notes

- All tests use `pytest`'s built-in `tmp_path` fixture — no real locked files or passwords are used.
- Rich live rendering is **not** tested (it requires an interactive terminal).
- Pure-calculation helpers (`percentage`, `format_elapsed`) are tested in isolation.
- Verification handler stubs are tested to confirm they raise `NotImplementedError` (Phase 1 contract).

## Coverage

```bash
pip install pytest-cov
pytest tests/ -v --cov=modules --cov-report=term-missing
```
