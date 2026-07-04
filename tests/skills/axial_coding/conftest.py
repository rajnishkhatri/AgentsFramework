"""Import the axial-coding bundle scripts by file path.

The scripts live under ``docs/skills/agentsframework-axial-coding/scripts/`` —
outside the ``scripts.`` import root — so tests load them via importlib, the
same idiom used by ``tests/scripts/test_build_memory_multisession_corpus.py``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_BUNDLE = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "skills"
    / "agentsframework-axial-coding"
    / "scripts"
)


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, _BUNDLE / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
