# NOTES — axial coding pass (without_skill workspace)

## What this was
Stage-2 axial coding over the open-coded slice at
`docs/skills/agentsframework-axial-coding/evals/fixtures/coded_slice.jsonl`
(30 traces, all `pre_submit`, 21 distinct open codes). Goal: build a partitioned,
testable failure taxonomy ready to hand to rubric design.

## Method (agentsframework-axial-coding skill, the how)
Followed the skill's 6-step loop and its one hard rule: *no assertion may be
emitted from an unpartitioned aggregate* — the `axial_checker.py` gate had to pass
before any count or rubric candidate.

## Steps run
0. **Inventory** — `scripts/build_coach_open_code_inventory.py --coded <fixture>
   --out outputs/inventory.csv` → 21 rows, blank axis/category.
1. **Partition** — filled `axis` for all 21 codes (programmatic fill preserving the
   generated CSV's multi-line example fields):
   - 20 agent-behavior, 1 environment-confound (`truncated-reply`), 0 judge-reliability.
   - Straddle: `truncated-reply` = confound **by cause**, unscorable **by
     consequence**; assigned by cause, consequence in `alias_note`.
2. **Cluster** — filled `category`; wrote `outputs/categories.csv` (9 categories:
   8 agent-behavior + 1 confound), each with a real `binary_check`; 2 declared
   dimensions (`answer-leakage`, `hint-calibration`) carry `|`-separated boundary
   checks. Did NOT force-lump to 6 — honest count is 8 agent-behavior categories.
3. **Gate** — `axial_checker.py` → **OK / exit 0** (emit allowed).
4. **Count + pairs** — `axial_matrix.py` → `outputs/matrix.json`
   (agent_denominator 30, confound_only_excluded 0); `axial_minimal_pairs.py` →
   `outputs/minimal_pairs.json`. Then applied the FR-8 axis-blind filter by hand:
   of 4 surfaced groups, **3 are gold, 1 is noise** (Pair D diverged only on the
   `truncated-reply` confound — the exact false positive the tool warns about).
5. **Write-up** — `outputs/coach_axial_coding.md` (category map, 2 gradients,
   frequencies, 3 gold minimal pairs + 1 rejected + 1 non-paired graded family,
   cross-cuts).
6. **Emit** — 7 rubric assertions + 4 judge test-case seeds, each traced to a
   partitioned testable category.

## Key judgment calls
- **Refusal-theater is the headline finding.** `2c21ab67` and `48129021` refuse the
  answer *by name* and then leak the crux in Socratic clothing — narration
  contradicts behavior. Rubric assertion #2 exists to force behavior-over-narration
  scoring.
- **answer-leakage is graded, not binary** — a 4-boundary severity ramp
  (preserve → rule-name → strong-implication → hands-over). Highest frequency (24).
  The rubric must score the boundary.
- **overshoot→leak coupling**: every `overshoots-the-ask` trace also leaks; hint-size
  and leakage are not independent.
- **Corpus flags kept OUT of the taxonomy.** Memo `DATASET FLAG` / id-churn /
  generator-conflation notes are item-bank artifacts → corpus-hygiene ticket, not
  failure modes. That's why judge-reliability axis is empty (no verdict-defect code
  was minted) — distinct from "no judge problems exist".

## Outputs in this dir
- `inventory.csv` — 21 codes, axis + category filled (edit surface for re-runs).
- `categories.csv` — 9 categories, polarity + binary_check + dimension.
- `matrix.json` — confound-excluded per-category counts.
- `minimal_pairs.json` — raw detector output (axis-blind; filtered in write-up).
- `coach_axial_coding.md` — the taxonomy write-up + emitted candidates.
- `NOTES.md` — this file.

## To re-run / iterate
Edit `inventory.csv` (axis/category) or `categories.csv`, then:
```
S=docs/skills/agentsframework-axial-coding
.venv/bin/python $S/scripts/axial_checker.py --inventory inventory.csv --categories categories.csv
.venv/bin/python $S/scripts/axial_matrix.py --coded <fixture> --inventory inventory.csv
.venv/bin/python $S/scripts/axial_minimal_pairs.py --coded <fixture>
```

## Not done (out of Stage-2 scope)
Selective coding (single core category + storyline) is human synthesis on top —
the handbook owns it. Candidate core category if asked: *answer-leakage under
pressure* (leakage is the dominant, graded axis and couples to refusal-theater +
overshoot).
