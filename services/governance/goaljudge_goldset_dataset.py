"""Stage 5 golden dataset: Langfuse dataset CRUD + contamination firewall (L2).

Offline seam for ``goaljudge_goldset_v1`` — ensure the dataset exists, upsert
labeled items, and assert firewall invariants before freeze. No Langfuse SDK
import; inject a :class:`LangfuseDatasetClient` (real SDK wrapper in scripts,
:class:`InMemoryLangfuseDatasetClient` in tests).

Field contract: ``docs/research/goaljudge_stage5_goldset_spec.md`` §9.
NO ``langgraph`` / ``langchain`` imports (AGENTS.md invariant #4).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger("services.governance.goaljudge_goldset_dataset")

GOALJUDGE_GOLDSET_V1 = "goaljudge_goldset_v1"

# Mirror of ``components.schemas.GOAL_FAILURE_MODES`` — duplicated here so
# ``services/`` does not import ``components/``. Drift-guarded in
# ``tests/services/test_goaljudge_goldset_dataset.py``.
_ACTIVE_FAILURE_MODES: frozenset[str] = frozenset(
    {
        "missing-requested-information",
        "incomplete-synthesis",
        "fluent-evasion",
        "criteria-mismatch",
        "subtask-dropped",
        "partial-counted-as-full",
        "fabricated-progress",
        "raw-error-propagation",
        "tool-error-misread",
        "non-existent-file-error",
        "graceful-failure-honest",
        "impossible-task-reported",
        "impossible-task-unhandled",
        "premature-impossible",
        "right-answer-wrong-process",
        "goal-met-but-unsafe-wasteful",
    }
)


class GoldsetSplit(str, Enum):
    DEV = "dev"
    TEST = "test"


class GoldsetProvenance(str, Enum):
    PRODUCTION = "production"
    SYNTHETIC = "synthetic"


class GoldsetItem(BaseModel):
    """One labeled row for ``goaljudge_goldset_v1`` (spec §9)."""

    model_config = {"extra": "forbid"}

    item_id: str = Field(min_length=1)
    task_input: str
    final_answer: str
    evidence_digest: str = ""
    goal_met: bool
    graceful_failure: bool = False
    partial_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    failure_mode: str | None = None
    evidence_spans: list[str] = Field(default_factory=list)
    split: GoldsetSplit
    provenance: GoldsetProvenance
    source_trace_id: str | None = None

    @field_validator("failure_mode", mode="before")
    @classmethod
    def _normalize_failure_mode(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped or stripped.lower() in {"none", "null"}:
                return None
            if stripped not in _ACTIVE_FAILURE_MODES:
                raise ValueError(
                    f"unknown failure_mode {stripped!r}; expected one of "
                    f"{sorted(_ACTIVE_FAILURE_MODES)} or null"
                )
            return stripped
        raise ValueError(
            f"failure_mode must be a string or null, got {type(value).__name__}"
        )

    @model_validator(mode="after")
    def _firewall(self) -> GoldsetItem:
        if (
            self.provenance == GoldsetProvenance.SYNTHETIC
            and self.split != GoldsetSplit.DEV
        ):
            raise ValueError(
                "contamination firewall: provenance=synthetic requires split=dev"
            )
        return self


class DuplicateItemError(Exception):
    """Raised when upserting an ``item_id`` that already exists in the dataset."""


class FirewallError(Exception):
    """Raised when a batch violates the dev/test contamination firewall."""


@runtime_checkable
class LangfuseDatasetClient(Protocol):
    """Minimal Langfuse SDK surface for gold-set dataset CRUD."""

    def create_dataset(self, *, name: str, **kwargs: Any) -> dict[str, Any]: ...

    def create_dataset_item(
        self,
        *,
        dataset_name: str,
        input: dict[str, Any],
        id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]: ...


class InMemoryLangfuseDatasetClient:
    """Record/replay fake for L2 tests (mirrors SDK v4 dataset semantics)."""

    def __init__(self) -> None:
        self.datasets: set[str] = set()
        self.dataset_items: list[dict[str, Any]] = []

    def create_dataset(self, *, name: str, **kwargs: Any) -> dict[str, Any]:
        self.datasets.add(name)
        return {"name": name}

    def create_dataset_item(
        self,
        *,
        dataset_name: str,
        input: dict[str, Any],
        id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if dataset_name not in self.datasets:
            raise KeyError(f"dataset {dataset_name!r} not found")
        item = {
            "dataset_name": dataset_name,
            "input": input,
            "id": id,
            "metadata": metadata or {},
        }
        self.dataset_items.append(item)
        return item


class GoalJudgeGoldsetRepository:
    """Create and populate ``goaljudge_goldset_v1`` via an injected client."""

    def __init__(
        self,
        client: LangfuseDatasetClient,
        *,
        dataset_name: str = GOALJUDGE_GOLDSET_V1,
    ) -> None:
        self._client = client
        self._dataset_name = dataset_name
        self._item_ids: set[str] = set()

    @property
    def dataset_name(self) -> str:
        return self._dataset_name

    @property
    def item_ids(self) -> frozenset[str]:
        return frozenset(self._item_ids)

    def ensure_dataset(self) -> None:
        """Idempotent upsert of the Langfuse dataset."""
        self._client.create_dataset(name=self._dataset_name)
        logger.debug("ensure_dataset name=%s", self._dataset_name)

    def upsert_item(self, item: GoldsetItem) -> None:
        """Insert one labeled item (raises on duplicate ``item_id``)."""
        if item.item_id in self._item_ids:
            raise DuplicateItemError(f"duplicate item_id {item.item_id!r}")
        self.ensure_dataset()
        self._client.create_dataset_item(
            dataset_name=self._dataset_name,
            input=item.model_dump(mode="json"),
            id=item.item_id,
            metadata={
                "split": item.split.value,
                "provenance": item.provenance.value,
            },
        )
        self._item_ids.add(item.item_id)

    def upsert_many(self, items: Sequence[GoldsetItem]) -> int:
        """Insert a batch after firewall checks; returns count inserted."""
        assert_firewall_batch(items)
        for item in items:
            self.upsert_item(item)
        return len(items)


def assert_firewall_batch(items: Iterable[GoldsetItem]) -> None:
    """Assert assembly invariants from spec §9 / plan §8.2."""
    seen: set[str] = set()
    for item in items:
        if item.item_id in seen:
            raise FirewallError(f"duplicate item_id {item.item_id!r}")
        seen.add(item.item_id)
        if (
            item.provenance == GoldsetProvenance.SYNTHETIC
            and item.split == GoldsetSplit.TEST
        ):
            raise FirewallError(
                f"{item.item_id}: synthetic items must not be in the test split"
            )
    test_synthetic = [
        i.item_id
        for i in items
        if i.split == GoldsetSplit.TEST and i.provenance == GoldsetProvenance.SYNTHETIC
    ]
    if test_synthetic:
        raise FirewallError(
            f"test ∩ synthetic is non-empty: {test_synthetic}"
        )


def active_failure_modes() -> frozenset[str]:
    """Return the closed ``failure_mode`` vocabulary (for drift guards)."""
    return _ACTIVE_FAILURE_MODES
