#!/usr/bin/env python
"""Build the synthetic multi-turn / multi-session memory-stress corpus.

The corpus validates the now-wired memory layer END TO END across **multiple
sessions for one persistent user**: a fact stored in session N must be recalled
in session N+1, the knowledge-update seam must return the corrected value, the
agent must abstain when nothing was stored, and a fact under one user's id must
NEVER leak into another user's recall. See
``docs/plans/memory_multisession_e2e_stress.plan.md``.

Each *case* is a conversation = an ordered list of **sessions**; each session is
one ``/run/stream`` invocation (one thread) driven through the live UI by the
T3 spec. The memory layer keys on ``user_id`` (``identity.owner``), so each case
carries a PER-CASE-UNIQUE ``user_id`` — that uniqueness is what makes the
cross-user-leak guard observable (one shared user => no leak is possible).

Provenance / licensing (plan §3.1):
- ``longmemeval-derived``  — shape derived from LongMemEval (MIT). The prompts
  here are independently authored paraphrases of the upstream ability classes
  (single-session-user/preference, multi-session, temporal-reasoning,
  knowledge-update, abstention) so the committed fixture is self-contained and
  redistributable; ``scripts/fetch_longmemeval.py`` pulls the upstream JSON into
  the gitignored cache for anyone who wants to grow this from the real haystacks.
- ``synthetic-locomo-shape`` — persona-drift cases borrow LoCoMo's persona +
  evolving-preference SHAPE only (CC BY-NC). Independently authored; NO LoCoMo
  text is copied (the test suite asserts the known speaker names never appear).
- ``synthetic`` — leak-control cases (no external analogue).

Regenerate after editing the rows below:
    python scripts/build_memory_multisession_corpus.py

Output: frontend/e2e/fixtures/memory_multisession_corpus.json
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
AGENT_ROOT = SCRIPTS_DIR.parent
FIXTURES_DIR = AGENT_ROOT / "frontend" / "e2e" / "fixtures"
OUT_PATH = FIXTURES_DIR / "memory_multisession_corpus.json"

# Deterministic trace_id namespace (same idiom as build_planning_stress_corpus).
_NS = uuid.NAMESPACE_DNS


def _trace_id(seed: str) -> str:
    return uuid.uuid5(_NS, seed).hex


def _session(
    idx: int,
    kind: str,
    turns: list[str],
    *,
    date: str | None = None,
    want_recall: bool | None = None,
    expect_substring: list[str] | None = None,
    evidence_session_idx: int | None = None,
) -> dict:
    s: dict = {"session_idx": idx, "kind": kind, "turns": turns}
    if date is not None:
        s["date"] = date
    if want_recall is not None:
        s["want_recall"] = want_recall
    if expect_substring is not None:
        s["expect_substring"] = expect_substring
    if evidence_session_idx is not None:
        s["evidence_session_idx"] = evidence_session_idx
    return s


def _case(
    *,
    case: str,
    mem_id: str,
    ability: str,
    provenance: str,
    user_id: str,
    sessions: list[dict],
    rationale: str,
    lme_question_type: str | None = None,
) -> dict:
    # Pin a deterministic per-session trace_id so the analyzer can pre-compute
    # the join key (the T3 spec also mints fresh per-RUN trace_ids to avoid
    # superposition; the corpus value is the stable fallback / report key).
    for s in sessions:
        s.setdefault("trace_id", _trace_id(f"{case}:s{s['session_idx']}"))
    row: dict = {
        "case": case,
        "mem_id": mem_id,
        "ability": ability,
        "provenance": provenance,
        "user_id": user_id,
        "sessions": sessions,
        "rationale": rationale,
    }
    if lme_question_type is not None:
        row["lme_question_type"] = lme_question_type
    return row


# ─────────────────────────────────────────────────────────────────────────────
# CONTROLS FIRST (failure-paths-first) — the precision guards this corpus is for.
# ─────────────────────────────────────────────────────────────────────────────

def _leak_control_cases() -> list[dict]:
    """A case under user_B probes a fact ONLY ever seeded under another user.
    There is no seed session in this case — recall MUST return 0 / abstain. The
    paired seeding lives in the recall cases (distinct user_ids); the analyzer
    cross-checks that no user_B probe recalls a user_A fact."""
    return [
        _case(
            case="MEM-LEAK-units-cross-user-01",
            mem_id="MEM-0901",
            ability="leak-control",
            provenance="synthetic",
            user_id="userleak01",
            sessions=[
                _session(
                    0,
                    "probe",
                    ["What measurement units do I prefer? Only answer if you actually remember me telling you."],
                    want_recall=False,
                ),
            ],
            rationale="probes the 'metric units' fact seeded under userpref01 (recall-01); a different user must recall nothing",
        ),
        _case(
            case="MEM-LEAK-allergy-cross-user-02",
            mem_id="MEM-0902",
            ability="leak-control",
            provenance="synthetic",
            user_id="userleak02",
            sessions=[
                _session(
                    0,
                    "probe",
                    ["Do you remember any food allergies I have?"],
                    want_recall=False,
                ),
            ],
            rationale="probes the peanut-allergy fact seeded under userhealth01; cross-user recall must be empty",
        ),
        _case(
            case="MEM-LEAK-jobrole-cross-user-03",
            mem_id="MEM-0903",
            ability="leak-control",
            provenance="synthetic",
            user_id="userleak03",
            sessions=[
                _session(
                    0,
                    "probe",
                    ["What is my job title, if I have ever mentioned it?"],
                    want_recall=False,
                ),
            ],
            rationale="probes a role fact seeded under another user; leak guard hard-0",
        ),
        _case(
            case="MEM-LEAK-city-cross-user-04",
            mem_id="MEM-0904",
            ability="leak-control",
            provenance="synthetic",
            user_id="userleak04",
            sessions=[
                _session(
                    0,
                    "probe",
                    ["Which city did I say I live in?"],
                    want_recall=False,
                ),
            ],
            rationale="city fact belongs to another user; recall must abstain",
        ),
    ]


def _abstention_cases() -> list[dict]:
    """Probe a fact NEVER seeded for this user — the agent must abstain, recall
    count 0, no fabricated 'I remember…'. The corrupt-success guard for recall."""
    return [
        _case(
            case="MEM-ABSTAIN-pet-name-01",
            mem_id="MEM-0801",
            ability="abstention",
            provenance="longmemeval-derived",
            lme_question_type="single-session-user_abs",
            user_id="userabs01",
            sessions=[
                _session(0, "filler", ["Can you explain what a hash map is?"]),
                _session(
                    1,
                    "probe",
                    ["What's the name of my pet? Only say so if I've told you."],
                    want_recall=False,
                ),
            ],
            rationale="never seeded a pet -> must abstain, not fabricate",
        ),
        _case(
            case="MEM-ABSTAIN-birthday-02",
            mem_id="MEM-0802",
            ability="abstention",
            provenance="longmemeval-derived",
            lme_question_type="temporal-reasoning_abs",
            user_id="userabs02",
            sessions=[
                _session(0, "filler", ["Summarize the plot of a generic detective novel."]),
                _session(1, "probe", ["When is my birthday?"], want_recall=False),
            ],
            rationale="no birthday ever stated -> abstain",
        ),
        _case(
            case="MEM-ABSTAIN-favorite-color-03",
            mem_id="MEM-0803",
            ability="abstention",
            provenance="longmemeval-derived",
            lme_question_type="single-session-preference_abs",
            user_id="userabs03",
            sessions=[
                _session(0, "probe", ["What's my favorite color?"], want_recall=False),
            ],
            rationale="cold probe, nothing seeded -> abstain",
        ),
        _case(
            case="MEM-ABSTAIN-project-deadline-04",
            mem_id="MEM-0804",
            ability="abstention",
            provenance="longmemeval-derived",
            lme_question_type="single-session-assistant_abs",
            user_id="userabs04",
            sessions=[
                _session(0, "filler", ["What's the difference between TCP and UDP?"]),
                _session(1, "probe", ["What deadline did I tell you about earlier?"], want_recall=False),
            ],
            rationale="no deadline mentioned -> abstain",
        ),
        _case(
            case="MEM-ABSTAIN-sibling-05",
            mem_id="MEM-0805",
            ability="abstention",
            provenance="longmemeval-derived",
            lme_question_type="multi-session_abs",
            user_id="userabs05",
            sessions=[
                _session(0, "filler", ["Give me a recipe for pancakes."]),
                _session(1, "filler", ["How do I reverse a linked list?"]),
                _session(2, "probe", ["How many siblings did I say I have?"], want_recall=False),
            ],
            rationale="never seeded family info -> abstain",
        ),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# PHASE A — cross-session recall (gates B/C)
# ─────────────────────────────────────────────────────────────────────────────

def _recall_cases() -> list[dict]:
    return [
        _case(
            case="MEM-RECALL-units-01",
            mem_id="MEM-0001",
            ability="recall",
            provenance="longmemeval-derived",
            lme_question_type="single-session-preference",
            user_id="userpref01",  # the fact MEM-LEAK-...-01 probes cross-user
            sessions=[
                _session(0, "seed", ["Remember that I prefer metric units for everything."], date="2026-05-01"),
                _session(
                    1,
                    "probe",
                    ["When you summarize my running data, which units should you use?"],
                    date="2026-05-08",
                    want_recall=True,
                    expect_substring=["metric"],
                    evidence_session_idx=0,
                ),
            ],
            rationale="single-session-preference seeded then recalled one session later -> recall floor",
        ),
        _case(
            case="MEM-RECALL-allergy-02",
            mem_id="MEM-0002",
            ability="recall",
            provenance="longmemeval-derived",
            lme_question_type="single-session-user",
            user_id="userhealth01",
            sessions=[
                _session(0, "seed", ["I have a severe peanut allergy."], date="2026-04-10"),
                _session(1, "filler", ["What's a good source of plant protein?"], date="2026-04-12"),
                _session(
                    2,
                    "probe",
                    ["Suggest a snack for me — keep my dietary restrictions in mind."],
                    date="2026-04-20",
                    want_recall=True,
                    expect_substring=["peanut", "allerg"],
                    evidence_session_idx=0,
                ),
            ],
            rationale="health fact seeded, filler session between, recalled across 2 sessions",
        ),
        _case(
            case="MEM-RECALL-jobrole-03",
            mem_id="MEM-0003",
            ability="recall",
            provenance="longmemeval-derived",
            lme_question_type="single-session-user",
            user_id="userwork01",
            sessions=[
                _session(0, "seed", ["I work as a backend engineer on a payments team."], date="2026-03-01"),
                _session(
                    1,
                    "probe",
                    ["Given my role, what kind of code examples are most useful to me?"],
                    date="2026-03-15",
                    want_recall=True,
                    expect_substring=["backend", "payment"],
                    evidence_session_idx=0,
                ),
            ],
            rationale="role fact recall",
        ),
        _case(
            case="MEM-RECALL-city-04",
            mem_id="MEM-0004",
            ability="recall",
            provenance="longmemeval-derived",
            lme_question_type="single-session-user",
            user_id="usergeo01",
            sessions=[
                _session(0, "seed", ["I live in Portland."], date="2026-02-01"),
                _session(
                    1,
                    "probe",
                    ["What's the weather usually like where I live this time of year?"],
                    date="2026-02-10",
                    want_recall=True,
                    expect_substring=["Portland"],
                    evidence_session_idx=0,
                ),
            ],
            rationale="location fact recall",
        ),
        _case(
            case="MEM-RECALL-tooling-05",
            mem_id="MEM-0005",
            ability="recall",
            provenance="longmemeval-derived",
            lme_question_type="single-session-preference",
            user_id="usertool01",
            sessions=[
                _session(0, "seed", ["I always use pytest for Python tests, never unittest."], date="2026-01-05"),
                _session(
                    1,
                    "probe",
                    ["Write me a test for an add() function in my preferred framework."],
                    date="2026-01-20",
                    want_recall=True,
                    expect_substring=["pytest"],
                    evidence_session_idx=0,
                ),
            ],
            rationale="tooling preference recall",
        ),
        _case(
            case="MEM-RECALL-language-06",
            mem_id="MEM-0006",
            ability="recall",
            provenance="longmemeval-derived",
            lme_question_type="single-session-preference",
            user_id="userlang01",
            sessions=[
                _session(0, "seed", ["Please always reply to me in British English spelling."], date="2026-05-02"),
                _session(
                    1,
                    "probe",
                    ["Describe the colour of a clear sky and how I'd organise a list."],
                    date="2026-05-09",
                    want_recall=True,
                    expect_substring=["colour", "organise"],
                    evidence_session_idx=0,
                ),
            ],
            rationale="style preference recall (spelling)",
        ),
        _case(
            case="MEM-RECALL-goal-07",
            mem_id="MEM-0007",
            ability="recall",
            provenance="longmemeval-derived",
            lme_question_type="single-session-user",
            user_id="usergoal01",
            sessions=[
                _session(0, "seed", ["My goal this quarter is to learn Rust."], date="2026-04-01"),
                _session(
                    1,
                    "probe",
                    ["Recommend a weekend project aligned with my current learning goal."],
                    date="2026-04-22",
                    want_recall=True,
                    expect_substring=["Rust"],
                    evidence_session_idx=0,
                ),
            ],
            rationale="goal fact recall",
        ),
        _case(
            case="MEM-RECALL-constraint-08",
            mem_id="MEM-0008",
            ability="recall",
            provenance="longmemeval-derived",
            lme_question_type="single-session-user",
            user_id="usercon01",
            sessions=[
                _session(0, "seed", ["Keep all answers under 100 words; I'm always short on time."], date="2026-03-10"),
                _session(
                    1,
                    "probe",
                    ["Explain how DNS resolution works."],
                    date="2026-03-18",
                    want_recall=True,
                    expect_substring=["DNS"],
                    evidence_session_idx=0,
                ),
            ],
            rationale="brevity constraint recall (length preference applied)",
        ),
    ]


def _multi_session_cases() -> list[dict]:
    """A fact split across TWO seed sessions; the probe needs BOTH -> recall
    must return >=2 evidence items."""
    return [
        _case(
            case="MEM-MULTI-trip-01",
            mem_id="MEM-0101",
            ability="multi-session",
            provenance="longmemeval-derived",
            lme_question_type="multi-session",
            user_id="usermulti01",
            sessions=[
                _session(0, "seed", ["I'm planning a trip to Japan in the autumn."], date="2026-02-01"),
                _session(1, "seed", ["For that trip my budget is about 3000 dollars."], date="2026-02-08"),
                _session(
                    2,
                    "probe",
                    ["Help me outline my upcoming trip given what you know about it."],
                    date="2026-02-20",
                    want_recall=True,
                    expect_substring=["Japan", "3000"],
                    evidence_session_idx=0,
                ),
            ],
            rationale="destination (s0) + budget (s1) both needed in the probe",
        ),
        _case(
            case="MEM-MULTI-stack-02",
            mem_id="MEM-0102",
            ability="multi-session",
            provenance="longmemeval-derived",
            lme_question_type="multi-session",
            user_id="usermulti02",
            sessions=[
                _session(0, "seed", ["My app's frontend is Next.js."], date="2026-01-10"),
                _session(1, "seed", ["The same app's database is Postgres."], date="2026-01-17"),
                _session(
                    2,
                    "probe",
                    ["Recommend a deployment setup for my app's full stack."],
                    date="2026-01-25",
                    want_recall=True,
                    expect_substring=["Next.js", "Postgres"],
                    evidence_session_idx=0,
                ),
            ],
            rationale="two stack facts across sessions must both surface",
        ),
        _case(
            case="MEM-MULTI-family-03",
            mem_id="MEM-0103",
            ability="multi-session",
            provenance="longmemeval-derived",
            lme_question_type="multi-session",
            user_id="usermulti03",
            sessions=[
                _session(0, "seed", ["I have two kids."], date="2026-03-01"),
                _session(1, "seed", ["They are both in elementary school."], date="2026-03-09"),
                _session(
                    2,
                    "probe",
                    ["Suggest a weekend activity suitable for my family."],
                    date="2026-03-15",
                    want_recall=True,
                    expect_substring=["kids", "elementary"],
                    evidence_session_idx=0,
                ),
            ],
            rationale="count (s0) + age band (s1) combined",
        ),
        _case(
            case="MEM-MULTI-diet-04",
            mem_id="MEM-0104",
            ability="multi-session",
            provenance="longmemeval-derived",
            lme_question_type="multi-session",
            user_id="usermulti04",
            sessions=[
                _session(0, "seed", ["I'm vegetarian."], date="2026-04-01"),
                _session(1, "seed", ["I also avoid dairy."], date="2026-04-05"),
                _session(
                    2,
                    "probe",
                    ["Plan a dinner that fits all my dietary needs."],
                    date="2026-04-12",
                    want_recall=True,
                    expect_substring=["vegetarian", "dairy"],
                    evidence_session_idx=0,
                ),
            ],
            rationale="two diet constraints across sessions",
        ),
    ]


def _temporal_cases() -> list[dict]:
    """Seeds dated weeks apart where a value CHANGES over time; the probe asks
    for the MOST RECENT value -> recall + recency."""
    return [
        _case(
            case="MEM-TEMPORAL-city-move-01",
            mem_id="MEM-0201",
            ability="temporal",
            provenance="longmemeval-derived",
            lme_question_type="temporal-reasoning",
            user_id="usertemp01",
            sessions=[
                _session(0, "seed", ["I live in Chicago."], date="2026-01-01"),
                _session(1, "seed", ["I just moved — I now live in Denver."], date="2026-04-01"),
                _session(
                    2,
                    "probe",
                    ["Where do I currently live?"],
                    date="2026-04-10",
                    want_recall=True,
                    expect_substring=["Denver"],
                    evidence_session_idx=1,
                ),
            ],
            rationale="most-recent city is Denver (s1), not Chicago (s0) -> recency",
        ),
        _case(
            case="MEM-TEMPORAL-role-change-02",
            mem_id="MEM-0202",
            ability="temporal",
            provenance="longmemeval-derived",
            lme_question_type="temporal-reasoning",
            user_id="usertemp02",
            sessions=[
                _session(0, "seed", ["I'm a junior developer."], date="2026-01-15"),
                _session(1, "seed", ["I got promoted to senior developer."], date="2026-05-15"),
                _session(
                    2,
                    "probe",
                    ["What's my current seniority level?"],
                    date="2026-05-20",
                    want_recall=True,
                    expect_substring=["senior"],
                    evidence_session_idx=1,
                ),
            ],
            rationale="latest role wins",
        ),
        _case(
            case="MEM-TEMPORAL-tool-switch-03",
            mem_id="MEM-0203",
            ability="temporal",
            provenance="longmemeval-derived",
            lme_question_type="temporal-reasoning",
            user_id="usertemp03",
            sessions=[
                _session(0, "seed", ["I use npm for my JS projects."], date="2026-02-01"),
                _session(1, "seed", ["I've switched to pnpm now."], date="2026-05-01"),
                _session(
                    2,
                    "probe",
                    ["Which package manager should you use in examples for me?"],
                    date="2026-05-05",
                    want_recall=True,
                    expect_substring=["pnpm"],
                    evidence_session_idx=1,
                ),
            ],
            rationale="recency: pnpm replaces npm",
        ),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# PHASE B — knowledge-update / contradiction (seed X, correct to Y, probe -> Y)
# ─────────────────────────────────────────────────────────────────────────────

def _knowledge_update_cases() -> list[dict]:
    return [
        _case(
            case="MEM-UPDATE-units-01",
            mem_id="MEM-0301",
            ability="knowledge-update",
            provenance="longmemeval-derived",
            lme_question_type="knowledge-update",
            user_id="userupd01",
            sessions=[
                _session(0, "seed", ["I prefer imperial units."], date="2026-01-01"),
                _session(1, "seed", ["Actually, scratch that — I prefer metric units now."], date="2026-02-01"),
                _session(
                    2,
                    "probe",
                    ["Which unit system should you use for me?"],
                    date="2026-02-05",
                    want_recall=True,
                    expect_substring=["metric"],
                    evidence_session_idx=1,
                ),
            ],
            rationale="ADD-vs-UPDATE: must return metric (Y), not imperial (X)",
        ),
        _case(
            case="MEM-UPDATE-name-02",
            mem_id="MEM-0302",
            ability="knowledge-update",
            provenance="longmemeval-derived",
            lme_question_type="knowledge-update",
            user_id="userupd02",
            sessions=[
                _session(0, "seed", ["Call me Alex."], date="2026-03-01"),
                _session(1, "seed", ["I go by Sam now, please use that."], date="2026-03-20"),
                _session(
                    2,
                    "probe",
                    ["What name should you address me by?"],
                    date="2026-03-25",
                    want_recall=True,
                    expect_substring=["Sam"],
                    evidence_session_idx=1,
                ),
            ],
            rationale="corrected name Sam (Y), not Alex (X)",
        ),
        _case(
            case="MEM-UPDATE-language-03",
            mem_id="MEM-0303",
            ability="knowledge-update",
            provenance="longmemeval-derived",
            lme_question_type="knowledge-update",
            user_id="userupd03",
            sessions=[
                _session(0, "seed", ["My main language is Python."], date="2026-01-10"),
                _session(1, "seed", ["I've moved to Go as my main language."], date="2026-04-10"),
                _session(
                    2,
                    "probe",
                    ["What language should code examples be in for me?"],
                    date="2026-04-15",
                    want_recall=True,
                    expect_substring=["Go"],
                    evidence_session_idx=1,
                ),
            ],
            rationale="Go (Y) supersedes Python (X)",
        ),
        _case(
            case="MEM-UPDATE-diet-04",
            mem_id="MEM-0304",
            ability="knowledge-update",
            provenance="longmemeval-derived",
            lme_question_type="knowledge-update",
            user_id="userupd04",
            sessions=[
                _session(0, "seed", ["I'm vegetarian."], date="2026-02-01"),
                _session(1, "seed", ["I'm fully vegan now, not just vegetarian."], date="2026-05-01"),
                _session(
                    2,
                    "probe",
                    ["Plan a meal that matches my current diet."],
                    date="2026-05-04",
                    want_recall=True,
                    expect_substring=["vegan"],
                    evidence_session_idx=1,
                ),
            ],
            rationale="vegan (Y) supersedes vegetarian (X)",
        ),
        _case(
            case="MEM-UPDATE-timezone-05",
            mem_id="MEM-0305",
            ability="knowledge-update",
            provenance="longmemeval-derived",
            lme_question_type="knowledge-update",
            user_id="userupd05",
            sessions=[
                _session(0, "seed", ["I'm in the Eastern timezone."], date="2026-01-05"),
                _session(1, "seed", ["I relocated to the Pacific timezone."], date="2026-03-05"),
                _session(
                    2,
                    "probe",
                    ["What's a good meeting time for me in the morning?"],
                    date="2026-03-10",
                    want_recall=True,
                    expect_substring=["Pacific"],
                    evidence_session_idx=1,
                ),
            ],
            rationale="Pacific (Y) supersedes Eastern (X)",
        ),
        _case(
            case="MEM-UPDATE-framework-06",
            mem_id="MEM-0306",
            ability="knowledge-update",
            provenance="longmemeval-derived",
            lme_question_type="knowledge-update",
            user_id="userupd06",
            sessions=[
                _session(0, "seed", ["My web framework is Flask."], date="2026-02-10"),
                _session(1, "seed", ["I rewrote everything in FastAPI."], date="2026-04-20"),
                _session(
                    2,
                    "probe",
                    ["Show me a route handler in my current web framework."],
                    date="2026-04-25",
                    want_recall=True,
                    expect_substring=["FastAPI"],
                    evidence_session_idx=1,
                ),
            ],
            rationale="FastAPI (Y) supersedes Flask (X)",
        ),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# PHASE C — persona-drift (LoCoMo SHAPE only, paraphrased; CC BY-NC reference)
# ─────────────────────────────────────────────────────────────────────────────

def _persona_drift_cases() -> list[dict]:
    """Hand-authored personas whose preference EVOLVES over 3 sessions; the probe
    must reflect the current state. Borrows LoCoMo's persona + evolving-event
    SHAPE only — independently authored, no LoCoMo text (see the no-verbatim test)."""
    return [
        _case(
            case="MEM-PERSONA-fitness-01",
            mem_id="MEM-0401",
            ability="persona-drift",
            provenance="synthetic-locomo-shape",
            user_id="userpers01",
            sessions=[
                _session(0, "seed", ["I'm just starting to get into running, total beginner."], date="2026-01-01"),
                _session(1, "seed", ["I've been running a few months — I did my first 10k."], date="2026-03-01"),
                _session(2, "seed", ["I'm training for a marathon now."], date="2026-05-01"),
                _session(
                    3,
                    "probe",
                    ["Suggest a training plan appropriate for my current level."],
                    date="2026-05-10",
                    want_recall=True,
                    expect_substring=["marathon"],
                    evidence_session_idx=2,
                ),
            ],
            rationale="persona evolves beginner -> 10k -> marathon; current state is marathon",
        ),
        _case(
            case="MEM-PERSONA-career-02",
            mem_id="MEM-0402",
            ability="persona-drift",
            provenance="synthetic-locomo-shape",
            user_id="userpers02",
            sessions=[
                _session(0, "seed", ["I'm studying computer science in college."], date="2026-01-15"),
                _session(1, "seed", ["I landed an internship at a startup."], date="2026-03-15"),
                _session(2, "seed", ["I just accepted a full-time offer as a software engineer."], date="2026-05-15"),
                _session(
                    3,
                    "probe",
                    ["Give me advice suited to where I am in my career right now."],
                    date="2026-05-20",
                    want_recall=True,
                    expect_substring=["full-time", "engineer"],
                    evidence_session_idx=2,
                ),
            ],
            rationale="student -> intern -> full-time engineer; current state is full-time",
        ),
        _case(
            case="MEM-PERSONA-hobby-03",
            mem_id="MEM-0403",
            ability="persona-drift",
            provenance="synthetic-locomo-shape",
            user_id="userpers03",
            sessions=[
                _session(0, "seed", ["I've been getting into film photography."], date="2026-02-01"),
                _session(1, "seed", ["I sold my film camera and switched to digital."], date="2026-04-01"),
                _session(2, "seed", ["Now I mostly shoot video, not stills."], date="2026-05-25"),
                _session(
                    3,
                    "probe",
                    ["Recommend gear for my current photography/video interest."],
                    date="2026-05-30",
                    want_recall=True,
                    expect_substring=["video"],
                    evidence_session_idx=2,
                ),
            ],
            rationale="film -> digital -> video; current interest is video",
        ),
    ]


def build_corpus() -> list[dict]:
    """Assemble the full corpus. CONTROLS FIRST (failure-paths-first), then the
    happy phases. Deterministic — two calls return identical output (Check 7)."""
    rows: list[dict] = []
    # Controls (precision guards) first.
    rows += _leak_control_cases()
    rows += _abstention_cases()
    # Phase A — cross-session recall (gates B/C).
    rows += _recall_cases()
    rows += _multi_session_cases()
    rows += _temporal_cases()
    # Phase B — knowledge-update / contradiction.
    rows += _knowledge_update_cases()
    # Phase C — persona-drift (LoCoMo shape).
    rows += _persona_drift_cases()
    return rows


def main() -> int:
    corpus = build_corpus()
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(corpus, indent=2, ensure_ascii=False) + "\n")
    by_ability: dict[str, int] = {}
    for c in corpus:
        by_ability[c["ability"]] = by_ability.get(c["ability"], 0) + 1
    print(f"wrote {len(corpus)} cases -> {OUT_PATH.relative_to(AGENT_ROOT)}")
    for ability, n in sorted(by_ability.items()):
        print(f"  {ability}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
