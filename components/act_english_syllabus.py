"""Generated ACT-English syllabus data asset (D3 spec FR-9).

GENERATED FILE — do not edit by hand. Emitted from the canonical
docs/plan/act-english-syllabus.seed.json (the human-gated 32-topic
extraction of docs/ACT-syllabus/act-english.pdf, brainstorm
docs/plan/act-english-full-bank.brainstorm.md). Regenerate (emits this
file AND components/act_english_syllabus.py):

  .venv/bin/python scripts/emit_syllabus.py

Pure stdlib data: consumed by coverage tooling (the standard x band ratchet)
and generation targeting. The frontend twin is
``frontend/lib/adapters/engine/_act_english_syllabus.ts``; both planes are
pinned byte-for-byte to the canonical seed by the FR-10 drift test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class ActEnglishStandard:
    """One syllabus standard: a teachable ACT-English topic with the score
    bands it appears in and the app practice skill that owns it."""

    standard_id: int
    name: str
    category: str
    bands: tuple[int, ...]
    app_skill: str


ACT_ENGLISH_SYLLABUS: Final[tuple[ActEnglishStandard, ...]] = (
    ActEnglishStandard(
        standard_id=1,
        name="Topic and organization (topic/concluding sentences, transitions, passage development, thesis, argument tracing)",
        category="production",
        bands=(1, 2, 3, 4, 5),
        app_skill="s-org",
    ),
    ActEnglishStandard(
        standard_id=2,
        name="Purpose (text purpose, connotation, audience, ethos/pathos/logos)",
        category="production",
        bands=(2, 3, 4),
        app_skill="s-rhet",
    ),
    ActEnglishStandard(
        standard_id=3,
        name="Common word errors",
        category="knowledge",
        bands=(1,),
        app_skill="s-gram",
    ),
    ActEnglishStandard(
        standard_id=4,
        name="Style and tone (formality, tone comparison, figures of speech)",
        category="knowledge",
        bands=(2, 3, 4),
        app_skill="s-rhet",
    ),
    ActEnglishStandard(
        standard_id=5,
        name="Redundancy",
        category="knowledge",
        bands=(3,),
        app_skill="s-style",
    ),
    ActEnglishStandard(
        standard_id=6,
        name="Shades of meaning (related words, connotation)",
        category="knowledge",
        bands=(3,),
        app_skill="s-style",
    ),
    ActEnglishStandard(
        standard_id=7,
        name="Correlative conjunctions",
        category="knowledge",
        bands=(3, 4),
        app_skill="s-gram",
    ),
    ActEnglishStandard(
        standard_id=8,
        name="Word nuance (precision, connotation/denotation, revisions)",
        category="knowledge",
        bands=(4,),
        app_skill="s-style",
    ),
    ActEnglishStandard(
        standard_id=9,
        name="Word usage (foreign expressions, related words, redundancy, revisions)",
        category="knowledge",
        bands=(5,),
        app_skill="s-style",
    ),
    ActEnglishStandard(
        standard_id=10,
        name="Joining simple clauses (coordinating/subordinating conjunctions, compound sentences)",
        category="conventions",
        bands=(1,),
        app_skill="s-sent",
    ),
    ActEnglishStandard(
        standard_id=11,
        name="Inappropriate shifts in verb tense",
        category="conventions",
        bands=(1, 2),
        app_skill="s-gram",
    ),
    ActEnglishStandard(
        standard_id=12,
        name="Irregular past tense and past participle",
        category="conventions",
        bands=(1,),
        app_skill="s-gram",
    ),
    ActEnglishStandard(
        standard_id=13,
        name="Comparative and superlative adjectives/adverbs",
        category="conventions",
        bands=(1, 3),
        app_skill="s-gram",
    ),
    ActEnglishStandard(
        standard_id=14,
        name="Commas (series, dates/places, addresses, introductory, compound/complex, coordinate adjectives, nonrestrictive, antithetical)",
        category="conventions",
        bands=(1, 2, 3, 4, 5),
        app_skill="s-punc",
    ),
    ActEnglishStandard(
        standard_id=15,
        name="Sentences, fragments and run-ons",
        category="conventions",
        bands=(2, 3, 4),
        app_skill="s-sent",
    ),
    ActEnglishStandard(
        standard_id=16,
        name="Adjectives vs. adverbs",
        category="conventions",
        bands=(2,),
        app_skill="s-gram",
    ),
    ActEnglishStandard(
        standard_id=17,
        name="Subject-verb agreement (incl. compound subjects, indefinite pronouns)",
        category="conventions",
        bands=(2, 3, 5),
        app_skill="s-gram",
    ),
    ActEnglishStandard(
        standard_id=18,
        name="Pronoun-antecedent agreement",
        category="conventions",
        bands=(2,),
        app_skill="s-gram",
    ),
    ActEnglishStandard(
        standard_id=19,
        name="Frequently confused words",
        category="conventions",
        bands=(2, 5),
        app_skill="s-gram",
    ),
    ActEnglishStandard(
        standard_id=20,
        name="Adjective placement",
        category="conventions",
        bands=(3,),
        app_skill="s-sent",
    ),
    ActEnglishStandard(
        standard_id=21,
        name="Misplaced and dangling modifiers",
        category="conventions",
        bands=(3, 4),
        app_skill="s-sent",
    ),
    ActEnglishStandard(
        standard_id=22,
        name="Relative pronouns (who/whom/whose/which/that)",
        category="conventions",
        bands=(3, 5),
        app_skill="s-gram",
    ),
    ActEnglishStandard(
        standard_id=23,
        name="Idiomatic expressions",
        category="conventions",
        bands=(3,),
        app_skill="s-gram",
    ),
    ActEnglishStandard(
        standard_id=24,
        name="Apostrophes (plural vs possessive, compound/joint possession)",
        category="conventions",
        bands=(3, 4, 5),
        app_skill="s-punc",
    ),
    ActEnglishStandard(
        standard_id=25,
        name="Parallelism / parallel structure",
        category="conventions",
        bands=(4, 5),
        app_skill="s-sent",
    ),
    ActEnglishStandard(
        standard_id=26,
        name="Verb and pronoun consistency (shifts in number/person/tense, active vs passive)",
        category="conventions",
        bands=(4, 5),
        app_skill="s-gram",
    ),
    ActEnglishStandard(
        standard_id=27,
        name="Verb tense (progressive, perfect, past review)",
        category="conventions",
        bands=(4,),
        app_skill="s-gram",
    ),
    ActEnglishStandard(
        standard_id=28,
        name="Pronouns (vague reference, subject/object, reflexive, who)",
        category="conventions",
        bands=(4, 5),
        app_skill="s-gram",
    ),
    ActEnglishStandard(
        standard_id=29,
        name="Colons and semicolons (lists, joining clauses)",
        category="conventions",
        bands=(4, 5),
        app_skill="s-punc",
    ),
    ActEnglishStandard(
        standard_id=30,
        name="Parenthetical elements (appositives, dashes, relative-clause combining)",
        category="conventions",
        bands=(4,),
        app_skill="s-punc",
    ),
    ActEnglishStandard(
        standard_id=31,
        name="Restrictive and nonrestrictive elements",
        category="conventions",
        bands=(5,),
        app_skill="s-punc",
    ),
    ActEnglishStandard(
        standard_id=32,
        name="Advanced sentence revision (double/illogical comparisons, modifier + parallel-structure review)",
        category="conventions",
        bands=(5,),
        app_skill="s-sent",
    ),
)
