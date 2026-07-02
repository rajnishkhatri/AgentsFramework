"""subject-coach-english AgentFacts instance (FR-1/FR-2, ADR-0007/ADR-0012).

The Subject Coach is an identity-bound *instance* of the existing pipeline: a
new ``AgentFacts`` record with a least-privilege contract, NOT a new ``trust/``
type (no kernel re-sign — spec §4 "New *instance*, not new field").

Declared = enforced: every policy names its enforcement plane in ``rules``
(runtime capability gate / input guardrail / offline judge / trace audit), so
the contract is mechanically auditable (§13.2) rather than prose-only —
the ADR-0011/0012 lesson.

Design refs:
- docs/plan/subject-coach-agent.spec.md §3.1 (FR-1/FR-2)
- docs/adr/0007-subject-coach-agent-tool-capability-gating.md (capability gate)
- docs/adr/0008-subject-coach-judges-grader-and-pedagogy.md (leakage judge)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from services.base_config import AgentConfig

from trust.enums import IdentityStatus
from trust.models import AgentFacts, Capability, Policy

SUBJECT_COACH_AGENT_ID: Final[str] = "subject-coach-english"

# FR-3/FR-4: the ONLY tools the coach LLM may ever see. ``derive_bound_tools``
# (components/capability_gating.py) fails fast if either is missing from the
# ToolRegistry (FR-5); the declared=bound arch test asserts the equality (FR-6).
SUBJECT_COACH_CAPABILITIES: Final[list[str]] = ["think", "file_io"]

# FR-7..9: the injectable InputGuardrail accept_condition. Deliberately BROAD
# (FR-9 — the named failure mode is over-refusal): the full breadth of English
# learning is admitted, including one-word coaching replies and adversarial
# "just tell me the answer" (on-topic; the PERSONA refuses the reveal, the
# rail must not). Gate: ≥98% admit on the frozen held-out set
# (tests/fixtures/subject_coach/guardrail_heldout_v1.py — L3, live).
SUBJECT_COACH_ACCEPT_CONDITION: Final[str] = (
    "The input is part of a legitimate English-language-learning exchange — "
    "any question, answer, reply, or request concerning English grammar, "
    "usage, mechanics, punctuation, sentence structure, rhetoric, style, "
    "reading comprehension, vocabulary, or test-taking strategy. This "
    "includes quiz items and hint requests, short or one-word replies within "
    "an ongoing coaching conversation (e.g. 'yes', 'B', 'idk'), requests to "
    "reveal or confirm an answer (admitted here; the coach itself decides "
    "how to respond), and non-English phrasing when the underlying intent "
    "is learning English."
)

SUBJECT_COACH_POLICIES: Final[tuple[str, ...]] = (
    "domain-english-teaching",
    "no-code-execution",
    "answer-leakage-prohibited",
    "coach-rate-limit",
)


def subject_coach_english_facts() -> AgentFacts:
    """Build the coach's identity card with its ratified contract.

    Unsigned — ``AgentFactsRegistry.register`` computes the HMAC signature at
    registration (FR-1), and ``guard_input`` verifies it per run (FR-2).
    """
    return AgentFacts(
        agent_id=SUBJECT_COACH_AGENT_ID,
        agent_name="Subject Coach (English)",
        owner="preact-coach",
        version="1.0.0",
        description=(
            "Governed Socratic English-coaching agent: scaffolds without "
            "revealing answers (ADR-0012 mode-dependent context contract)."
        ),
        capabilities=[
            Capability(
                name="think",
                description="Structured reasoning scratchpad; no side effects.",
            ),
            Capability(
                name="file_io",
                description="Sandboxed file read/write for coaching artifacts.",
            ),
        ],
        policies=[
            Policy(
                name="domain-english-teaching",
                description=(
                    "Admit only English-learning input (full breadth: grammar, "
                    "usage, mechanics, rhetoric, reading, vocabulary, strategy)."
                ),
                rules={"enforced_by": "input_guardrail_accept_condition"},
            ),
            Policy(
                name="no-code-execution",
                description=(
                    "shell/python/web_search are never bound to the coach LLM."
                ),
                rules={"enforced_by": "capability_gating.derive_bound_tools"},
            ),
            Policy(
                name="answer-leakage-prohibited",
                description=(
                    "Pre-submit context excludes answer-bearing fields; hints "
                    "come only from reviewed ladder rungs; leakage is judged "
                    "post-hoc as a first-class flag."
                ),
                rules={"enforced_by": ("bff_sanitizer+pedagogy_judge.answer_leakage")},
            ),
            Policy(
                name="coach-rate-limit",
                description="Per-learner run budget on the coach surface.",
                rules={"enforced_by": "bff_route_rate_limit"},
            ),
        ],
        status=IdentityStatus.ACTIVE,
    )


def subject_coach_agent_config(**overrides) -> "AgentConfig":
    """AgentConfig for the identity-bound coach instance (FR-3, ADR-0007).

    Capability gating is ON here — the least-privilege contract IS the
    identity, not a rollout flag (shadow-first applies to judge/gate flags,
    which stay OFF elsewhere). Callers pass ``bound_capabilities=
    SUBJECT_COACH_CAPABILITIES`` to ``build_graph`` alongside this config.

    ``overrides`` lets the composition root supply models, the English
    guardrail condition, and the persona without re-stating identity fields.
    """
    from services.base_config import AgentConfig

    params: dict = {
        "agent_name": SUBJECT_COACH_AGENT_ID,
        "agent_version": "1.0.0",
        "capability_gating_enabled": True,
        "input_guardrail_accept_condition": SUBJECT_COACH_ACCEPT_CONDITION,
        "eval_capture_target": "subject_coach",
    }
    params.update(overrides)
    return AgentConfig(**params)


# Contract-bearing AgentFacts fields for the drift check: everything except
# the registration-time signature and the per-instantiation timestamps.
_CONTRACT_EXCLUDE: Final = {"signature_hash", "created_at", "updated_at"}


def register_subject_coach(
    registry, registered_by: str = "composition-root"
) -> AgentFacts:
    """Idempotently register the coach card (FR-1).

    Composition-root helper: registers on first call; on subsequent calls
    returns the stored card ONLY if it still declares the ratified contract.
    A stored card that drifted from the current definition (e.g. an older
    deploy's weaker policy set) raises instead of being silently served, and
    a registration failure propagates untouched — "already registered" is
    the one silent path (review finding I1). A tampered stored card is NOT
    healed here — it stays on disk and fails ``verify`` at guard_input
    (FR-2), which is the loud, auditable failure the contract wants.
    """
    expected = subject_coach_english_facts()
    try:
        stored = registry.get(SUBJECT_COACH_AGENT_ID)
    except KeyError:
        return registry.register(expected, registered_by=registered_by)

    stored_contract = stored.model_dump(mode="json", exclude=_CONTRACT_EXCLUDE)
    expected_contract = expected.model_dump(mode="json", exclude=_CONTRACT_EXCLUDE)
    if stored_contract != expected_contract:
        raise ValueError(
            f"Stored AgentFacts for '{SUBJECT_COACH_AGENT_ID}' drift from the "
            "ratified contract (stale card from an older deploy?). Refusing to "
            "serve it as current — migrate or re-register the card explicitly."
        )
    return stored
