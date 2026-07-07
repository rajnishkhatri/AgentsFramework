"""Hint-ladder types + interim authored asset (FR-20, ADR-0012).

The ladder has EXACTLY three rungs — the schema is the enforcement (FR-20
"no assertion rung exists" is a type-level fact, not a prose rule):

1. **probe** — Feynman teach-back: ask the learner to articulate their
   current reasoning; adds no new information.
2. **conceptual** — rule-level: names the governing rule; never references a
   specific choice.
3. **directive** — narrows the search (what to check, what to eliminate);
   NEVER asserts or uniquely identifies the answer.

Pre-submit mode serves hints ONLY from ``reviewed=True`` rungs
(``rungs_for_question`` is the serving gate). This module carries the
hand-authored interim asset (agent design §11 step 2) keyed to the dev-seed
questions; Phase 4's generator + ``hint`` table replace it (ADR-0006 second
amendment), at which point ``authored_by`` becomes ``generated_by``
provenance.

Framework-agnostic (Invariant #3): stdlib + Pydantic only.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, field_validator

RUNG_PROBE: Final = 1
RUNG_CONCEPTUAL: Final = 2
RUNG_DIRECTIVE: Final = 3


class HintRung(BaseModel):
    """One leak-checked rung of a question's hint ladder."""

    question_id: str
    rung: Literal[1, 2, 3]
    body_md: str
    reviewed: bool = False
    authored_by: str

    model_config = ConfigDict(frozen=True)

    @field_validator("body_md")
    @classmethod
    def _body_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("hint body must be non-empty")
        return v


def rungs_for_question(
    question_id: str,
    source: list[HintRung] | None = None,
) -> list[HintRung]:
    """Serve the reviewed ladder for a question, probe → directive (FR-20).

    The gate: unreviewed rungs are filtered here, so an ungated row can never
    reach a learner regardless of how it entered ``source``.

    Default source = the authored asset PLUS the generated bank ladders
    (coach-bank-hints FR-D1): the ADR-0021 bank serves ``ti-gen-*`` ids the
    authored rows never match, and an empty ladder makes the persona
    free-generate (the Stage-0 leak class). Imported lazily so the generated
    data asset — which imports ``HintRung`` from THIS module — stays a
    one-way import at load time.
    """
    if source is None:
        from components.subject_coach_bank_hints import BANK_RUNGS

        rows: list[HintRung] = [*AUTHORED_RUNGS, *BANK_RUNGS]
    else:
        rows = source
    served = [r for r in rows if r.question_id == question_id and r.reviewed]
    return sorted(served, key=lambda r: r.rung)


def _rung(question_id: str, rung: Literal[1, 2, 3], body_md: str) -> HintRung:
    return HintRung(
        question_id=question_id,
        rung=rung,
        body_md=body_md,
        reviewed=True,  # hand-authored + human leak-checked at authoring
        authored_by="human",
    )


# Interim authored asset — dev-seed corpus (frontend/lib/adapters/engine/
# _dev_seed.ts). One full ladder per question. Leak discipline: rung 3 may
# narrow ("check X", "eliminate Y-shaped choices") but never names a letter
# or uniquely identifies the correct choice.
AUTHORED_RUNGS: Final[list[HintRung]] = [
    # q-punc-1 — nonrestrictive clause commas
    _rung(
        "q-punc-1",
        RUNG_PROBE,
        "Read the sentence aloud — where do you naturally pause? What job is "
        "the phrase 'which opened in 1974' doing in this sentence?",
    ),
    _rung(
        "q-punc-1",
        RUNG_CONCEPTUAL,
        "Extra, droppable information inside a sentence — a nonrestrictive "
        "clause — has to be fenced off from the rest of the sentence on "
        "**both** sides, not just one.",
    ),
    _rung(
        "q-punc-1",
        RUNG_DIRECTIVE,
        "The clause opens with a comma before 'which'. Check each choice: "
        "does it close what that opening comma started?",
    ),
    # q-gram-1 — subject-verb agreement with 'each'
    _rung(
        "q-gram-1",
        RUNG_PROBE,
        "Cover the phrase 'of the runners' and read what's left. What is the "
        "subject of this sentence, in your own words?",
    ),
    _rung(
        "q-gram-1",
        RUNG_CONCEPTUAL,
        "Words like 'each' and 'every' are always singular — no matter what "
        "plural noun sits inside the phrase right after them.",
    ),
    _rung(
        "q-gram-1",
        RUNG_DIRECTIVE,
        "So the subject is singular. Which verb forms can agree with a "
        "singular subject? Eliminate every choice that stays plural.",
    ),
    # q-sent-1 — dangling modifier
    _rung(
        "q-sent-1",
        RUNG_PROBE,
        "Who was walking to the store? Say it in your own words before you "
        "look at the choices again.",
    ),
    _rung(
        "q-sent-1",
        RUNG_CONCEPTUAL,
        "An opening '-ing' phrase attaches to the first noun after the comma "
        "— that noun must be the one actually doing the action.",
    ),
    _rung(
        "q-sent-1",
        RUNG_DIRECTIVE,
        "Test each choice: can the noun right after the comma actually walk "
        "to the store? Eliminate every choice where it can't.",
    ),
    # q-rhet-1 — redundant intensifiers / concision
    _rung(
        "q-rhet-1",
        RUNG_PROBE,
        "What would the sentence lose if you dropped one of the two "
        "underlined words? Try reading it each way.",
    ),
    _rung(
        "q-rhet-1",
        RUNG_CONCEPTUAL,
        "Two intensifiers stacked on one adjective do the same job twice; "
        "concise writing keeps a single, precise modifier.",
    ),
    _rung(
        "q-rhet-1",
        RUNG_DIRECTIVE,
        "Compare the single-word choices: which one carries the emphasis on "
        "its own, without repeating another word's work?",
    ),
    # q-org-1 — transition word logic
    _rung(
        "q-org-1",
        RUNG_PROBE,
        "In your own words: how are these two sentences related — time, "
        "contrast, example, or simple addition?",
    ),
    _rung(
        "q-org-1",
        RUNG_CONCEPTUAL,
        "A transition must name the **actual** logical relationship. A long "
        "process followed by its outcome is a relationship in time.",
    ),
    _rung(
        "q-org-1",
        RUNG_DIRECTIVE,
        "Which choices signal time passing? Rule out any that promise a "
        "contrast or an example the passage never delivers.",
    ),
    # q-style-1 — redundancy with 'return back'
    _rung(
        "q-style-1",
        RUNG_PROBE,
        "What does the verb 'return' already tell you about the direction "
        "the book is going?",
    ),
    _rung(
        "q-style-1",
        RUNG_CONCEPTUAL,
        "When a verb's meaning already contains a word's idea, adding that "
        "word is redundancy — and the fix is usually removal, not "
        "replacement.",
    ),
    _rung(
        "q-style-1",
        RUNG_DIRECTIVE,
        "Try the sentence with the underlined word gone entirely — does any "
        "meaning disappear? Compare that against the choices that add words.",
    ),
]
