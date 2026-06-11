"""Stage 5 golden dataset: Langfuse dataset CRUD + contamination firewall (L2).

Offline seam for ``goaljudge_goldset_v1`` — ensure the dataset exists, upsert
labeled items, and assert firewall invariants before freeze. No Langfuse SDK
import; inject a :class:`LangfuseDatasetClient` (real SDK wrapper in scripts,
:class:`InMemoryLangfuseDatasetClient` in tests).

Field contract: ``docs/research/goaljudge_stage5_goldset_spec.md`` §9.
NO ``langgraph`` / ``langchain`` imports (AGENTS.md invariant #4).
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
from collections.abc import Iterable, Mapping, Sequence
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
    FRESH_AUTHORED = "fresh-authored"


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


# ---------------------------------------------------------------------------
# Phase 3 — Cell-aware sourcing (L1 pure, no I/O, no LLM)
# ---------------------------------------------------------------------------
#
# Building blocks the Tier 3 full-sheet builder (``scripts/
# build_goaljudge_stage5_full_sheet.py``) composes. These live in
# ``services/governance/`` (not ``components/``) so the dependency direction
# stays *down*: scripts/ and tests/ may import from here, this module
# imports nothing above it. Pure functions: same input ⇒ same output.
#
# References:
#   * Stage 5 Tier 3 assembly plan §"Pipeline dimension space" — the eight
#     D5 clusters.
#   * Stage 5 Tier 3 assembly plan §"Stratification matrix" — D1/D5 floors.
#   * Stage 5 gold-set spec §4 — 40/30/20/10 stratum shares (D8).


# Eight-cluster D5 vocabulary. Locked here so the builder and manifest learn
# new clusters via this constant rather than by reading classifier source.
CELL_TOOL_CLUSTERS: frozenset[str] = frozenset(
    {
        "file-only",
        "shell-bound",
        "web-bound",
        "no-tool",
        "compose",
        "wrong-tool",
        "blocked-tool",
        "request_approval",
    }
)


# Per-dim cell floors from the plan's "Stratification matrix" — sized for
# binomial-CI per-cell estimates at 95 % CI (foundation doc §C.6).
D1_FLOORS: dict[str, int] = {"L0": 60, "L1": 100, "L2": 60}

D5_FLOORS: dict[str, int] = {
    "file-only": 25,
    "shell-bound": 30,
    "web-bound": 25,
    "no-tool": 15,
    "compose": 40,
    "wrong-tool": 20,
    "blocked-tool": 15,
    "request_approval": 10,
}


# Spec §4 stratum shares (D8). The allocator multiplies these by the total
# to produce per-stratum sizing targets without re-deriving the math.
STRATA_SHARES: dict[str, float] = {
    "representative": 0.40,
    "boundary": 0.30,
    "edge": 0.20,
    "impossible": 0.10,
}


# Tool-family mapping. The shell-bound family deliberately *absorbs* file_io
# so a shell+file flow is one cell (file_io is a common helper for
# shell-driven flows). Web is its own family; pure file is its own family;
# ``think_tool`` is metacognitive and does NOT count as an action tool.
_TOOL_FAMILIES: dict[str, str] = {
    "file_io": "file",
    "file_tools": "file",
    "shell": "shell",
    "web_search": "web",
}


def classify_tool_cluster(evidence: list[dict[str, Any]] | None) -> str:
    """Bucket a row's tool trajectory into one of :data:`CELL_TOOL_CLUSTERS`.

    Override semantics (first match wins):

      1. **request_approval** — any HITL call wins; structural cell.
      2. **blocked-tool** — any entry marked ``blocked=True`` wins (GJ-011
         pattern: shell metachar/allowlist denial leaves the row
         evidence-poor regardless of other calls).
      3. **wrong-tool** — any entry marked ``wrong_tool=True`` wins (GJ-012
         pattern: ``ls`` for a "show contents" subtask).
      4. **compose** — ≥ 2 distinct tool families (file, shell, web).
      5. **shell-bound / web-bound / file-only** — single dominant family.
      6. **no-tool** — empty list, None, or only think_tool / unknown names.

    Permissive on unknown tool names: an unrecognized name contributes
    nothing rather than raising, so a deprecated-tool replay doesn't crash
    the builder.
    """
    if not evidence:
        return "no-tool"

    families: set[str] = set()
    saw_request_approval = False
    saw_blocked = False
    saw_wrong_tool = False

    for entry in evidence:
        name = entry.get("tool_name", "")
        if entry.get("blocked"):
            saw_blocked = True
        if entry.get("wrong_tool"):
            saw_wrong_tool = True
        if name == "request_approval":
            saw_request_approval = True
            continue
        family = _TOOL_FAMILIES.get(name)
        if family:
            families.add(family)

    if saw_request_approval:
        return "request_approval"
    if saw_blocked:
        return "blocked-tool"
    if saw_wrong_tool:
        return "wrong-tool"

    # shell-bound absorbs the file family (file_io is a common helper for
    # shell-driven flows). compose fires only when web is mixed with
    # something else, or shell + file + web all appear.
    has_shell = "shell" in families
    has_web = "web" in families
    has_file = "file" in families

    if has_shell and has_web:
        return "compose"
    if has_file and has_web:
        return "compose"
    if has_shell:
        return "shell-bound"
    if has_web:
        return "web-bound"
    if has_file:
        return "file-only"
    return "no-tool"


# ---------------------------------------------------------------------------
# Corpus-trajectory → tool_calls_summary projection (sidecar loader helper)
# ---------------------------------------------------------------------------


def _safe_arg_keys(raw: Any) -> list[str]:
    """Extract argument keys from a stringified Python dict, safely.

    Langfuse trajectory spans emit ``input.details.args`` as a *stringified
    Python dict* (single-quoted), e.g.
    ``"{'path': '/x', 'operation': 'read'}"``. JSON parsers reject these;
    :func:`ast.literal_eval` accepts them and refuses arbitrary code by
    design. Any parse error falls back to ``[]`` so a malformed span never
    crashes the builder.
    """
    if isinstance(raw, dict):
        return sorted(raw.keys())
    if not isinstance(raw, str) or not raw:
        return []
    try:
        parsed = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return []
    if isinstance(parsed, dict):
        return sorted(parsed.keys())
    return []


def project_trajectory_tools(
    trajectory: list[dict[str, Any]] | None,
    *,
    last_n: int = 8,
) -> list[dict[str, Any]]:
    """Project a Langfuse trajectory into the shape :func:`classify_tool_cluster`
    consumes.

    Walks ``trajectory`` and keeps spans whose ``name == "tool.called"``;
    from each, reads ``input.details.tool`` (tool name) and
    ``input.details.args`` (stringified Python-dict args). Returns at most
    ``last_n`` entries (last-n cap matches
    ``components.goal_judge._summarize_evidence``'s 8-call ceiling — cluster
    classification cares about *families touched*, not call count).

    Output shape::

        [{"tool_name": "file_io", "args_keys": ["operation", "path"]}, ...]

    The dict shape is the contract consumed by :func:`classify_tool_cluster`;
    drift here breaks D5 classification downstream. The L1 test
    ``TestProjectTrajectoryTools`` round-trips a multi-family projection
    through the classifier to drift-guard the shape.

    No imports from ``components/``; pure stdlib (`ast`). Safe to call on
    arbitrary corpus snapshots — malformed args fall back to empty ``args_keys``
    rather than raising.
    """
    if not trajectory:
        return []

    projected: list[dict[str, Any]] = []
    for span in trajectory:
        if not isinstance(span, dict):
            continue
        if span.get("name") != "tool.called":
            continue
        details = ((span.get("input") or {}).get("details") or {})
        if not isinstance(details, dict):
            continue
        tool_name = details.get("tool", "")
        if not tool_name:
            continue
        projected.append(
            {
                "tool_name": tool_name,
                "args_keys": _safe_arg_keys(details.get("args")),
            }
        )

    if last_n > 0 and len(projected) > last_n:
        projected = projected[-last_n:]
    return projected


# ---------------------------------------------------------------------------
# Phase 4 — FreshTask schema (cell-targeted authoring) + drift-guard helpers
# ---------------------------------------------------------------------------
#
# FreshTask is a sibling of GoldsetItem: same module, same firewall-aware
# home, same "extra=forbid" discipline. It is the row shape for
# ``tests/fixtures/goaljudge/fresh_test_tasks.py`` (the test-split backbone
# of the gold set).
#
# Vocabulary alignment:
#   * ``stratum``                ← keys of ``STRATA_SHARES``
#   * ``expected_tool_cluster``  ← members of ``CELL_TOOL_CLUSTERS``
#   * ``expected_failure_mode``  ← members of ``_ACTIVE_FAILURE_MODES`` ∪ {None}
#   * ``expected_planning_depth``← keys of ``D1_FLOORS``
#   * ``source_benchmark_schema``← members of ``FRESH_TASK_BENCHMARK_SCHEMAS``
#
# The locked vocabularies are validated at construction time; downstream
# allocators / classifiers receive guaranteed-in-set values.


FRESH_TASK_BENCHMARK_SCHEMAS: frozenset[str] = frozenset(
    {
        # Phase 4 plan §8 — reuse schemas, NOT items.
        "tau-bench",
        "the-agent-company-checkpoint",
        "webarena-impossible",
        "agentboard-subgoal",
        "novel",  # author-original; ``novel`` is the explicit signal that the
                  # task was hand-authored from scratch with no upstream schema
    }
)


# Domain vocabulary mirrors the goldset spec §4 "domain" enumeration. Kept
# small and additive: a new domain requires updating this set AND the
# Phase 4 fresh_task_authoring_guide.md (drift forces a code review).
_FRESH_TASK_DOMAINS: frozenset[str] = frozenset(
    {
        "file_io",
        "math",
        "web",
        "shell",
        "composite",
        "knowledge",
    }
)


class FreshTaskValidationError(Exception):
    """Raised by :func:`validate_fresh_task_set` when the corpus violates a
    drift-guard invariant (Jaccard, router-agreement, duplicate id, etc.).

    Distinct from ``FirewallError`` (which guards dev/test contamination):
    this is the Phase 4 authoring contract, not the Phase 6 freeze contract.
    """


class FreshTask(BaseModel):
    """One cell-targeted fresh-authored task (Phase 4 plan §"FreshTask schema").

    A FreshTask is an author's *intent* for a (D1, D5-cluster, stratum)
    cell — including the expected failure mode (D7) when applicable.
    The validate_fresh_task_set drift-guard later confirms the author's
    expected_planning_depth agrees with what ``components.router.select_planning_depth``
    would route the prompt to. Drift = test failure.
    """

    model_config = {"extra": "forbid"}

    id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    stratum: str
    domain: str
    expected_planning_depth: str
    expected_tool_cluster: str
    expected_failure_mode: str | None = None
    source_benchmark_schema: str

    @field_validator("stratum")
    @classmethod
    def _check_stratum(cls, value: str) -> str:
        if value not in STRATA_SHARES:
            raise ValueError(
                f"unknown stratum {value!r}; expected one of "
                f"{sorted(STRATA_SHARES)}"
            )
        return value

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, value: str) -> str:
        if value not in _FRESH_TASK_DOMAINS:
            raise ValueError(
                f"unknown domain {value!r}; expected one of "
                f"{sorted(_FRESH_TASK_DOMAINS)}"
            )
        return value

    @field_validator("expected_planning_depth")
    @classmethod
    def _check_planning_depth(cls, value: str) -> str:
        if value not in D1_FLOORS:
            raise ValueError(
                f"unknown expected_planning_depth {value!r}; expected one of "
                f"{sorted(D1_FLOORS)}"
            )
        return value

    @field_validator("expected_tool_cluster")
    @classmethod
    def _check_tool_cluster(cls, value: str) -> str:
        if value not in CELL_TOOL_CLUSTERS:
            raise ValueError(
                f"unknown expected_tool_cluster {value!r}; expected one of "
                f"{sorted(CELL_TOOL_CLUSTERS)}"
            )
        return value

    @field_validator("expected_failure_mode", mode="before")
    @classmethod
    def _check_failure_mode(cls, value: object) -> str | None:
        # Mirror GoldsetItem._normalize_failure_mode for consistency: same
        # rules, same vocabulary source. A future enlargement of
        # GOAL_FAILURE_MODES propagates here automatically via
        # _ACTIVE_FAILURE_MODES.
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped or stripped.lower() in {"none", "null"}:
                return None
            if stripped not in _ACTIVE_FAILURE_MODES:
                raise ValueError(
                    f"unknown expected_failure_mode {stripped!r}; expected one of "
                    f"{sorted(_ACTIVE_FAILURE_MODES)} or null"
                )
            return stripped
        raise ValueError(
            f"expected_failure_mode must be a string or null, "
            f"got {type(value).__name__}"
        )

    @field_validator("source_benchmark_schema")
    @classmethod
    def _check_benchmark_schema(cls, value: str) -> str:
        if value not in FRESH_TASK_BENCHMARK_SCHEMAS:
            raise ValueError(
                f"unknown source_benchmark_schema {value!r}; expected one of "
                f"{sorted(FRESH_TASK_BENCHMARK_SCHEMAS)}"
            )
        return value


def jaccard_similarity(a: str, b: str) -> float:
    """Token-set Jaccard similarity between two strings, case-insensitive.

    Convention: ``|A ∩ B| / |A ∪ B|`` where ``A``, ``B`` are the
    whitespace-split, lowercased token sets. Returns ``0.0`` when both
    sets are empty (rather than raising) so the validator can compare
    against an empty registry without a corner-case crash.

    Whitespace-split is intentional: the Phase 4 contamination guard is
    surface-form, not semantic. A semantic embedding-based similarity
    would be its own Phase 6 enhancement; this is a fast, dependency-free
    drift-guard that catches author copy-paste from the registry.
    """
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    union = tokens_a | tokens_b
    if not union:
        return 0.0
    intersection = tokens_a & tokens_b
    return len(intersection) / len(union)


def validate_fresh_task_set(
    tasks: list[FreshTask],
    registry_prompts: list[str],
    router_fn: Any,
    *,
    jaccard_threshold: float = 0.5,
) -> None:
    """Drift-guard the Phase 4 fresh-task corpus.

    Raises :class:`FreshTaskValidationError` on any of:

      * **Duplicate id** — Phase 6 freeze would collide; reject early.
      * **Router disagreement** — ``router_fn(task.prompt, 0)`` ≠
        ``task.expected_planning_depth``. Without this guard, fresh tasks
        could silently land in the wrong D1 cell of the gap report.
      * **Registry contamination** — Jaccard(task.prompt, registry_prompt)
        ≥ ``jaccard_threshold`` for any registry prompt. Default
        threshold is 0.5 (Phase 4 plan §"drift-guards"); the threshold is
        configurable so a future Phase 4 iteration can tighten if 0.5
        admits too much paraphrase.

    ``router_fn`` matches the ``components.router.select_planning_depth``
    signature: ``(*, task_input: str, task_tool_results_count: int) ->
    tuple[str, str]`` (depth, reason). Injection is intentional — the
    services/governance L1 layer does not import ``components`` (AGENTS.md
    invariant); scripts/tests wire the real router in.
    """
    # ── Failure-paths-first order matches the test class' order ──
    # 1. Duplicate id (the cheapest check; constant-time per task).
    seen_ids: set[str] = set()
    for task in tasks:
        if task.id in seen_ids:
            raise FreshTaskValidationError(
                f"duplicate fresh-task id {task.id!r}"
            )
        seen_ids.add(task.id)

    # 2. Router agreement (calls the injected router once per task).
    for task in tasks:
        predicted_depth, _reason = router_fn(
            task_input=task.prompt,
            task_tool_results_count=0,
        )
        if predicted_depth != task.expected_planning_depth:
            raise FreshTaskValidationError(
                f"router/expected_planning_depth disagree on {task.id!r}: "
                f"router={predicted_depth!r} expected={task.expected_planning_depth!r}"
            )

    # 3. Registry contamination (O(|tasks| × |registry|)).
    for task in tasks:
        for registry_prompt in registry_prompts:
            score = jaccard_similarity(task.prompt, registry_prompt)
            if score >= jaccard_threshold:
                raise FreshTaskValidationError(
                    f"jaccard contamination on {task.id!r}: "
                    f"score={score:.3f} ≥ threshold={jaccard_threshold} "
                    f"vs registry prompt"
                )
    # Silent success.
    return None


class CoverageReport(BaseModel):
    """Per-dimension gap report consumed by the Tier 3 builder + Phase 4
    authoring brief.

    ``d1_gaps`` and ``d5_gaps`` are positive integers ≥ 0; zero means the
    floor is met for that cell. The report serializes to a markdown table
    via :meth:`to_markdown` because the authoring brief is read by humans.
    """

    model_config = {"extra": "forbid"}

    total_items: int = 0
    d1_gaps: dict[str, int] = Field(default_factory=dict)
    d5_gaps: dict[str, int] = Field(default_factory=dict)

    def to_markdown(self) -> str:
        """Render the gap report as a human-readable markdown table."""
        lines: list[str] = []
        lines.append("# Stage 5 Tier 3 cell-coverage gap report")
        lines.append("")
        lines.append(f"_total items considered: **{self.total_items}**_")
        lines.append("")
        lines.append("## D1 — planning_depth")
        lines.append("| depth | floor | gap |")
        lines.append("|---|---|---|")
        for depth in ("L0", "L1", "L2"):
            floor = D1_FLOORS.get(depth, 0)
            gap = self.d1_gaps.get(depth, 0)
            lines.append(f"| `{depth}` | {floor} | {gap} |")
        lines.append("")
        lines.append("## D5 — tool_cluster")
        lines.append("| cluster | floor | gap |")
        lines.append("|---|---|---|")
        for cluster in sorted(CELL_TOOL_CLUSTERS):
            floor = D5_FLOORS.get(cluster, 0)
            gap = self.d5_gaps.get(cluster, 0)
            lines.append(f"| `{cluster}` | {floor} | {gap} |")
        return "\n".join(lines) + "\n"


def compute_cell_coverage(rows: Iterable[dict[str, Any]]) -> CoverageReport:
    """Compute per-(D1, D5) gap counts against the locked floors.

    A row is any mapping with ``planning_depth`` ∈ {"L0", "L1", "L2"} and
    ``tool_cluster`` ∈ :data:`CELL_TOOL_CLUSTERS`. Rows with values outside
    the closed vocabularies contribute to nothing — they don't crash the
    report, but they also don't fill any cell. This matches the
    classifier's permissive failure mode.

    Does **not** look at D7 ``failure_mode``: that's a separate per-code
    count enforced at assemble time (Phase 6). Mixing it in would conflate
    sourcing (Phase 3) with labeling (Phase 5).
    """
    rows = list(rows)
    d1_counts: dict[str, int] = {d: 0 for d in D1_FLOORS}
    d5_counts: dict[str, int] = {c: 0 for c in D5_FLOORS}
    for row in rows:
        depth = str(row.get("planning_depth", ""))
        if depth in d1_counts:
            d1_counts[depth] += 1
        cluster = str(row.get("tool_cluster", ""))
        if cluster in d5_counts:
            d5_counts[cluster] += 1
    d1_gaps = {
        depth: max(0, floor - d1_counts.get(depth, 0))
        for depth, floor in D1_FLOORS.items()
    }
    d5_gaps = {
        cluster: max(0, floor - d5_counts.get(cluster, 0))
        for cluster, floor in D5_FLOORS.items()
    }
    return CoverageReport(
        total_items=len(rows),
        d1_gaps=d1_gaps,
        d5_gaps=d5_gaps,
    )


def evaluate_goldset_post_alpha_coverage(
    rows: Iterable[Mapping[str, Any]],
) -> CoverageReport:
    """Phase 5 labeling-quality gate (vs. Phase 3 sourcing-quality gate).

    Filters ``rows`` down to those whose ``adjudicated_goal_met`` is
    canonically ``"false"`` and then defers to :func:`compute_cell_coverage`
    for the per-(D1, D5) gap math. The rationale (Tier 3 plan §"Phase 5"
    step 6):

    Stage 6's primary metric class is the failure modes. A sourcing pass
    in Phase 3 can satisfy the per-cell floors on the COMBINED set yet
    leave a cell with no labeled failures once adjudication finishes —
    a successful labeling collapse. This gate catches that collapse
    *before* the manifest is hashed and frozen at Phase 6.

    Behavior contract:

    * Rows with ``adjudicated_goal_met`` ∉ {"false"} (after
      :func:`normalize_bool_label`) are **dropped** before scoring.
      That includes blanks (which mean 'agreement-row implicit; not
      explicitly graded false'), ``"true"``, and any other string.
    * The dropped rows do **not** contribute to ``total_items`` —
      ``total_items`` reflects the failure subset, which is what the
      Stage 6 calibration corpus actually consumes.
    * Empty input or all-true input returns a report whose every gap
      equals the corresponding floor. The gate is then a *failed*
      gate (not silent), which is the desired surfacing.
    """
    # Local import to keep iaa.py at L1 (it imports nothing from this
    # module today; if it ever does, that's the place to break the cycle).
    from services.governance.iaa import normalize_bool_label

    filtered: list[Mapping[str, Any]] = []
    for row in rows:
        adjudicated = normalize_bool_label(str(row.get("adjudicated_goal_met", "")))
        if adjudicated == "false":
            filtered.append(row)
    return compute_cell_coverage(filtered)


def compute_test_split_hash(items: Iterable[GoldsetItem]) -> str:
    """SHA-256 over the canonical-JSON of the sorted-by-item_id test rows.

    Stable across dict ordering (``sort_keys=True``) and Python re-runs;
    sensitive to **any** field change on **any** test-split row. Stage 6
    must recompute this and diff against the manifest before every run —
    a hash mismatch means the test split was tuned on.

    Spec/plan references:

    - Stage 5 spec §9 — "the test split's content hash is recorded and frozen".
    - Stage 5 master plan §8.2 — "hash-freeze + per-run hash diff".
    - Tier 3 assembly plan Phase 2/6 — this is the helper Phase 6 calls and
      that the manifest records as ``test_split_sha256``.

    Dev-split items in the input iterable are **ignored** — the hash is over
    test rows only, so a dev-split churn does not break Stage 6's diff.
    """
    test_items = [i for i in items if i.split == GoldsetSplit.TEST]
    test_items.sort(key=lambda item: item.item_id)
    payload = [item.model_dump(mode="json", exclude_none=False) for item in test_items]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Phase 6 — Assemble, freeze, manifest
# ---------------------------------------------------------------------------
#
# Three helpers consumed by ``scripts/assemble_goaljudge_goldset.py``:
#
#   row_to_goldset_item(row)          — CSV row → validated GoldsetItem
#   assert_assembly_invariants(...)   — integration-boundary safety net
#   build_goldset_manifest(items, …)  — produces the v1 manifest dict
#
# All pure functions. No Langfuse SDK, no logging side effects, no I/O.


class AssemblyInvariantError(Exception):
    """Raised by :func:`assert_assembly_invariants` when an integration-
    boundary check fails on a candidate gold-set batch.

    Distinct from :class:`FirewallError` so the assembly script's error
    narrative can distinguish 'data shape' violations (firewall) from
    'data distribution' violations (cell-coverage / minimum-share).
    """


# A2 corrupt-success codes per the Stage 4 rubric: these collectively
# need ≥ 40 occurrences for binomial-CI per-code estimates at 95% CI.
_A2_FAILURE_MODE_CODES: frozenset[str] = frozenset(
    {
        "fabricated-progress",
        "fluent-evasion",
        "partial-counted-as-full",
        "right-answer-wrong-process",
        "goal-met-but-unsafe-wasteful",
    }
)


def row_to_goldset_item(row: Mapping[str, str]) -> GoldsetItem:
    """Convert one sheet row (FIELDS contract) into a validated :class:`GoldsetItem`.

    The function:

    1. Normalizes ``adjudicated_goal_met`` via
       :func:`services.governance.iaa.normalize_bool_label` — so ``Y``,
       ``1``, ``True`` all collapse to ``True``.
    2. Maps the seven literal sheet columns to the seven GoldsetItem
       fields (``task`` → ``task_input``, ``claim`` → ``final_answer``,
       and so on).
    3. Validates the result through the GoldsetItem model (pydantic
       enforces ``synthetic ⇒ dev`` and the closed
       ``failure_mode`` vocabulary).

    Failure modes:

    * Blank ``item_id`` ⇒ ``ValueError`` (pydantic min_length).
    * Un-normalizable ``adjudicated_goal_met`` ⇒ ``ValueError`` (we
      reject early so the user gets a clear message instead of a
      pydantic boolean-coercion failure).
    * Unknown ``adjudicated_failure_mode`` ⇒ ``ValueError`` (GoldsetItem
      validator).
    * Synthetic provenance in test split ⇒ ``ValueError`` (firewall).
    * Blank ``task`` ⇒ ``ValueError``.
    """
    # Local import to keep the dependency direction Horizontal→Horizontal
    # within services/governance/ (iaa.py has no upward dependencies).
    from services.governance.iaa import normalize_bool_label

    task = str(row.get("task", "")).strip()
    if not task:
        raise ValueError(
            f"row {row.get('item_id', '<?>')!r}: task is blank"
        )

    raw_goal_met = str(row.get("adjudicated_goal_met", "")).strip()
    normalized_goal_met = normalize_bool_label(raw_goal_met)
    if normalized_goal_met not in {"true", "false"}:
        raise ValueError(
            f"row {row.get('item_id', '<?>')!r}: "
            f"adjudicated_goal_met={raw_goal_met!r} is not a recognized "
            "truth value (expected one of: true/false/Y/N/yes/no/1/0)."
        )
    goal_met = normalized_goal_met == "true"

    # Graceful-failure is the same normalization story.
    raw_graceful = str(row.get("adjudicated_graceful_failure", row.get("r1_graceful_failure", ""))).strip()
    normalized_graceful = normalize_bool_label(raw_graceful)
    graceful_failure = normalized_graceful == "true"

    # Partial fraction — float in [0, 1]. Fallback to 1.0 / 0.0 if blank.
    raw_partial = str(row.get("adjudicated_partial_fraction", row.get("r1_partial_fraction", ""))).strip()
    if raw_partial:
        try:
            partial_fraction = float(raw_partial)
        except ValueError as exc:
            raise ValueError(
                f"row {row.get('item_id', '<?>')!r}: "
                f"partial_fraction={raw_partial!r} is not a valid float"
            ) from exc
    else:
        partial_fraction = 1.0 if goal_met else 0.0

    # Failure mode is None when blank; GoldsetItem validator rejects
    # unknown codes downstream.
    raw_failure_mode = str(row.get("adjudicated_failure_mode", "")).strip()
    failure_mode = raw_failure_mode or None

    item = GoldsetItem(
        item_id=str(row.get("item_id", "")).strip(),
        task_input=task,
        final_answer=str(row.get("claim", "")).strip(),
        evidence_digest=str(row.get("evidence_summary", "")).strip(),
        goal_met=goal_met,
        graceful_failure=graceful_failure,
        partial_fraction=partial_fraction,
        failure_mode=failure_mode,
        evidence_spans=[],
        split=GoldsetSplit(str(row.get("split", "dev")).strip().lower()),
        provenance=GoldsetProvenance(
            str(row.get("provenance", "production")).strip().lower()
        ),
        source_trace_id=str(row.get("trace_id", "")).strip() or None,
    )
    return item


def assert_assembly_invariants(
    items: Sequence[GoldsetItem],
    *,
    planning_depth_by_id: Mapping[str, str] | None = None,
    tool_cluster_by_id: Mapping[str, str] | None = None,
    d1_floors: Mapping[str, int] | None = None,
    d5_floors: Mapping[str, int] | None = None,
    min_goal_met_false_share: float = 0.60,
) -> None:
    """Integration-boundary safety net for Phase 6 assembly.

    Reuses :func:`assert_firewall_batch` for duplicate-id and
    synthetic-in-test checks, then layers the *distribution* checks
    Phase 6 adds:

    * ``goal_met=false`` ≥ ``min_goal_met_false_share`` of total items
      (default 60 % per spec §4).
    * Per-D1 (planning_depth) cell counts ≥ ``d1_floors`` (default
      :data:`D1_FLOORS`).
    * Per-D5 (tool_cluster) cell counts ≥ ``d5_floors`` (default
      :data:`D5_FLOORS`).

    The two ``*_by_id`` maps carry the *sheet-side* dimension labels
    (which live on the CSV, not on the GoldsetItem). The script passes
    them in keyed by ``item_id``; tests can override floors so the
    invariant suite is exercisable on small fixtures.

    On any violation raises :class:`AssemblyInvariantError` with a
    descriptive, operator-actionable message.
    """
    # Layer 1: reuse firewall semantics. Re-wrap FirewallError so the
    # caller can catch a single error type for *all* assembly violations.
    try:
        assert_firewall_batch(items)
    except FirewallError as exc:
        raise AssemblyInvariantError(str(exc)) from exc

    if not items:
        # Empty input is a programming bug at the call site, not a
        # silent-pass: raise so the operator notices.
        raise AssemblyInvariantError(
            "no items provided to assert_assembly_invariants"
        )

    # Layer 2: goal_met=false share.
    total = len(items)
    false_count = sum(1 for i in items if not i.goal_met)
    share = false_count / total
    if share < min_goal_met_false_share:
        raise AssemblyInvariantError(
            f"goal_met=false share {share:.3f} below floor "
            f"{min_goal_met_false_share:.2f} "
            f"({false_count}/{total} items false)"
        )

    # Layer 3 + 4: D1 / D5 cell-coverage if dimension maps are provided.
    # If neither map is provided, we skip these checks — the caller is
    # explicitly opting out (e.g., a smoke run without sheet metadata).
    if planning_depth_by_id is not None:
        floors = dict(d1_floors) if d1_floors is not None else D1_FLOORS
        counts: dict[str, int] = {d: 0 for d in floors}
        for item in items:
            depth = planning_depth_by_id.get(item.item_id, "")
            if depth in counts:
                counts[depth] += 1
        for depth, floor in floors.items():
            if counts[depth] < floor:
                raise AssemblyInvariantError(
                    f"planning_depth floor unmet: cell={depth!r} "
                    f"count={counts[depth]} floor={floor}"
                )

    if tool_cluster_by_id is not None:
        floors = dict(d5_floors) if d5_floors is not None else D5_FLOORS
        counts = {c: 0 for c in floors}
        for item in items:
            cluster = tool_cluster_by_id.get(item.item_id, "")
            if cluster in counts:
                counts[cluster] += 1
        for cluster, floor in floors.items():
            if counts[cluster] < floor:
                raise AssemblyInvariantError(
                    f"tool_cluster floor unmet: cell={cluster!r} "
                    f"count={counts[cluster]} floor={floor}"
                )


def build_goldset_manifest(
    items: Sequence[GoldsetItem],
    *,
    test_split_sha256: str,
    rubric_version: str,
    frozen_at: str,
    stratum_by_id: Mapping[str, str] | None = None,
    planning_depth_by_id: Mapping[str, str] | None = None,
    tool_cluster_by_id: Mapping[str, str] | None = None,
    observed_distributions: Mapping[str, Mapping[str, int]] | None = None,
    dataset_name: str = GOALJUDGE_GOLDSET_V1,
    provisional: bool = False,
    floor_gap_summary: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Assemble the v1 manifest dict per Phase 6 / Tier 3 plan spec.

    The manifest is the single source of truth Stage 6 diffs against
    every run. Stage 6 reads ``test_split_sha256`` to detect tuning,
    ``rubric_version`` to gate against rubric-version mismatch, and the
    per-dim distribution dicts to surface drift on the calibration plot.

    Required inputs:

    * ``test_split_sha256`` — non-blank; computed via :func:`compute_test_split_hash`.
    * ``rubric_version`` — non-blank; the locked rubric version string.
    * ``frozen_at`` — non-blank ISO-8601 timestamp.

    Optional inputs (default to empty dicts):

    * ``stratum_by_id`` / ``planning_depth_by_id`` / ``tool_cluster_by_id`` —
      sheet-side label maps; when provided produce the corresponding
      distribution dict; when absent the dict is ``{}``.
    * ``observed_distributions`` — three informational dicts
      (``routing_reason_distribution_observed``,
      ``model_tier_distribution_observed``,
      ``cost_fraction_bins_observed``); always echoed back into the
      manifest with stable keys so Stage 6's diff has a stable shape.
    * ``dataset_name`` — defaults to ``"goaljudge_goldset_v1"``.

    Pure: no I/O, no side effects. Caller writes the resulting dict to
    JSON.
    """
    if not test_split_sha256:
        raise ValueError("test_split_sha256 is required and must be non-empty")
    if not rubric_version:
        raise ValueError("rubric_version is required and must be non-empty")
    if not frozen_at:
        raise ValueError("frozen_at is required and must be non-empty")
    gap_summary: dict[str, int] = dict(floor_gap_summary or {})
    if not provisional and gap_summary:
        raise ValueError(
            "provisional=False requires floor_gap_summary={} — refusing to ship "
            f"a v1 manifest with unmet floors: {sorted(gap_summary)}"
        )

    total_items = len(items)
    dev_count = sum(1 for i in items if i.split == GoldsetSplit.DEV)
    test_count = sum(1 for i in items if i.split == GoldsetSplit.TEST)
    false_count = sum(1 for i in items if not i.goal_met)
    goal_met_false_share = (false_count / total_items) if total_items else 0.0

    # Distribution dicts.
    failure_mode_distribution: dict[str, int] = {}
    for item in items:
        if item.failure_mode:
            failure_mode_distribution[item.failure_mode] = (
                failure_mode_distribution.get(item.failure_mode, 0) + 1
            )

    def _dist(by_id: Mapping[str, str] | None) -> dict[str, int]:
        if not by_id:
            return {}
        out: dict[str, int] = {}
        for item in items:
            label = by_id.get(item.item_id, "")
            if not label:
                continue
            out[label] = out.get(label, 0) + 1
        return out

    stratum_distribution = _dist(stratum_by_id)
    planning_depth_distribution = _dist(planning_depth_by_id)
    tool_cluster_distribution = _dist(tool_cluster_by_id)

    observed = observed_distributions or {}
    routing_reason_distribution_observed = dict(
        observed.get("routing_reason_distribution_observed", {})
    )
    model_tier_distribution_observed = dict(
        observed.get("model_tier_distribution_observed", {})
    )
    cost_fraction_bins_observed = dict(
        observed.get("cost_fraction_bins_observed", {})
    )

    return {
        "dataset_name": dataset_name,
        "total_items": total_items,
        "dev_count": dev_count,
        "test_count": test_count,
        "test_split_sha256": test_split_sha256,
        "rubric_version": rubric_version,
        "frozen_at": frozen_at,
        "stratum_distribution": stratum_distribution,
        "planning_depth_distribution": planning_depth_distribution,
        "tool_cluster_distribution": tool_cluster_distribution,
        "failure_mode_distribution": failure_mode_distribution,
        "routing_reason_distribution_observed":
            routing_reason_distribution_observed,
        "model_tier_distribution_observed":
            model_tier_distribution_observed,
        "cost_fraction_bins_observed":
            cost_fraction_bins_observed,
        "goal_met_false_share": goal_met_false_share,
        "provisional": bool(provisional),
        "floor_gap_summary": gap_summary,
    }


_V1_GATE_REQUIRED_KEYS: tuple[str, ...] = (
    "dataset_name",
    "test_split_sha256",
    "rubric_version",
    "frozen_at",
    "total_items",
    "test_count",
    "provisional",
    "floor_gap_summary",
)


def gate_goldset_v1_floors(manifest: Mapping[str, Any]) -> None:
    """Stage 6 entry-point gate. Raises ``AssemblyInvariantError`` unless
    ``manifest`` is a production-freeze (v1) artifact with every floor met.

    Fails-closed on:

    * Missing any of the v1-required keys.
    * Blank ``test_split_sha256`` (the hash IS the freeze).
    * ``provisional=True`` (the manifest is an interim v0.9 / smoke shape).
    * Non-empty ``floor_gap_summary`` (some D1/D5 cell is still under
      floor).

    Idempotent. Does not mutate ``manifest``. Returns ``None`` on success
    — callers should treat the absence of an exception as the pass signal.
    """
    missing = [k for k in _V1_GATE_REQUIRED_KEYS if k not in manifest]
    if missing:
        raise AssemblyInvariantError(
            f"manifest missing required v1 keys: {missing}"
        )
    sha = str(manifest.get("test_split_sha256", "")).strip()
    if not sha:
        raise AssemblyInvariantError(
            "manifest test_split_sha256 is blank — refusing to gate v1"
        )
    if manifest.get("provisional"):
        raise AssemblyInvariantError(
            "manifest is provisional (v0.9) — Stage 6 v1 floors not yet met. "
            f"Gap summary: {dict(manifest.get('floor_gap_summary') or {})}"
        )
    gaps = dict(manifest.get("floor_gap_summary") or {})
    if gaps:
        raise AssemblyInvariantError(
            f"manifest claims non-provisional but has unmet floor gaps: "
            f"{sorted(gaps)}"
        )
