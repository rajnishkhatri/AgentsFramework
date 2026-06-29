# meta/ — Offline Meta-Optimization

> Nested guide. Loads when Claude reads a file under `meta/`. Root `AGENTS.md`
> owns the inter-layer invariants; `tests/architecture/` enforces them. This file
> is local guidance.

## What meta is

Offline meta-optimization and evaluation: optimizer, analysis, judge, drift,
judge validation, code reviewer, feasibility. It **reads logs and config** and
produces evaluations — it never drives the live graph.

## AP-4 — No upward governance calls

**`meta/` MUST NOT import from `orchestration/` (Invariant #8).** Governance is
horizontal, not above orchestration. Importing orchestration creates a circular
dependency (governance → orchestration → services → governance). `meta/` may
import `services/` (e.g. `drift.py`, `run_eval.py`, `judge_validation.py` already
do) and `trust/`. Governance emits `TrustTraceRecord` events; a separate consumer
acts on them.

## Eval conventions

- **Judge drift** is Cohen's **κ** (`drift.py` Level 2) — a chance-corrected
  *drift* signal. It deliberately hides directionality.
- **Judge validation** is TPR/TNR + Rogan-Gladen (`judge_validation.py`) — the
  directional *validation* gate. It composes the
  `services/governance/goaljudge_calibration` confusion primitives; never
  re-implement confusion math here.
- **AP-6 (no fabricated metrics):** an undecidable metric (empty denominator,
  zero discriminative power) returns `None`, never `0.0`. `0.0` is a claim about
  a quadrant with no data.

## L4 testing rules (meta/)

- Governance feedback-loop simulations, drift/judge conventions. Tagged
  `@pytest.mark.simulation` (L4, on-demand) or plain L1 for the pure math.
- Pure metric functions are L1: exact assertions, golden numbers pinned against
  the audit anchors (e.g. the §4 production-shadow confusion counts).
- **TAP-4 (failure paths first):** judge/drift/eval-graduation tests must cover
  the rejection path before the acceptance path — `None`-when-undecidable
  (AP-6), empty-denominator guards, and regression-floor violations all need a
  failing-input test, not just the happy path. The detector
  (`detect_failure_path_ratio`) is shared; the *rule* lives here so `meta/`
  cites its own AGENTS.md.
