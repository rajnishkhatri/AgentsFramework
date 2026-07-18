---
type: research-pack
title: Synthetic-data pipeline research handover pack
description: >-
  Self-contained baselines + research prompt for a research agent to supplement
  the Practical Synthetic Data chapters with 2024–2026 best practices, grounded
  in this workspace’s coach-bank / cascade reality.
authored: 2026-07-17
---

# Synthetic-data pipeline — research handover pack

Give this **entire folder** to the research agent.

## Start here

1. Read [`RESEARCH_PROMPT.md`](RESEARCH_PROMPT.md) (mission, RQs, deliverable shape).
2. Read every path listed under **Baseline** in that prompt (all files live in this pack; paths are relative to this folder root).
3. Produce the research note at the path named in the prompt (usually written back into the main repo under `docs/research/`).

## Layout

Paths mirror the main repo so citations stay stable:

| Pack path | Role |
|---|---|
| `docs/SyntheticDataCreation/` | Book chapters (baseline to update) |
| `docs/plan/` | Brainstorms + Gen2 adoption session |
| `docs/questionbank/` | Gen2 bank/hints + QA report + batch prompt |
| `docs/research/goaljudge_*` | Exemplars of in-repo “synthetic” = eval strata (not SDV) |
| `research/act_english_*.md` | Existing QA playbook + LLM ranking |
| `components/test_item_generation.py` | Verifier cascade (`reviewed` earned) |
| `scripts/` | Gen1 generate / emit / promote jobs |
| `frontend/lib/wire/engine_entities.ts` | `TestItem` wire schema |
| `tests/synthetic/` | Constructed eval fixtures |
| `AGENTS.md` | Repo constraints (no live LLM in CI, Ask-first deps) |
| `MANIFEST.txt` | Exact file list in this pack |

## Size note

Gen2 JSON corpora (~6.5 MB combined) are included so the agent can inspect schema/shape and QA claims; do **not** re-emit or treat them as reviewed product fuel.

## Source of truth

This pack is a **snapshot for research handover**. Canonical live files remain in the main repo at the same relative paths. Refresh the pack if baselines change materially before a new research run.
