#!/usr/bin/env python
"""Generate the GoalJudge synthetic prompt-matrix manual walkthrough from case_registry.py.

Run from repo root:
    python scripts/generate_goaljudge_manual_walkthrough.py

Writes:
    docs/walk-through/04_goaljudge_synthetic_prompt_matrix_manual_walkthrough.md
"""

from __future__ import annotations

import uuid
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = (
    AGENT_ROOT
    / "docs/walk-through/04_goaljudge_synthetic_prompt_matrix_manual_walkthrough.md"
)

import sys

sys.path.insert(0, str(AGENT_ROOT))

from tests.fixtures.goaljudge.case_registry import LIVE_CASES, GoalJudgeCase

_NON_FAILURE = {"correct-complete"}


def _trace_id(case_id: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_DNS, case_id).hex


def _axes_line(axes: dict) -> str:
    gm = axes.get("goal_met")
    gf = axes.get("graceful_failure")
    pf = axes.get("partial_fraction")
    return (
        f"`goal_met={str(gm).lower()}` · "
        f"`graceful_failure={str(gf).lower()}` · "
        f"`partial_fraction≈{pf}`"
    )


def _ec_checklist(case: GoalJudgeCase) -> str:
    axes = case.target_axes
    gm = axes.get("goal_met")
    gf = axes.get("graceful_failure")
    pf = axes.get("partial_fraction")
    lines = [
        f"- [ ] **LF** Langfuse trace `{_trace_id(case.id)}` → `task.completed` has `goal_met={str(gm).lower()}` (± judge tolerance)",
    ]
    if gf is True:
        lines.append(
            '- [ ] **EC** `graceful_failure=true` in `logs/evals.log` (`target="goal_judge"`, same `task_id`)'
        )
    elif gf is False:
        lines.append("- [ ] **EC** `graceful_failure=false`")
    if isinstance(pf, (int, float)) and 0 < pf < 1:
        lines.append(f"- [ ] **EC** `partial_fraction` in `(0,1)` (target ≈ `{pf}`)")
    elif pf == 0.0:
        lines.append("- [ ] **EC** `partial_fraction≈0.0`")
    elif pf == 1.0:
        lines.append("- [ ] **EC** `partial_fraction≈1.0`")
    lines.append(
        "- [ ] **EC** `per_criterion` + `rationale` cite observable tool evidence (not narration alone)"
    )
    lines.append(
        f"- [ ] **Coding** Record observed open codes (≤3); target `{case.target_code}` — mismatch is data, not a re-roll"
    )
    return "\n".join(lines)


def _case_block(case: GoalJudgeCase) -> str:
    tid = _trace_id(case.id)
    return f"""#### {case.id} · `{case.target_code}`

| Field | Value |
| --- | --- |
| **Trace ID** (deterministic) | `{tid}` |
| **Stratum (D5)** | `{case.stratum}` |
| **Domain (D1)** | `{case.domain}` |
| **Feasibility (D2)** | `{case.expected_feasibility}` |
| **Target axes (D4)** | {_axes_line(case.target_axes)} |
| **Provenance** | `{case.provenance}` |

**Prompt** (paste verbatim into the local agent, or run `python scripts/run_goaljudge_synthetic_batch.py --case {case.id}`):

> {case.prompt}

{_ec_checklist(case)}

"""


def _group_cases() -> list[tuple[str, list[GoalJudgeCase]]]:
    order: list[str] = []
    groups: dict[str, list[GoalJudgeCase]] = {}
    for c in LIVE_CASES:
        if c.target_code not in groups:
            groups[c.target_code] = []
            order.append(c.target_code)
        groups[c.target_code].append(c)
    return [(code, groups[code]) for code in order]


def _index_table() -> str:
    rows = [
        "| Case | Trace ID | Target code | Stratum | Domain | Expected axes (D4) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for c in LIVE_CASES:
        rows.append(
            f"| {c.id} | `{_trace_id(c.id)}` | `{c.target_code}` | {c.stratum} | {c.domain} | {_axes_line(c.target_axes)} |"
        )
    return "\n".join(rows)


def _code_sections() -> str:
    parts: list[str] = []
    n = 0
    for code, cases in _group_cases():
        n += 1
        label = (
            "baseline (non-failure)"
            if code in _NON_FAILURE
            else f"agent-behavior code {n}"
        )
        parts.append(f"### Code group: `{code}` ({label})\n")
        parts.append(f"*{len(cases)} case(s) in this group.*\n")
        for case in cases:
            parts.append(_case_block(case))
    return "\n".join(parts)


HEADER = """# GoalJudge Synthetic Prompt Matrix — Manual Walkthrough

> **Generated from** [`tests/fixtures/goaljudge/case_registry.py`](../../tests/fixtures/goaljudge/case_registry.py) via [`scripts/generate_goaljudge_manual_walkthrough.py`](../../scripts/generate_goaljudge_manual_walkthrough.py). Re-run the generator after editing the registry so this document stays in sync.

**Goal:** Hand-validate the **47-case live synthetic prompt matrix** (Phase 2b saturation corpus) the same way [02 — UI + Langfuse validation](02_goaljudge_ui_langfuse_validation_walkthrough.md) validates P1–P5: run each prompt, record deterministic `trace_id`s, verify Langfuse + `eval_capture` axes, and annotate open codes — without relying on batch-only sign-off.

**Audience:** Engineer or researcher running case-by-case local validation, debugging a single stratum, or producing evidence rows for [Phase 2b open coding](../research/goaljudge_phase2b_open_coding.md).

**Time budget:** ~6–8 hours for all 47 cases at ~8 min/case (setup ~15 min; optional full batch ~20 min after spot-checks). Smoke path: **GJ-001 + GJ-025 + GJ-049** (~30 min).

**Why this guide exists:** Walkthrough **03** covers the **programmatic batch** path. This document is the **human-readable prompt matrix**: every `GJ-*` prompt, dimension tags, expected verdict axes, deterministic trace IDs, and per-case LF/EC checklists — mirroring §“The prompt matrix (P1–P5)” in walkthrough 02.

**Companion docs:**
- Dimension space + codebook: [`docs/research/goaljudge_synthetic_dimension_space.md`](../research/goaljudge_synthetic_dimension_space.md)
- Batch automation: [`docs/walk-through/03_goaljudge_synthetic_saturation_walkthrough.md`](03_goaljudge_synthetic_saturation_walkthrough.md)
- Phase 2 exploratory runs (P1–P5): [`docs/walk-through/02_goaljudge_ui_langfuse_validation_walkthrough.md`](02_goaljudge_ui_langfuse_validation_walkthrough.md)
- Field-location map (Langfuse vs `eval_capture`): [02 §Field-location map](02_goaljudge_ui_langfuse_validation_walkthrough.md#field-location-map-read-before-you-check-anything)
- Judge-stress set (`fabricated-progress`, `premature-impossible`): [`tests/fixtures/goaljudge/stress_fixtures.py`](../../tests/fixtures/goaljudge/stress_fixtures.py) — **not** in this live matrix

---

## Corpus scope

| Item | Count | Notes |
| --- | ---: | --- |
| Live cases in `LIVE_CASES` | **47** | IDs `GJ-001` … `GJ-052` (gaps intentional; no GJ-016–018, 037–038) |
| Agent-behavior failure codes | **15** | ≥3 cases each (45 failure prompts) |
| Non-failure baseline | **2** | `correct-complete` (`GJ-049`, `GJ-050`) |
| Excluded from live matrix | 2 codes | `fabricated-progress`, `premature-impossible` → stress fixtures only |
| Scoping `user_id` | `synthetic-saturation-user` | Required for export + coverage gate |
| Trace / task / workflow ID | `uuid.uuid5(NAMESPACE_DNS, case_id).hex` | Stable across re-runs |

---

## What you are proving

```mermaid
flowchart TD
  s0["Step 0: Env + outbox relay + truncate evals.log"] --> s1["Step 1: Local pytest pins"]
  s1 --> s2["Step 2: Smoke GJ-001 / GJ-025 / GJ-049"]
  s2 --> s3["Step 3: Run matrix case-by-case"]
  s3 --> s4["Step 4: Coverage gate"]
  s4 --> s5["Step 5: Export scoped JSONL"]
  s5 --> s6["Step 6: Fill run log + open codes"]
```

| Item | What it proves |
| --- | --- |
| Registry ↔ telemetry join | Each `GJ-*` maps to one 32-hex `trace_id` with both Langfuse + `goal_judge` eval_capture rows |
| Stratified coverage | Every live failure code has ≥3 independent prompts across D1/D2/D5 |
| Target vs observed | Axes and open codes recorded; divergences kept as judge/agent evidence (J2/J3 candidates) |
| Scoping integrity | No foreign/orphan rows under `synthetic-saturation-user` |

---

## Per-prompt checklist legend

Same convention as walkthrough 02:

- **LF** — Langfuse trace (`task.completed` details: `goal_met`, `outcome`, `downgrade_reason`)
- **EC** — `grep '"target": "goal_judge"' logs/evals.log | jq` keyed on `task_id` == trace ID
- **Coding** — Qualitative open codes (≤3), first-failure discipline; see [dimension space codebook](../research/goaljudge_synthetic_dimension_space.md)

> **Path note:** Prompts in the registry use the repo `workspace/` directory (local file_io sandbox). Run from repo root (`python scripts/run_goaljudge_synthetic_batch.py` already `chdir`s there). Do not substitute `/tmp` paths from walkthrough 02 unless you intentionally fork a case.

---

## Step 0 — Environment and isolation

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent
pip install -e ".[dev]"

# Required for live runs + Langfuse export
export OPENAI_API_KEY="sk-..."
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_SECRET_KEY="sk-lf-..."
export LANGFUSE_HOST="https://cloud.langfuse.com"
```

**Terminal A — outbox relay** (keep open):

```bash
python -m middleware.sidecars
```

**Terminal B — before the matrix**, truncate `logs/evals.log` so eval_capture rows belong only to this session (batch runner does this automatically):

```bash
: > logs/evals.log
```

**Local GoalJudge posture** (file-backed, not GCS): ensure [`config/goal_judge_config.json`](../../config/goal_judge_config.json) has `goal_judge_enabled: true`. For shadow telemetry during coding, keep `goal_judge_downgrade_enabled: false` unless you are explicitly re-testing the gate.

**Checklist:**
- [ ] `OPENAI_API_KEY` and `LANGFUSE_*` set
- [ ] Outbox relay running (Terminal A)
- [ ] `logs/evals.log` truncated or fresh
- [ ] `config/goal_judge_config.json` posture confirmed

---

## Step 1 — Local pytest baseline

```bash
python -m pytest -p no:logfire tests/components/test_goal_judge.py -q
python -m pytest -p no:logfire tests/orchestration/test_goal_judge_gate.py -q
python -m pytest -p no:logfire tests/components/test_goal_judge_redteam_offline.py -q
```

---

## Step 2 — Smoke cases (recommended before all 47)

Run three cases that anchor failure, graceful impossibility, and success baselines:

```bash
python scripts/run_goaljudge_synthetic_batch.py --case GJ-001 --yes
python scripts/run_goaljudge_synthetic_batch.py --case GJ-025 --yes
python scripts/run_goaljudge_synthetic_batch.py --case GJ-049 --yes
```

Confirm in Langfuse (filter `user_id = synthetic-saturation-user`) that traces exist for:

| Case | Trace ID |
| --- | --- |
| GJ-001 | `d4c20501f8a45a82a1a9f2361237bb68` |
| GJ-025 | `af9f6dec81cf5848a050013f73116157` |
| GJ-049 | `7fb9c2c512c35dc5b8898c1a869935e4` |

---

## Step 3 — Run the prompt matrix (manual or batch)

### Option A — Case-by-case (this walkthrough)

For each section below, either:

1. Run `python scripts/run_goaljudge_synthetic_batch.py --case <GJ-xxx> --yes`, **or**
2. Paste the prompt into `python -m agent.cli "<prompt>"` (note: ad-hoc CLI runs **do not** get deterministic trace IDs unless you wire `workflow_id` yourself — prefer Option 1 for export join integrity).

Wait for Terminal A to flush Langfuse observations (~5–30s), then complete the per-case LF/EC/Coding checklists.

### Option B — Full batch (walkthrough 03)

```bash
python scripts/run_goaljudge_synthetic_batch.py --yes
```

Use this document afterward for spot audits and open-coding annotations.

---

## Master index (all live cases)

"""

FOOTER = """

---

## Step 4 — Coverage and integrity gate

```bash
python scripts/verify_goaljudge_coverage.py
```

Expect: every failure code ≥3 cases, zero orphan/foreign rows, axis divergences listed as **data** (not failures to re-roll).

---

## Step 5 — Export scoped JSONL corpus

```bash
python scripts/export_goaljudge_corpus.py --user-id "synthetic-saturation-user"
head -n 1 cache/goaljudge_eval/run.jsonl | python -m json.tool
```

Each row should include `provenance`, `stratum`, `target_code`, and `case_id` when exported with the registry map.

---

## Step 6 — Run log and open coding

Fill one row per case after inspection. Copy `trace_id` from the index table above.

| Case | `trace_id` | Target code | Observed `goal_met` | Observed `graceful_failure` | Observed `partial_fraction` | Open codes (≤3) | J2/J3 notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GJ-001 | | `missing-requested-information` | | | | | |
| … | | | | | | | |

Hand off annotated `cache/goaljudge_eval/run.jsonl` to Stage 3 axial coding per [Phase 2b report](../research/goaljudge_phase2b_open_coding.md).

---

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| Trace missing in Langfuse | Confirm outbox relay running; wait 30s; re-run `--case` |
| No `goal_judge` in `evals.log` | Judge disabled in `config/goal_judge_config.json` |
| `verify_goaljudge_coverage` foreign rows | Truncate `evals.log`; use only `synthetic-saturation-user` runs |
| Trace ID mismatch | Must use batch runner (deterministic `uuid5`) — do not mix ad-hoc CLI ids |
| File path errors | Run from repo root; paths must stay under `workspace/` |

---

## References

- [`tests/fixtures/goaljudge/case_registry.py`](../../tests/fixtures/goaljudge/case_registry.py) — source of truth for prompts
- [`scripts/run_goaljudge_synthetic_batch.py`](../../scripts/run_goaljudge_synthetic_batch.py) — local executor
- [`scripts/verify_goaljudge_coverage.py`](../../scripts/verify_goaljudge_coverage.py) — coverage gate
- [`scripts/export_goaljudge_corpus.py`](../../scripts/export_goaljudge_corpus.py) — JSONL export
- [`docs/walk-through/03_goaljudge_synthetic_saturation_walkthrough.md`](03_goaljudge_synthetic_saturation_walkthrough.md) — batch-first procedure
"""


def main() -> None:
    body = (
        HEADER
        + _index_table()
        + "\n\n---\n\n## The prompt matrix (GJ-001 … GJ-052)\n\n"
        + _code_sections()
        + FOOTER
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(body, encoding="utf-8")
    print(f"wrote {len(LIVE_CASES)} cases to {OUT_PATH}")


if __name__ == "__main__":
    main()
