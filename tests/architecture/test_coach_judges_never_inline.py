"""Architecture gate: coach judges are OFF-GRAPH except the ONE declared
leakage-gate binding (ADR-0009, narrowed by ADR-0020 — design §7.3, Phase 5).

The declared=bound discipline (ADR-0007) extended to judge injection: the coach
judges are DECLARED as a post-hoc ``meta/`` sampler concern, so Reflexion-style
inline judgment stays off the request path (ADR-0009). **ADR-0020 supersedes
ADR-0009 with conditions**: the certified answer-leakage judge (ADR-0019, TNR 1.0)
gets exactly ONE inline binding — the coach-leakage GATE at the ``evaluate_node``
OUTPUT_VALIDATION seam, reading the config via ``subject_coach_judge_runtime_config``
and acting via the pure ``components.coach_leakage_gate`` policy.

The carve-out is an EXPLICIT ALLOWLIST, not a blanket permission:
- the coach-judge **sampler** stays forbidden on the live path ALWAYS (that is the
  Reflexion/post-hoc path ADR-0009 truly protects);
- ``subject_coach_judges`` / ``subject_coach_judge_runtime_config`` are permitted
  ONLY in the exact files the leakage gate declares — any OTHER live-graph file
  importing them (a *second*, undeclared inline judge binding) still fails.

``G8-OK: ADR-0020 supersedes ADR-0009`` — this narrows a previously-blanket ban;
each relaxed assertion is justified by the FR-13 carve-out below.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent.parent
_LIVE_GRAPH_DIRS = ("orchestration", "middleware")

# The sampler is the Reflexion/post-hoc concern — forbidden on the live path
# unconditionally (ADR-0009's core protection survives ADR-0020 untouched).
_ALWAYS_FORBIDDEN_TOKENS = ("subject_coach_judge_sampler",)

# The judge + its config reader are permitted ONLY at the declared leakage-gate
# binding (ADR-0020 / FR-13). The map is file -> the tokens that file may import.
# Anything not in this allowlist that references the tokens is an UNDECLARED
# inline binding and must fail.
_LEAKAGE_GATE_ALLOWLIST: dict[str, frozenset[str]] = {
    # the enforcement seam reads the mode (config reader) and acts via the pure
    # gate policy; it does NOT import subject_coach_judges directly — the judge
    # call is wrapped by components/coach_leakage_gate.py.
    "orchestration/react_loop.py": frozenset({"subject_coach_judge_runtime_config"}),
}

# Tokens that are OFF-GRAPH except where the allowlist above permits them.
_GATED_TOKENS = ("subject_coach_judges", "subject_coach_judge_runtime_config")


def _python_files(directory: str) -> list[Path]:
    return sorted((_REPO / directory).rglob("*.py"))


@pytest.mark.parametrize("directory", _LIVE_GRAPH_DIRS)
def test_sampler_never_reachable_from_live_graph(directory: str) -> None:
    """ADR-0009 core (survives ADR-0020): the post-hoc/Reflexion sampler path is
    never inline. This assertion is UNCHANGED — the gate did not relax it."""
    offenders: list[str] = []
    for path in _python_files(directory):
        source = path.read_text(encoding="utf-8")
        for token in _ALWAYS_FORBIDDEN_TOKENS:
            if token in source:
                offenders.append(f"{path.relative_to(_REPO)}: {token}")
    assert not offenders, (
        "ADR-0009 breach — the coach-judge sampler is reachable from the live "
        "graph (it is post-hoc, meta/-only):\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("directory", _LIVE_GRAPH_DIRS)
def test_only_the_declared_leakage_gate_binds_the_judge_inline(directory: str) -> None:
    """ADR-0020/FR-13: the judge + config reader are permitted ONLY at the
    declared leakage-gate binding; any other live-graph file referencing them is
    an undeclared inline binding and must fail (the carve-out is one named seam,
    not a blanket allowance)."""
    offenders: list[str] = []
    for path in _python_files(directory):
        rel = str(path.relative_to(_REPO))
        allowed = _LEAKAGE_GATE_ALLOWLIST.get(rel, frozenset())
        source = path.read_text(encoding="utf-8")
        for token in _GATED_TOKENS:
            if token in source and token not in allowed:
                offenders.append(
                    f"{rel}: {token} (not a declared leakage-gate binding)"
                )
    assert not offenders, (
        "ADR-0020 carve-out breach — an UNDECLARED inline coach-judge binding on "
        "the live graph (only the leakage gate's declared seam may bind it):\n  "
        + "\n  ".join(offenders)
    )


def test_the_carveout_is_a_named_allowlist_not_blanket() -> None:
    """The permission is an explicit file->token map, not an unconditional token
    allowance — so a *second* inline judge binding is still caught. Guards against
    a future widening of the carve-out into a blanket permit (ADR-0020 intent)."""
    # The allowlist names specific files, and does NOT grant subject_coach_judges
    # anywhere on the live graph by default (the judge is wrapped in components/).
    all_allowed_tokens = set().union(*_LEAKAGE_GATE_ALLOWLIST.values())
    assert "subject_coach_judges" not in all_allowed_tokens, (
        "subject_coach_judges must stay wrapped in components/coach_leakage_gate.py; "
        "the live graph binds the GATE, not the judge directly."
    )
    # Exactly one declared binding today (the enforcement seam); if this grows,
    # the growth is a deliberate ADR-tracked decision, not an accident.
    assert set(_LEAKAGE_GATE_ALLOWLIST) == {"orchestration/react_loop.py"}


def test_the_sampler_is_the_only_judge_consumer_outside_the_gate() -> None:
    """The judge seam is bound where declared: components (definition + the gate
    adapter), meta (the sampler job). Anything else in these dirs is undeclared."""
    allowed = {
        Path("components/subject_coach_judges.py"),
        Path("components/coach_leakage_gate.py"),  # ADR-0020: the gate adapter
        Path("meta/subject_coach_judge_sampler.py"),
    }
    offenders: list[str] = []
    for directory in ("components", "services", "meta", "trust", "utils"):
        for path in _python_files(directory):
            rel = path.relative_to(_REPO)
            if rel in allowed:
                continue
            if "subject_coach_judges" in path.read_text(encoding="utf-8"):
                offenders.append(str(rel))
    assert not offenders, "undeclared coach-judge binding:\n  " + "\n  ".join(offenders)
