"""Coach answer-leakage gate — the pure enforcement decision (Phase 5, T1/T2).

Framework-agnostic (Invariant #3): no ``langgraph`` / ``orchestration`` /
``AgentState`` import. This is the *policy* half of the gate — the same split as
:mod:`components.reflexion` (``decide_reentry``) and
``services.governance.carrier_gate`` (``decide_enforcement``): a deterministic,
CI-pure predicate decides *what* to do; the orchestration node owns the LLM call
and the act (AP-4). The certified leakage judge (ADR-0019) supplies the verdict;
this module never calls it.

Modes (config-driven, reversible per-deploy — ADR-0020):
  - ``off``     — inert; never judge, never alter a reply (FR-5).
  - ``shadow``  — judge + record, but let every reply through (FR-6).
  - ``enforce`` — a flagged reply is regenerated once, then suppressed if it
    still leaks (FR-7/FR-3); a judge outage fails OPEN (FR-1).

The fail-dark / fail-open split is deliberate: config uncertainty must never
enforce (the *reader* resolves an unknown posture to ``off``), but a transient
judge outage while armed must not black out coaching — it lets the reply through
loudly (``fail_open``).
"""

from __future__ import annotations

from typing import Any, Literal, Protocol

LeakageGateMode = Literal["off", "shadow", "enforce"]
LeakageGateVerdict = Literal["clean", "leak", "unavailable"]
LeakageGateAction = Literal[
    "allow", "shadow_record", "regenerate", "suppress", "fail_open"
]


def decide_leakage_enforcement(
    mode: LeakageGateMode,
    verdict: LeakageGateVerdict,
    *,
    retry_verdict: LeakageGateVerdict | None = None,
) -> LeakageGateAction:
    """Pure mapping ``(mode, verdict, retry_verdict) → action``. No I/O, no raise.

    ``retry_verdict`` is the judge's verdict on the *regenerated* reply, or
    ``None`` if regeneration has not been attempted yet. The caller acts on the
    returned action (AP-4): ``regenerate`` triggers one retry then re-calls this
    with the retry verdict; ``suppress`` substitutes the safe fallback;
    ``fail_open`` lets the original reply through with a loud carrier.
    """
    if mode == "off":
        return "allow"

    if mode == "shadow":
        # Observe-only: record the verdict, never act on it (FR-6).
        return "shadow_record"

    # mode == "enforce"
    if verdict == "unavailable":
        # FR-1: a judge outage while armed fails OPEN, not closed — availability
        # over a rare leak during the outage (loud carrier at the act site).
        return "fail_open"
    if verdict == "clean":
        return "allow"

    # verdict == "leak"
    if retry_verdict is None:
        # FR-7: first flag → regenerate once with a stronger no-leak directive.
        return "regenerate"
    if retry_verdict == "leak":
        # FR-3: the regeneration still leaks → suppress; never emit flagged text.
        return "suppress"
    # retry cleared the leak (clean) or the retry judge was unavailable → allow
    # the regenerated reply through. (An unavailable retry judge does not re-flag
    # a reply the first judge already flagged; the regeneration is the mitigation.)
    return "allow"


def arm(mode: LeakageGateMode, *, goldset_certified: bool) -> LeakageGateMode:
    """FR-10: refuse to arm ``shadow``/``enforce`` unless the judge is certified.

    The ADR-0008 cond#1 floor — never enforce below the cert. A config that sets a
    live mode while the goldset manifest is not ``ENABLE``-certified resolves to
    ``off`` (a config typo can never enforce on an uncertified judge). ``off`` is
    always ``off``.
    """
    if not goldset_certified:
        return "off"
    return mode


class LeakageJudge(Protocol):
    """Structural type for the certified answer-leakage judge (``PedagogyJudge``).

    Kept structural (not an import of ``subject_coach_judges``) so the pure policy
    above stays importable without pulling the judge, and so CI can inject a stub
    (FR-11 — no live LLM in CI). The orchestration node passes the real judge.
    """

    async def evaluate(
        self,
        *,
        learner_utterance: str,
        coach_reply: str,
        mode: str,
        question: str = "",
    ) -> Any | None: ...


async def judge_leakage(
    judge: LeakageJudge,
    *,
    learner_utterance: str,
    coach_reply: str,
    mode: str,
    question: str = "",
) -> LeakageGateVerdict:
    """Map the certified judge's verdict → a :data:`LeakageGateVerdict` (FR-1).

    Fail-safe: a judge that raises OR returns ``None`` (its fail-CLOSED signal on a
    parse/transport error) OR returns a verdict whose ``answer_leakage`` is itself
    ``None`` (un-decided) maps to ``"unavailable"`` — never a fabricated ``clean``
    (AP-6). ``unavailable`` becomes ``fail_open`` at the enforce decision, so a
    judge outage lets the reply through loudly rather than blacking out coaching.
    """
    try:
        verdict = await judge.evaluate(
            learner_utterance=learner_utterance,
            coach_reply=coach_reply,
            mode=mode,
            question=question,
        )
    except Exception:
        return "unavailable"
    if verdict is None:
        return "unavailable"
    answer_leakage = getattr(verdict, "answer_leakage", None)
    if answer_leakage is None:
        return "unavailable"
    return "leak" if answer_leakage else "clean"


# ── Live wiring (ADR-0020): the judge stays WRAPPED here, not imported into ─────
# orchestration. The node calls these factories; the arch gate permits the judge
# import only in this components adapter + the sanctioned scripts/sampler.

# The regeneration directive is coach-facing model instruction text, so it is a
# rendered ``.j2`` template (AP-3 — no hardcoded prompt prose), not a constant.
_COACH_NO_LEAK_PROMPT = "coach_regenerate_no_leak"

# A safe Socratic fallback substituted when a regenerated reply still leaks (FR-3).
# This is fixed UI copy shown verbatim to the learner (not model input), so a
# constant is correct here — it is not a prompt template.
COACH_LEAKAGE_FALLBACK = (
    "Let's slow down — what part of this are you least sure about? "
    "Walk me through your reasoning and we'll find the next step together."
)


def build_leakage_judge(profile: Any) -> LeakageJudge:  # pragma: no cover - live only
    """Construct the certified answer-leakage judge (``PedagogyJudge``) for the
    given profile. Lazily imports ``subject_coach_judges`` so the pure policy above
    stays import-light and CI (which injects a stub) never pulls a live judge."""
    from components.subject_coach_judges import PedagogyJudge
    from services.base_config import AgentConfig
    from services.llm_config import LLMService
    from services.prompt_service import PromptService

    agent_config = AgentConfig(default_model=profile.name, models=[profile])
    llm_service = LLMService(agent_config)
    prompt_service = PromptService()
    return PedagogyJudge(llm_service, prompt_service, profile, name="PedagogyJudge")


def make_regenerate(
    llm_service: Any,
    profile: Any,
    *,
    learner_utterance: str,
    prompt_service: Any = None,
):
    """Return an async ``regenerate(coach_reply=...) -> str`` bound to ``llm_service``
    (FR-7). One plain LLM call with the no-leak directive rendered from
    ``coach_regenerate_no_leak.j2`` (AP-3 — no hardcoded prompt prose); the node
    injects this so the gate helper stays testable with a stub. The directive is
    rendered once at factory-build time (it is static)."""
    from services.prompt_service import PromptService

    prompt_service = prompt_service or PromptService()
    directive = prompt_service.render_prompt(_COACH_NO_LEAK_PROMPT)

    async def _regenerate(*, coach_reply: str) -> str:
        messages = [
            {"role": "system", "content": directive},
            {"role": "user", "content": f"Learner: {learner_utterance}"},
        ]
        resp = await llm_service.invoke(profile, messages)
        return getattr(resp, "content", "") or ""

    return _regenerate
