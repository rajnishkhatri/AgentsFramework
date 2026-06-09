# Stage 4 A2 IAA — Pass 1 Instrument Validation

> **Not a human gate clearance.** This file records κ computation on a synthetic sheet where
> both raters match the withheld answer key — it validates the instrument and κ script only.
> **G5 remains OPEN** until two blind human graders complete
> [`goaljudge_stage4_a2_iaa_grader_sheet.csv`](goaljudge_stage4_a2_iaa_grader_sheet.csv).

## Pass 1 scope (gate-eligible anchors)

GJ-008, GJ-010, GJ-012, GJ-001B, GJ-019

## Result

```
rows=5 agreements=5 kappa=1.0000 band=almost perfect
gate=PASS (threshold κ ≥ 0.8)
```

Computed via:

```bash
python scripts/compute_goaljudge_stage4_iaa_kappa.py \
  docs/IAA/goalJudge/goaljudge_stage4_a2_iaa_pass1_instrument_validation.csv
```

## Pass 2 (pending)

After G3 batch: add GJ-011, GJ-013, GJ-003B traces; re-run blind human grading.
