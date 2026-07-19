# Plan — Gen2 item-level (no-pick) hint opener authoring — pilot shard

**Spec:** [gen2-item-level-openers.spec.md](gen2-item-level-openers.spec.md)
**Status:** Draft — 2026-07-19
**Pipeline:** synthetic-data-pipeline Steps 1–7 (Plane C)

---

## A1 — Simplest thing that satisfies the criteria

The pilot reuses **every existing seam** and adds exactly **one net-new authored artifact** (an item-level opener prompt). No new abstraction, no new script framework, no schema change. What already exists and is reused:

| Need | Existing seam (grounded) | Change |
|---|---|---|
| Generator | `scripts/generate_hints.py` (`--questions --out --existing`, per-Q loop, renders a `.j2`) | Point at a new prompt + item-level few-shot; no code rewrite |
| Prompt | `prompts/hint_generator.j2` (choice-keyed) | **NEW sibling** `prompts/hint_item_level_opener.j2` (the one net-new artifact) |
| Leak lint | `components/hint_leakage.py` (deterministic per-rung regex) | Reused as-is (FR-1) |
| Cascade | `components/test_item_generation.py` / hint cascade | Reused; output stays `reviewed=false` |
| Emit gate | `scripts/emit_hint_bank.py` (dies on unreviewed) | Unchanged; FR-3 asserts not-weakened |
| Coverage ratchet | `frontend/lib/adapters/engine/_hint_bank.test.ts` | Unchanged (item-level is the *other* covered branch) |
| Acceptance sampling | `docs/questionbank/coach-bank-gen2-aql-sample.json` + `-step5-scorecard.md` | **Reuse the shape** for the pilot scorecard |
| Wire schema | `frontend/lib/wire/engine_entities.ts:108-122` (`choice_letter` nullable, rung 1\|2\|3) | Unchanged — item-level openers already representable |

**G1 note:** no new abstraction introduced. The item-level prompt is content; the misconception-neutrality invariant (FR-2) is a lint, not a new type.

## Architecture / flow

```
Step 1 (demand)  → DONE at brainstorm: gap sized (816 items), pilot chosen, D3 accepted
Step 2 (generate)→ scripts/generate_hints.py --questions <pilot-shard.json>
                    --out <pilot-openers.raw.json>
                    rendering prompts/hint_item_level_opener.j2
                    few-shot anchors = reviewed Gen1 item-level rows (FR-6)
Step 3 (cascade) → schema + FR-1 leak lint (hint_leakage.py) + FR-2 neutrality lint
                    + FR-4 rung-shape + FR-5 diversity + dedup → rows stay reviewed=false
Step 4 (solve/contam) → n/a for openers (no key to solve); contamination dedup vs served bank
Step 5 (accept)  → ISO-2859 sample harness (reuse gen2 aql-sample shape) → SCORECARD
                    [HUMAN REVIEW — deferred, out of impl scope]
Step 6 (emit)    → NOT run in pilot impl (gated on reviewed=true, earned only at Step 5)
Step 7 (monitor) → per-shard scorecard = the go/no-go input for the full 816 corpus (FR-9)
```

## File-level touchpoints

**New files:**
- `prompts/hint_item_level_opener.j2` — misconception-neutral pre-pick opener prompt; both item types (underlined-span + rhetorical); inherits no-leak + ≥10-opener-diversity contracts. **(the one net-new artifact)**
- `docs/plan/gen2-item-level-openers.pilot-shard.json` — the frozen ~50–100 skill-stratified item list (selection rule → `decisions.md`).
- `docs/questionbank/coach-bank-openers-pilot.raw.json` — Step-2 generator output (reviewed=false).
- `docs/questionbank/coach-bank-openers-pilot-step5-scorecard.md` — Step-5 scorecard (mirrors `coach-bank-gen2-step5-scorecard.md`).
- Tests: item-level-opener lints (FR-1/2/4/5) — co-located with the existing hint cascade tests.

**Touched (additive only):**
- `docs/plan/coach-bank-hints.seed.json` — pilot openers appended **only after** Step-5 accept (deferred; not in impl).
- `docs/adr/decisions.md` — pilot shard selection rule (2–4 lines).

**Explicitly NOT touched:**
- `frontend/lib/wire/engine_entities.ts` (no schema change).
- `scripts/emit_hint_bank.py` (fail-closed behavior preserved).
- No `pyproject.toml` change (no new dep).

## Migration steps

1. Freeze the skill-stratified pilot shard → `pilot-shard.json` + `decisions.md` entry.
2. Author `prompts/hint_item_level_opener.j2` (few-shot from reviewed Gen1 openers).
3. Write the FR-1/2/4/5 lints (red first — assert they reject a leaking / choice-presuming / mis-shaped / repetitive opener).
4. Run the offline generation job → `openers-pilot.raw.json` (reviewed=false).
5. Run cascade + lints on 100% of rows; route failures to repair (three-strikes → stop, re-plan the prompt).
6. Build the Step-5 sampling harness + scorecard template (reuse gen2 aql shape); populate n / Ac=0 / defect-class fields.
7. **STOP.** Hand the scorecard + cascade-passed rows to the human reviewer as a scheduled step. Full-corpus go/no-go is a separate human decision (FR-9).

## Constitution check (root AGENTS.md 8 invariants)

- **Not an Ask-first trigger:** no new dep, no trust-kernel type, no new node, no new service, no new abstraction, no schema change → **no ADR** (spec §5). `decisions.md` entry for the shard rule only.
- **No live LLM in CI** (🚫 Never): generation is offline; only deterministic lints/cascade/emit tests run in `make check`.
- **Layer invariants:** untouched — content + one prompt + offline script + tests.
- **`reviewed=true` earned only at Step 5** (pipeline law): impl builds the funnel, never asserts the flag.
