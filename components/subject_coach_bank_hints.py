"""Generated bank hint-ladder rungs (coach-bank-hints spec FR-B1).

GENERATED FILE — do not edit by hand. Every row was EARNED through the
hint verifier cascade (components/hint_generation.py: schema ->
deterministic per-rung leakage -> duplicate) driven by
scripts/generate_hints.py; `generated_by` carries the promoting run's
"<model>@<workflow_id>" stamp. Regenerate (reads
docs/plan/coach-bank-hints.seed.json, emits this file AND
components/subject_coach_bank_hints.py):

  .venv/bin/python scripts/emit_hint_bank.py

``authored_by`` carries the wire ``generated_by`` stamp VERBATIM (FR-B3) — the
provenance value is identical on both serving planes. Served by
``components.subject_coach_hints.rungs_for_question`` (AUTHORED + BANK), which
imports this module lazily so this data asset stays one-way-importable.
"""

from __future__ import annotations

from typing import Final

from components.subject_coach_hints import HintRung

BANK_RUNGS: Final[list[HintRung]] = [
    HintRung(
        question_id='ti-gen-2fddf2bbbfb1b061',
        rung=1,
        body_md="What do you think the phrase 'consistent to' means in this context?",
        reviewed=True,
        authored_by='gpt-4o-mini@bfea31359cb34f868096a878216c3ae1',
    ),
    HintRung(
        question_id='ti-gen-2fddf2bbbfb1b061',
        rung=2,
        body_md='Consider how idiomatic expressions often have specific prepositions that are used with them.',
        reviewed=True,
        authored_by='gpt-4o-mini@bfea31359cb34f868096a878216c3ae1',
    ),
    HintRung(
        question_id='ti-gen-2fddf2bbbfb1b061',
        rung=3,
        body_md='Look at the relationship between the results and the hypothesis; think about common phrases that describe this relationship.',
        reviewed=True,
        authored_by='gpt-4o-mini@bfea31359cb34f868096a878216c3ae1',
    ),
    HintRung(
        question_id='ti-gen-949378b918123353',
        rung=1,
        body_md="What do you think about the phrase 'super weird' in the context of a lab report?",
        reviewed=True,
        authored_by='gpt-4o-mini@b84a0e653d4545fab68539e5b35f7159',
    ),
    HintRung(
        question_id='ti-gen-949378b918123353',
        rung=2,
        body_md='Consider how word choice can affect the tone of a passage, especially in formal writing.',
        reviewed=True,
        authored_by='gpt-4o-mini@b84a0e653d4545fab68539e5b35f7159',
    ),
    HintRung(
        question_id='ti-gen-949378b918123353',
        rung=3,
        body_md='Look closely at the tone of the entire sentence and think about how each option aligns with that tone.',
        reviewed=True,
        authored_by='gpt-4o-mini@b84a0e653d4545fab68539e5b35f7159',
    ),
    HintRung(
        question_id='ti-gen-95b88bbdaeda2910',
        rung=1,
        body_md="What do you think about the word 'rise up' in this context? Do you feel it adds anything to the meaning of the sentence?",
        reviewed=True,
        authored_by='gpt-4o-mini@499f3f27b0e34c1fafcf69e3e8cbf2a3',
    ),
    HintRung(
        question_id='ti-gen-95b88bbdaeda2910',
        rung=2,
        body_md='Consider the concept of redundancy in language. What does it mean for a word to be redundant in a sentence?',
        reviewed=True,
        authored_by='gpt-4o-mini@499f3f27b0e34c1fafcf69e3e8cbf2a3',
    ),
    HintRung(
        question_id='ti-gen-95b88bbdaeda2910',
        rung=3,
        body_md='Look closely at the verb in the sentence. Are there any parts of the phrase that might be unnecessary or repetitive?',
        reviewed=True,
        authored_by='gpt-4o-mini@499f3f27b0e34c1fafcf69e3e8cbf2a3',
    ),
    HintRung(
        question_id='ti-gen-99e05e271a9f6c92',
        rung=1,
        body_md='What do you think about the verb form used in the sentence?',
        reviewed=True,
        authored_by='gpt-4o-mini@d8b4e41f82784b89bd294266d4f82c57',
    ),
    HintRung(
        question_id='ti-gen-99e05e271a9f6c92',
        rung=2,
        body_md='Consider the rule for using verb forms to indicate actions that were ongoing before a specific past event.',
        reviewed=True,
        authored_by='gpt-4o-mini@d8b4e41f82784b89bd294266d4f82c57',
    ),
    HintRung(
        question_id='ti-gen-99e05e271a9f6c92',
        rung=3,
        body_md='Look closely at the timing of the action in relation to the arrival of the bus. How does that affect the verb form you should choose?',
        reviewed=True,
        authored_by='gpt-4o-mini@d8b4e41f82784b89bd294266d4f82c57',
    ),
    HintRung(
        question_id='ti-gen-9fb6fd5eaae7fdf9',
        rung=1,
        body_md="What do you think about the phrase that is underlined? How does it convey the committee's agreement?",
        reviewed=True,
        authored_by='gpt-4o-mini@3b4837bd5e3d4ec199afa6eae923701a',
    ),
    HintRung(
        question_id='ti-gen-9fb6fd5eaae7fdf9',
        rung=2,
        body_md='Consider the concept of conciseness in writing. How can we express an idea using fewer words without losing its meaning?',
        reviewed=True,
        authored_by='gpt-4o-mini@ffa220c7af7e43bc9fc60293cfcee6f1',
    ),
    HintRung(
        question_id='ti-gen-9fb6fd5eaae7fdf9',
        rung=3,
        body_md='Look closely at the options and compare how each one expresses the idea of agreement. Which options seem to use more words than necessary?',
        reviewed=True,
        authored_by='gpt-4o-mini@3b4837bd5e3d4ec199afa6eae923701a',
    ),
    HintRung(
        question_id='ti-gen-abe42cfc107b3d34',
        rung=1,
        body_md='What do you think the relationship is between Ella training all winter and her finishing in her best time?',
        reviewed=True,
        authored_by='gpt-4o-mini@587fd740129f4b8b800e0661d115e744',
    ),
    HintRung(
        question_id='ti-gen-abe42cfc107b3d34',
        rung=2,
        body_md='Consider how transitions can indicate cause and effect or contrast between ideas.',
        reviewed=True,
        authored_by='gpt-4o-mini@587fd740129f4b8b800e0661d115e744',
    ),
    HintRung(
        question_id='ti-gen-abe42cfc107b3d34',
        rung=3,
        body_md='Look closely at the second sentence and think about how it relates to the first. What kind of relationship does it suggest?',
        reviewed=True,
        authored_by='gpt-4o-mini@587fd740129f4b8b800e0661d115e744',
    ),
    HintRung(
        question_id='ti-gen-c49644db17cedd1b',
        rung=1,
        body_md='What do you think about the structure of the series in the sentence?',
        reviewed=True,
        authored_by='gpt-4o-mini@5a892a1ad2b64cf28914de5cb8b75d99',
    ),
    HintRung(
        question_id='ti-gen-c49644db17cedd1b',
        rung=2,
        body_md='Consider the rule of parallelism in lists; items in a series should maintain the same grammatical form.',
        reviewed=True,
        authored_by='gpt-4o-mini@5a892a1ad2b64cf28914de5cb8b75d99',
    ),
    HintRung(
        question_id='ti-gen-c49644db17cedd1b',
        rung=3,
        body_md='Look closely at the verbs in the series and check if they all share the same form.',
        reviewed=True,
        authored_by='gpt-4o-mini@5a892a1ad2b64cf28914de5cb8b75d99',
    ),
    HintRung(
        question_id='ti-gen-eb8028a2b674681d',
        rung=1,
        body_md='What do you think is the purpose of the punctuation in this sentence?',
        reviewed=True,
        authored_by='gpt-4o-mini@95eaa48cb88b43ccab2fba2769efcd57',
    ),
    HintRung(
        question_id='ti-gen-eb8028a2b674681d',
        rung=2,
        body_md='Consider the rule about using punctuation to introduce lists.',
        reviewed=True,
        authored_by='gpt-4o-mini@95eaa48cb88b43ccab2fba2769efcd57',
    ),
    HintRung(
        question_id='ti-gen-eb8028a2b674681d',
        rung=3,
        body_md='Look closely at the clause before the list; does it form a complete thought?',
        reviewed=True,
        authored_by='gpt-4o-mini@95eaa48cb88b43ccab2fba2769efcd57',
    ),
]
