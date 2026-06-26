"""Deterministic, reference-free answer verifiers — the authoritative half of
the GoalJudge correctness cascade.

Why this exists
---------------
The GoalJudge LLM rubric grades *process-presence* ("did each subtask run and
get reported"), never *result-correctness*. The L2/L3 seed measurement caught it
scoring a REVERSED topological sort ``goal_met=1.0`` ("respects all
dependencies") while failing a CORRECT one for not echoing the order. A judge
with no ground truth scores confident-but-wrong output highly on plausibility
(documented LLM-as-judge failure mode); a programmatic check never hallucinates.

So for tasks with a *checkable* answer, a deterministic verifier owns the
correctness verdict and the LLM judge is the fallback for everything else. This
follows the priority-cascade pattern (deterministic first, LLM on abstain) —
never averaging a deterministic match with a judge score (the calibration gap).

Contract
--------
``verify_answer(task_input, final_answer, evidence) -> bool | None``
  - ``True``  — the task has a checkable shape AND the produced result is correct.
  - ``False`` — checkable shape AND the result is observably wrong.
  - ``None``  — no checkable shape, or the inputs cannot be parsed confidently.
    **Abstain, don't guess**: a parse miss MUST defer to the LLM judge so the
    verifier can never introduce a false fail.

Layering: a PURE Vertical-Component unit (FOUR_LAYER_ARCHITECTURE deep-agent
mapping). No LLM, no I/O, no logging; imports only stdlib. It does not import
``components.schemas`` — it deals in primitives, leaving verdict shaping to the
caller (``GoalJudge``).
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["verify_answer"]

# Currently the one checkable shape exercised by the L2/L3 corpus where the judge
# demonstrably mis-graded correctness (both missed-failures are topological
# sorts). New shapes (count, arithmetic, specific-value) slot in as additional
# branches in ``verify_answer`` with the same abstain-on-doubt rule; we do not
# build them speculatively for shapes no failing case needs.

# Dependency edges may be written with an ASCII ``->`` or a Unicode ``→`` arrow;
# normalise both to ``->`` before parsing.
_ARROW_RE = re.compile(r"\s*(?:->|→|⟶|⇒|⇨)\s*")
_EDGE_RE = re.compile(r"\b([A-Za-z][\w-]*)\s*->\s*([A-Za-z][\w-]*)\b")


def verify_answer(
    task_input: str,
    final_answer: str,
    evidence: list[dict[str, Any]] | None = None,
) -> bool | None:
    """Return the correctness verdict for a checkable answer, else ``None``.

    Dispatches on the task's answer shape. Each handler RECOMPUTES the expected
    answer from the source data in ``evidence`` (reference-free) and checks the
    final answer asserts it; an unrecognised shape or any parse doubt yields
    ``None`` so the LLM judge takes over. Shapes are ordered most-specific first.
    """
    text = task_input.lower()
    # The verifier validates the REPORTED result. When the task ALSO requires a
    # side effect it cannot observe — writing the answer to a specific file path
    # — a correct number with a wrong/absent write is only PARTIAL (the human
    # raters graded exactly this). We cannot confirm the write target from the
    # final answer, so we abstain and let the LLM judge weigh the side effect.
    # (Topological sort is exempt: its "report the order" has no write target.)
    if not _is_topological_sort_task(task_input) and _requires_file_write(text):
        return None

    if _is_topological_sort_task(task_input):
        return _verify_topological_sort(task_input, final_answer, evidence)
    if "status is 'paid'" in text or ("paid" in text and "subtotal" in text):
        return _verify_paid_subtotal(final_answer, evidence)
    if "region" in text and "how many orders" in text:
        return _verify_region_counts(final_answer, evidence)
    if "error" in text and "most errors" in text and "hour" in text:
        return _verify_peak_error_hour(final_answer, evidence)
    if "growth rate" in text and "quarter" in text:
        return _verify_growth_rates(final_answer, evidence)
    if "slot" in text and ("four of the five" in text or "at least four" in text):
        return _verify_earliest_slot(final_answer, evidence)
    return None


def _requires_file_write(task_text: str) -> bool:
    """True when the task demands the result be written to a named file path."""
    return bool(
        re.search(r"\bwrit(?:e|ing|ten)\b[^.]*?(?:to\s+)?/\S+\.\w+", task_text)
        or re.search(r"\bwrit(?:e|ing|ten)\b[^.]*\b\w+\.(?:txt|json|csv)\b", task_text)
    )


# ── shared parsing helpers ──────────────────────────────────────────


def _evidence_text(evidence: list[dict[str, Any]] | None) -> str:
    """Concatenate all string tool outputs — the agent's observed source data."""
    if not evidence:
        return ""
    return "\n".join(
        str(e.get("tool_output", "")) for e in evidence if isinstance(e.get("tool_output"), str)
    )


def _numbers_in(text: str) -> list[float]:
    """Every number in ``text`` (ints/decimals), commas in thousands stripped."""
    return [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]


def _answer_asserts_value(final_answer: str, value: float, *, wrong: set[float]) -> bool | None:
    """True if the answer asserts ``value`` and asserts none of ``wrong``.

    Abstains (``None``) if the answer states no usable number at all — we cannot
    confirm correctness without the agent actually reporting a figure.
    """
    present = set(_numbers_in(final_answer))
    if not present:
        return None
    if value in present and not (wrong & present):
        return True
    if (wrong & present) and value not in present:
        return False
    # Both the right value and a wrong value appear (or neither): ambiguous → defer.
    if value in present and (wrong & present):
        return None
    return False  # the value is absent and no specific wrong value either → not asserted


# ── 07: sum of 'paid' invoice amounts ───────────────────────────────


def _verify_paid_subtotal(final_answer: str, evidence: list[dict[str, Any]] | None) -> bool | None:
    src = _evidence_text(evidence)
    # Each invoice block has an ``amount: N`` and a ``status: X`` line.
    amounts = [int(m.group(1)) for m in re.finditer(r"amount:\s*(\d+)", src, re.I)]
    statuses = [m.group(1).lower() for m in re.finditer(r"status:\s*(\w+)", src, re.I)]
    if not amounts or len(amounts) != len(statuses):
        return None
    paid_total = float(sum(a for a, s in zip(amounts, statuses) if s == "paid"))
    all_total = float(sum(amounts))
    return _answer_asserts_value(final_answer, paid_total, wrong={all_total})


# ── 08: orders-per-region counts ────────────────────────────────────


def _verify_region_counts(final_answer: str, evidence: list[dict[str, Any]] | None) -> bool | None:
    src = _evidence_text(evidence)
    # customer_id,region rows and order_id,customer_id rows (skip the headers).
    cust_region = dict(re.findall(r"^(c\d+),(\w+)\s*$", src, re.M))
    order_cust = re.findall(r"^(o\d+),(c\d+)\s*$", src, re.M)
    if not cust_region or not order_cust:
        return None
    counts: dict[str, int] = {}
    for _order, cust in order_cust:
        region = cust_region.get(cust)
        if region is None:
            return None  # an order references an unknown customer → can't trust parse
        counts[region] = counts.get(region, 0) + 1
    # Every region's count must appear next to its name in the answer; a single
    # wrong or missing pairing abstains/rejects.
    answer = final_answer.lower()
    saw_wrong = False
    for region, expected in counts.items():
        reported = _count_for_label(answer, region)
        if reported is None:
            return None  # group not reported → cannot confirm the full answer
        if reported != expected:
            saw_wrong = True
    return False if saw_wrong else True


def _count_for_label(answer: str, label: str) -> int | None:
    """The integer the answer pairs with ``label`` (``label: 4`` / ``label | 4`` / ``label (4)``)."""
    m = re.search(
        rf"\b{re.escape(label)}\b[^\d\n]{{0,8}}(\d+)",
        answer,
    )
    return int(m.group(1)) if m else None


# ── 09: peak error hour ─────────────────────────────────────────────


def _verify_peak_error_hour(final_answer: str, evidence: list[dict[str, Any]] | None) -> bool | None:
    src = _evidence_text(evidence)
    hours: dict[str, int] = {}
    for line in src.splitlines():
        if "ERROR" not in line:
            continue
        m = re.match(r"\s*(\d{2}):\d{2}", line)
        if m:
            hours[m.group(1)] = hours.get(m.group(1), 0) + 1
    if not hours:
        return None
    peak = max(hours, key=lambda h: hours[h])
    # A tie has no single peak — abstain rather than judge.
    if list(hours.values()).count(hours[peak]) > 1:
        return None
    others = {h for h in hours if h != peak}
    return _answer_asserts_hour(final_answer, peak, others)


def _answer_asserts_hour(final_answer: str, peak: str, others: set[str]) -> bool | None:
    """True iff the answer reports ``peak`` (as ``09`` or ``09:00``) as THE hour."""
    reported = set(re.findall(r"\b(\d{2})(?::00)?\b", final_answer))
    # restrict to tokens that look like our hour buckets
    candidates = {h for h in reported if h == peak or h in others}
    if not candidates:
        return None
    if candidates == {peak}:
        return True
    if peak not in candidates:
        return False
    return None  # peak plus another bucket mentioned as a bare hour → ambiguous, defer


# ── 10: quarter-over-quarter growth rates ───────────────────────────


def _verify_growth_rates(final_answer: str, evidence: list[dict[str, Any]] | None) -> bool | None:
    src = _evidence_text(evidence)
    totals = [int(m.group(1)) for m in re.finditer(r"TOTAL:\s*(\d+)", src, re.I)]
    if len(totals) < 2:
        return None
    rates = [
        round((totals[i + 1] - totals[i]) / totals[i] * 100, 1)
        for i in range(len(totals) - 1)
    ]
    # The answer's percentage figures must include each expected rate.
    pcts = {round(float(m.group(1)), 1) for m in re.finditer(r"(\d+(?:\.\d+)?)\s*%", final_answer)}
    if len(pcts) < len(rates):
        return None  # didn't report enough rates to confirm → defer
    return all(r in pcts for r in rates)


# ── 13: earliest slot covering >= 4 people ──────────────────────────


def _verify_earliest_slot(final_answer: str, evidence: list[dict[str, Any]] | None) -> bool | None:
    # Each person's availability file is one evidence entry of HH:MM lines.
    if not evidence:
        return None
    per_person = [
        re.findall(r"\b(\d{2}:\d{2})\b", str(e.get("tool_output", "")))
        for e in evidence
        if isinstance(e.get("tool_output"), str)
    ]
    per_person = [p for p in per_person if p]
    if len(per_person) < 2:
        return None
    counts: dict[str, int] = {}
    for slots in per_person:
        for s in set(slots):
            counts[s] = counts.get(s, 0) + 1
    threshold = 4
    covering = sorted(s for s, n in counts.items() if n >= threshold)
    if not covering:
        return None
    earliest = covering[0]
    others = {s for s in counts if s != earliest}
    reported = set(re.findall(r"\b(\d{2}:\d{2})\b", final_answer))
    candidates = {s for s in reported if s == earliest or s in covering}
    if not candidates:
        return None
    if earliest in reported and not (set(covering[1:]) & reported):
        return True
    if earliest not in reported and (set(covering) & reported):
        return False
    return None


# ── topological sort ────────────────────────────────────────────────


def _is_topological_sort_task(task_input: str) -> bool:
    text = task_input.lower()
    return "topological sort" in text or (
        "install order" in text and "depend" in text
    )


def _verify_topological_sort(
    task_input: str,
    final_answer: str,
    evidence: list[dict[str, Any]] | None,
) -> bool | None:
    """Validate that the produced install order respects every dependency edge.

    Edges are read from the tool trajectory first (the agent's observed input),
    falling back to the task/answer text. ``A -> B`` means *A depends on B*, so a
    valid install order places B before A. Abstains (``None``) whenever the edges
    or the order cannot be parsed unambiguously.
    """
    edges = _parse_edges(evidence) or _parse_edges_from_text(
        _normalize_arrows(task_input + "\n" + final_answer)
    )
    if not edges:
        return None

    nodes = {n for edge in edges for n in edge}
    order = _parse_order(final_answer, nodes)
    if order is None:
        return None

    # A cycle has no valid linear order; if the agent claims one, that's wrong,
    # but detecting "is there a cycle" deterministically here would let us judge
    # cycle-report tasks too. The fixture set is acyclic, so we only validate the
    # ordering case and abstain if the answer doesn't present a full order.
    position = {node: i for i, node in enumerate(order)}
    # ``a -> b``: a depends on b ⇒ b must be installed (appear) before a.
    for a, b in edges:
        if position[b] >= position[a]:
            return False
    return True


def _normalize_arrows(text: str) -> str:
    """Rewrite every supported arrow glyph to ASCII ``->``."""
    return _ARROW_RE.sub(" -> ", text)


def _parse_edges(evidence: list[dict[str, Any]] | None) -> set[tuple[str, str]]:
    """Collect ``A -> B`` edges from tool outputs (the observed deps file)."""
    if not evidence:
        return set()
    edges: set[tuple[str, str]] = set()
    for entry in evidence:
        out = entry.get("tool_output")
        if isinstance(out, str):
            edges |= _parse_edges_from_text(_normalize_arrows(out))
    return edges


def _parse_edges_from_text(text: str) -> set[tuple[str, str]]:
    return {(m.group(1), m.group(2)) for m in _EDGE_RE.finditer(text)}


# Separators that join a written-out order: arrows, commas, list bullets, and
# the whitespace/newlines around them. NOT alphanumerics — those are node names.
_ORDER_SEP_RE = re.compile(r"(?:->|→|⟶|⇒|⇨|[,→\s]|^[-*\d.)]+)+", re.MULTILINE)


def _parse_order(final_answer: str, nodes: set[str]) -> list[str] | None:
    """Extract the produced install order from the final answer.

    Real answers write the order in several shapes — an arrow chain
    (``A → B → C → D``), a comma list (``D, B, C, A``), or a newline/fenced list
    (``D\\nB\\nC\\nA``) — and also restate the dependency edges (``- A → B``). We
    find the order by scanning maximal runs of node tokens separated only by
    order-separators and returning the run that is a CLEAN PERMUTATION of every
    graph node. Abstains (``None``) when no such run exists or more than one
    distinct full-permutation run disagrees — a parse we cannot trust must defer
    to the LLM, never emit a false verdict.
    """
    text = _normalize_arrows(final_answer)
    candidates: list[list[str]] = []
    for run, tainted in _node_runs(text, nodes):
        if len(run) == len(nodes) and len(set(run)) == len(nodes):
            if tainted:
                # A node-SHAPED token we don't recognise sat inside this run's
                # separators (e.g. "D, B, C, A, Z"): we cannot be sure we
                # isolated the true order — abstain rather than guess.
                return None
            candidates.append(run)
    if not candidates:
        return None
    # If the answer presents conflicting full orders, we cannot pick — abstain.
    if any(run != candidates[0] for run in candidates):
        return None
    return candidates[0]


def _looks_like_node(token: str) -> bool:
    """A short alphanumeric token shaped like a graph node id (e.g. ``A``, ``D2``)."""
    return len(token) <= 2 and token[0].isupper() and token.isalnum()


def _node_runs(text: str, nodes: set[str]) -> list[tuple[list[str], bool]]:
    """Maximal runs of node tokens separated only by order-separators.

    Returns ``(run, tainted)`` pairs. A run breaks at any character that is not a
    node token or an order separator (prose words, code-fence words, etc.).
    ``tainted`` is True when the run was broken by a NODE-SHAPED unknown token
    reached purely through order separators — that means an order line referenced
    a non-graph node, so the run cannot be trusted as the full order.
    """
    runs: list[tuple[list[str], bool]] = []
    current: list[str] = []
    tainted = False
    pos = 0
    token_re = re.compile(r"[A-Za-z][\w-]*")
    for m in token_re.finditer(text):
        gap = text[pos:m.start()]
        tok = m.group(0)
        sep = bool(_ORDER_SEP_RE.fullmatch(gap or " "))
        if tok in nodes:
            if current and not sep:
                runs.append((current, tainted))
                current, tainted = [], False
            current.append(tok)
        else:
            if current:
                # A node-shaped unknown reachable through separators taints the
                # run we are about to close (ambiguous order); prose breaks it cleanly.
                if sep and _looks_like_node(tok):
                    tainted = True
                runs.append((current, tainted))
                current, tainted = [], False
        pos = m.end()
    if current:
        runs.append((current, tainted))
    return runs
