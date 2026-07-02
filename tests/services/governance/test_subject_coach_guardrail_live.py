"""L3 Live gate: English guardrail admit-rate over the frozen held-out set.

Agent spec §7: the coach condition SHALL admit legitimate coaching utterances
at ≥ 98% (over-refusal is the named failure mode). Aggregate success rate —
never per-utterance exact-match (pyramid L3). Off-topic rejection rate is
REPORTED (FR-8 signal) but the binding floor is the admit rate only; do not
invent gates the spec didn't state.

``@pytest.mark.live_llm`` — excluded from CI by addopts; run on demand:

    .venv/bin/python -m pytest tests/services/governance/\
test_subject_coach_guardrail_live.py -m live_llm -q

§9 discipline: this test READS the frozen v1 set. If it fails, revise the
condition text and re-run — never edit the held-out rows (the freeze test
catches that).
"""

from __future__ import annotations

import pytest

from services.base_config import ModelProfile, default_fast_profile
from services.governance.subject_coach_identity import (
    SUBJECT_COACH_ACCEPT_CONDITION,
)
from services.guardrails import InputGuardrail
from services.llm_config import LLMService
from services.prompt_service import PromptService
from tests.fixtures.subject_coach.guardrail_heldout_v1 import HELDOUT_V1

ADMIT_RATE_FLOOR = 0.98


def _coach_guardrail() -> InputGuardrail:
    from services.governance.subject_coach_identity import (
        subject_coach_agent_config,
    )

    profile: ModelProfile = default_fast_profile()
    cfg = subject_coach_agent_config(default_model=profile.name, models=[profile])
    return InputGuardrail(
        name="subject_coach_english",
        accept_condition=SUBJECT_COACH_ACCEPT_CONDITION,
        llm_service=LLMService(config=cfg),
        prompt_service=PromptService(),
        judge_profile=profile,
        # Mirror the production posture (react_loop: domain_gated=True whenever
        # the config carries a domain condition). Without this, clean_short
        # precheck ACCEPTs bypass the condition entirely and the "live" gate
        # measures the precheck, not the judge — the vacuous 1.000 admit-rate
        # observed on 2026-07-02 (38/40 off-topic admitted at precheck).
        domain_gated=True,
    )


@pytest.mark.live_llm
@pytest.mark.asyncio
async def test_admit_rate_floor_on_legit_heldout():
    guard = _coach_guardrail()
    legit = [r for r in HELDOUT_V1 if r["label"] == "legit"]
    offtopic = [r for r in HELDOUT_V1 if r["label"] == "offtopic"]

    admitted, refusals = 0, []
    for row in legit:
        accepted, stage = await guard.decide(row["text"])
        if accepted:
            admitted += 1
        else:
            refusals.append((row["category"], row["text"], stage))

    rejected_offtopic = 0
    admitted_offtopic = []
    for row in offtopic:
        accepted, stage = await guard.decide(row["text"])
        if not accepted:
            rejected_offtopic += 1
        else:
            admitted_offtopic.append((row["category"], row["text"], stage))

    admit_rate = admitted / len(legit)
    # Reported signal (FR-8), not a gate:
    print(
        f"\nlegit admit-rate: {admit_rate:.3f} ({admitted}/{len(legit)}); "
        f"offtopic reject-rate: {rejected_offtopic / len(offtopic):.3f}"
    )
    if refusals:
        print("over-refusals:", refusals)
    if admitted_offtopic:
        print("admitted offtopic:", admitted_offtopic)

    assert admit_rate >= ADMIT_RATE_FLOOR, (
        f"admit-rate {admit_rate:.3f} < {ADMIT_RATE_FLOOR} — over-refusal; "
        f"refused: {refusals}"
    )
