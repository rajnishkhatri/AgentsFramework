"""Architecture gate: the coach judges are OFF-GRAPH (ADR-0009, design §7.3).

The declared=bound discipline (ADR-0007) extended to judge injection: the
coach judges are DECLARED as a post-hoc ``meta/`` sampler concern, so they may
be BOUND only there. Nothing judge-related runs inline on a coach turn — the
turn's evaluation loop is the learner's reply; judgment is offline. An import
of ``subject_coach_judges`` (or its config reader) from the live-graph layers
(orchestration, middleware) would put an LLM-as-judge call on the request
path, exactly what ADR-0009 forbids.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent.parent
_LIVE_GRAPH_DIRS = ("orchestration", "middleware")
_FORBIDDEN_TOKENS = (
    "subject_coach_judges",
    "subject_coach_judge_runtime_config",
    "subject_coach_judge_sampler",
)


def _python_files(directory: str) -> list[Path]:
    return sorted((_REPO / directory).rglob("*.py"))


@pytest.mark.parametrize("directory", _LIVE_GRAPH_DIRS)
def test_live_graph_layers_never_import_the_coach_judges(directory: str) -> None:
    offenders: list[str] = []
    for path in _python_files(directory):
        source = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN_TOKENS:
            if token in source:
                offenders.append(f"{path.relative_to(_REPO)}: {token}")
    assert not offenders, (
        "ADR-0009 breach — judge machinery reachable from the live graph "
        "(judges are post-hoc, meta/-only):\n  " + "\n  ".join(offenders)
    )


def test_the_sampler_is_the_only_judge_consumer_outside_tests() -> None:
    """The judge seam is bound where declared: components (definition),
    meta (the sampler job). Anything else is an undeclared binding."""
    allowed = {
        Path("components/subject_coach_judges.py"),
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
