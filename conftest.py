"""
conftest.py — pytest root configuration.

Inserts the project root into sys.path so that `modules.*` is importable
from any test file without needing an editable install.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
