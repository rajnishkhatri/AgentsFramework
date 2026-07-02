"""Sprint 4 hardening checks for deep-agent migration cleanup."""

from __future__ import annotations

from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_deep_agents_from_scratch_package_removed() -> None:
    scratch_dir = AGENT_ROOT / "deep_agents_from_scratch"
    if not scratch_dir.exists():
        return
    remaining_python = sorted(
        str(p.relative_to(AGENT_ROOT)) for p in scratch_dir.rglob("*.py")
    )
    assert remaining_python == [], (
        "Sprint 4 cleanup incomplete: deep_agents_from_scratch/ still contains Python modules:\n"
        + "\n".join(remaining_python)
    )


def test_no_runtime_python_references_to_removed_package() -> None:
    violations: list[str] = []
    for py_file in AGENT_ROOT.rglob("*.py"):
        rel = py_file.relative_to(AGENT_ROOT)
        # .claude holds agent-worktree repo snapshots — out of scan scope.
        if rel.parts[0] in {".venv", "venv", ".claude"}:
            continue
        if rel == Path("tests/architecture/test_deep_agent_cleanup.py"):
            continue
        content = py_file.read_text()
        if "deep_agents_from_scratch" in content:
            violations.append(str(rel))
    assert violations == [], (
        "Removed package still referenced in Python runtime/tests:\n"
        + "\n".join(sorted(violations))
    )
