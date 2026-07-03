"""Architecture gate: no reader-without-writer config knobs.

Real failure this traces to (2026-07-02): ``user_max_cost_per_task`` was
designed in PLAN.md as a per-task budget override, read in two places in
``orchestration/react_loop.py`` — one of them from a hardcoded empty dict —
while no caller ever wrote the key into ``config["configurable"]``. The knob
was silently dead; the global ``AgentConfig.max_cost_usd`` cap was the only
budget actually enforced. Decision: the knob was deleted, not wired (see
``docs/adr/decisions.md``).

This test ratchets that deletion: the string must not reappear in runtime
source. To legitimately reintroduce the knob, ship the *writer* (the runtime
adapter putting it into ``configurable``) in the same change, then remove the
string from ``_DEAD_KNOBS`` here — that is the conscious decision the ratchet
exists to force.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Knobs that were deleted as reader-without-writer dead code. Source dirs are
# the runtime layers a read could hide in; docs/ and tests/ are exempt.
_DEAD_KNOBS: tuple[str, ...] = ("user_max_cost_per_task",)
_SOURCE_DIRS: tuple[str, ...] = (
    "orchestration",
    "components",
    "services",
    "trust",
    "agent_ui_adapter",
    "middleware",
    "utils",
)
_SOURCE_FILES: tuple[str, ...] = ("cli.py",)


def _runtime_py_files() -> list[Path]:
    files: list[Path] = []
    for dirname in _SOURCE_DIRS:
        files.extend((_REPO_ROOT / dirname).rglob("*.py"))
    files.extend(_REPO_ROOT / name for name in _SOURCE_FILES)
    return [f for f in files if f.is_file()]


class TestNoDeadConfigKnobs:
    def test_deleted_knobs_do_not_reappear_in_runtime_source(self):
        offenders: list[str] = []
        for path in _runtime_py_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for knob in _DEAD_KNOBS:
                if knob in text:
                    offenders.append(f"{path.relative_to(_REPO_ROOT)}: {knob}")
        assert not offenders, (
            "Dead config knob resurfaced in runtime source without a writer. "
            "Either remove the read, or wire the writer end-to-end and drop the "
            "knob from _DEAD_KNOBS (see module docstring): "
            + "; ".join(sorted(offenders))
        )
