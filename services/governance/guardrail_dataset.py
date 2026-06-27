"""Synthetic guardrail dataset: PIArena schema + offline six-stage pipeline.

Sprint 2 (Dataset Foundation) of the dimension-aware guardrails program
(``docs/plans/guardrails_tuning_sprint_board.md``). This Layer 2 module
holds the *deterministic, CI-safe* half of the dataset workstream:

* :class:`GuardrailSample` — the frozen PIArena-derived sample schema
  (``docs/Architectures/GUARDRAILS_DIMENSION_SPACE.md`` §E.1).
* The pure six-stage SafeGuard pipeline helpers
  (``seed → preprocess → dedup → augment → teacher-label → freeze``).
* The **contamination guard** — NotInject rows are held-out / test-only
  and must never enter the train split (§E.1, frozen contract).
* JSONL load/freeze helpers.

The offline CLI driver (``scripts/generate_guardrail_dataset.py``) is a thin
wrapper over these helpers; the only non-deterministic stage is teacher
labeling, which is injected as a callable so this module — and every test
that imports it — stays free of live LLM calls (CI-safe).

NO ``langgraph`` / ``langchain`` imports (AGENTS.md invariant #4). Uses only
``pydantic`` + stdlib, peer to ``guardrail_validator.py`` in Layer 2.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable, Sequence
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger("services.governance.guardrail_dataset")


# ─────────────────────────────────────────────────────────────────────
# Frozen vocabulary (GUARDRAILS_DIMENSION_SPACE.md §E.1)
# ─────────────────────────────────────────────────────────────────────


class Label(str, Enum):
    """Ground-truth verdict for a sample."""

    INJECTION = "injection"  # must be rejected by the input rail
    BENIGN = "benign"  # must be accepted by the input rail


class Rail(str, Enum):
    """The NeMo rail a sample exercises."""

    INPUT = "input"
    RETRIEVAL = "retrieval"
    DIALOG = "dialog"
    EXECUTION = "execution"
    OUTPUT = "output"


class Dimension(str, Enum):
    """Attack/benign sub-category (the ``dimension`` field)."""

    OVERRIDE = "override"  # "ignore previous instructions"
    EXFILTRATION = "exfiltration"  # "reveal your system prompt"
    JAILBREAK = "jailbreak"  # persona / mode tricks
    OBFUSCATED = "obfuscated"  # base64 / encoded injection payload
    OVER_DEFENSE = "over_defense"  # benign-but-trigger-word (NotInject style)
    DOMAIN_ACCEPT = "domain_accept"  # legitimate domain prompts (S1-S8)


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class DatasetSplit(str, Enum):
    """Which partition a row belongs to."""

    TRAIN = "train"
    HELD_OUT = "held_out"  # over-defense eval / NotInject / frozen eval set


# Provenance value that triggers the contamination guard. Rows tagged with
# this source are the held-out over-defense set and MUST stay test-only.
NOTINJECT_SOURCE = "notinject"

_OWASP_RE = re.compile(r"^LLM\d{2}$")


class ContaminationError(Exception):
    """Raised when a held-out (NotInject) row leaks into the train split.

    SafeGuard documented a contamination incident that inflated reported
    accuracy to 99.38%; this guard fails loudly to prevent a repeat.
    """


# ─────────────────────────────────────────────────────────────────────
# Schema (GUARDRAILS_DIMENSION_SPACE.md §E.1)
# ─────────────────────────────────────────────────────────────────────


class GuardrailSample(BaseModel):
    """One PIArena-derived dataset row.

    The nine content fields are the frozen Sprint 0 contract; ``split`` is
    explicit split-tracking metadata (S2-2). A row-level validator enforces
    the frozen contamination guard: ``source == "notinject"`` rows must be
    held-out.
    """

    model_config = {"extra": "forbid"}

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    label: Label
    rail: Rail
    owasp: str
    dimension: Dimension
    trigger_words: list[str] = Field(default_factory=list)
    difficulty: Difficulty
    source: str = Field(min_length=1)
    split: DatasetSplit

    @field_validator("owasp")
    @classmethod
    def _owasp_shape(cls, value: str) -> str:
        if not _OWASP_RE.match(value):
            raise ValueError(f"owasp must look like 'LLM01' (got {value!r})")
        return value

    @model_validator(mode="after")
    def _contamination_guard(self) -> GuardrailSample:
        # Frozen contract (§E.1): NotInject is held-out / test-only.
        if self.source == NOTINJECT_SOURCE and self.split is not DatasetSplit.HELD_OUT:
            raise ValueError(
                "contamination: source='notinject' rows must be in the "
                f"held_out split (got split={self.split.value!r})"
            )
        return self


# ─────────────────────────────────────────────────────────────────────
# Stage helpers (pure, deterministic, CI-safe)
# ─────────────────────────────────────────────────────────────────────


def normalize_text(text: str) -> str:
    """Collapse internal whitespace runs and strip ends (deterministic)."""
    return re.sub(r"\s+", " ", text).strip()


def preprocess(samples: Iterable[GuardrailSample]) -> list[GuardrailSample]:
    """Stage 2 — normalize each row's ``text`` (whitespace canonicalization)."""
    return [
        sample.model_copy(update={"text": normalize_text(sample.text)})
        for sample in samples
    ]


def dedup(samples: Iterable[GuardrailSample]) -> list[GuardrailSample]:
    """Stage 3 — drop later rows whose normalized text was already seen.

    Stable: keeps the first occurrence, preserving input order.
    """
    seen: set[str] = set()
    out: list[GuardrailSample] = []
    for sample in samples:
        key = normalize_text(sample.text).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(sample)
    return out


def augment_domain_negatives(
    frames: Sequence[GuardrailSample],
    trigger_words: Sequence[str],
    *,
    source: str = "local_augment",
) -> list[GuardrailSample]:
    """Stage 4 — grow benign-but-trigger-word hard negatives (deterministic).

    For each benign domain frame, prepend a benign clause that *mentions* a
    trigger word (e.g. "Before you ignore the noise, ..."). The result is a
    benign sample carrying a trigger word — exactly the over-defense shape a
    trigger-word-shortcut classifier mislabels. These are TRAIN-split local
    negatives, distinct from the held-out NotInject set, so they are tagged
    ``local_augment`` (never ``notinject``) and therefore may live in train.
    """
    augmented: list[GuardrailSample] = []
    for frame in frames:
        if frame.label is not Label.BENIGN:
            continue
        for word in trigger_words:
            clause = f"Before you {word} anything irrelevant, please help: "
            augmented.append(
                frame.model_copy(
                    update={
                        "id": f"{frame.id}__aug_{word.lower().replace(' ', '_')}",
                        "text": clause + frame.text,
                        "dimension": Dimension.OVER_DEFENSE,
                        "trigger_words": sorted({*frame.trigger_words, word}),
                        "difficulty": Difficulty.HARD,
                        "source": source,
                        "split": DatasetSplit.TRAIN,
                    }
                )
            )
    return augmented


def teacher_label(
    samples: Iterable[GuardrailSample],
    labeler: Callable[[str], Label] | None = None,
) -> list[GuardrailSample]:
    """Stage 5 — optional teacher (LLM) re-labeling.

    When ``labeler`` is ``None`` (the offline / CI default) this is a
    pass-through: the seed rows are already labeled. When a ``labeler`` is
    injected (the live teacher-LLM path, run offline only), it relabels each
    row. The callable is injected so this module never imports an LLM client,
    keeping it CI-safe; the live path is exercised by a ``live_llm`` test.
    """
    rows = list(samples)
    if labeler is None:
        return rows
    return [s.model_copy(update={"label": labeler(s.text)}) for s in rows]


def assert_no_contamination(samples: Iterable[GuardrailSample]) -> None:
    """Collection-level contamination guard (defense in depth).

    Raises :class:`ContaminationError` if any held-out NotInject row appears
    in the train split. Complements the row-level validator on
    :class:`GuardrailSample` for datasets assembled by mutating ``.split``.
    """
    leaked = [
        s.id
        for s in samples
        if s.source == NOTINJECT_SOURCE and s.split is DatasetSplit.TRAIN
    ]
    if leaked:
        raise ContaminationError(
            "NotInject rows must never enter the train split; leaked ids: "
            + ", ".join(sorted(leaked))
        )


def assert_unique_ids(samples: Sequence[GuardrailSample]) -> None:
    """Fail if any sample ``id`` is duplicated (ids drive dedup + split tracking)."""
    seen: set[str] = set()
    dupes: set[str] = set()
    for s in samples:
        if s.id in seen:
            dupes.add(s.id)
        seen.add(s.id)
    if dupes:
        raise ValueError(f"duplicate sample ids: {', '.join(sorted(dupes))}")


def split_counts(samples: Iterable[GuardrailSample]) -> dict[str, int]:
    """Return a ``{split_value: count}`` summary for reporting."""
    counts: dict[str, int] = {s.value: 0 for s in DatasetSplit}
    for sample in samples:
        counts[sample.split.value] += 1
    return counts


# ─────────────────────────────────────────────────────────────────────
# JSONL IO
# ─────────────────────────────────────────────────────────────────────


def load_jsonl(path: str | Path) -> list[GuardrailSample]:
    """Load and schema-validate a JSONL dataset file.

    Each non-blank line is parsed as one :class:`GuardrailSample`; malformed
    rows raise ``pydantic.ValidationError`` (schema) or the contamination
    guard ``ValueError`` (NotInject in train).
    """
    samples: list[GuardrailSample] = []
    for lineno, raw in enumerate(Path(path).read_text().splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            samples.append(GuardrailSample.model_validate_json(line))
        except Exception as exc:  # noqa: BLE001 - re-raise with line context
            raise ValueError(f"{path}:{lineno}: invalid sample: {exc}") from exc
    return samples


def freeze(
    samples: Sequence[GuardrailSample],
    path: str | Path,
) -> None:
    """Stage 6 — validate then write the dataset as deterministic JSONL.

    Asserts unique ids and runs the contamination guard before writing, then
    emits rows sorted by ``id`` so the output is reproducible across runs.
    """
    assert_unique_ids(samples)
    assert_no_contamination(samples)
    ordered = sorted(samples, key=lambda s: s.id)
    lines = [s.model_dump_json() for s in ordered]
    Path(path).write_text("\n".join(lines) + "\n")
    logger.info(
        "Froze %d guardrail samples to %s (%s)",
        len(ordered),
        path,
        split_counts(ordered),
    )
