# Gen2 Step 5 scorecard — Z1.4 acceptance sampling

Generated 2026-07-17 · follows `synthetic-data-pipeline` Step 5 · lot:
leak-green ∩ solve-PASS from
`research/synthetic_data_pipeline_handover/docs/questionbank/coach-item-bank-gen2.promoted.json`
(N=**816**; 184 Step-4 quarantines excluded).

> **Law:** this is the only gate that earns `reviewed=true`. Flip is
> per accepted shard, never per-item patching.

---

## Sample frame

| Parameter | Value |
|---|---|
| Standard | ISO 2859-1 / ANSI-ASQ Z1.4 attributes |
| Inspection level | General **II** → code letter **J** |
| Lot size N | **816** |
| Sample size n | **80** (seed=20260717) |
| Critical | AQL **0** → Ac=0 / Re=1 |
| Minor | AQL **2.5** → Ac=5 / Re=6 |
| Unit | item + all 12 hints |
| Artifacts | `coach-bank-gen2-aql-sample.json`, `coach-bank-gen2-step5-review-packet.json`, `coach-bank-gen2-step5-inspection.json` |

## Inspection result — ACCEPT

| Verdict | n |
|---|---:|
| PASS | 77 |
| MINOR | 3 |
| CRITICAL | **0** |
| **Lot decision** | **ACCEPT** (0 critical ∧ 3 ≤ 5 minor) |

### Minors (do not reject)

| seq | question_id | class | evidence |
|---:|---|---|---|
| 29 | `ti-gen-6af713b67368333e` | stylistic_infelicity | space before semicolon in context (`hour ; the`) |
| 32 | `ti-gen-3eb5738a961ab620` | stylistic_infelicity | space-before-comma in NO CHANGE list (`crust , filling`) |
| 69 | `ti-gen-1a09c7cb7471f71e` | stylistic_infelicity | key rewrite yields stiff `and, unhurried, she` |

No wrong/indefensible key, hint leak beyond lint, schema break, live-bank duplicate, or rung-4 key statement in the sample.

## `reviewed` flip (applied)

| Scope | Count | `reviewed` |
|---|---:|---|
| Solve-PASS items | 816 | **true** |
| Their hints (×12) | 9,792 | **true** |
| Step-4 quarantine items | 184 | false (untouched) |
| Quarantine hints | 2,208 | false (untouched) |

Files written:
- `research/.../coach-item-bank-gen2.promoted.json`
- `research/.../coach-bank-hints-gen2.json`

`generated_by` left unchanged (cascade `<model>@<run_id>` provenance intact).

## Exit / next

- [x] AQL sample drawn from N=816 only
- [x] n=80 inspected against §B.2/B.3 taxonomy
- [x] Lot ACCEPT → `reviewed=true` on eligible shard
- [x] Step 6 schema/emitter — ADR-0031 (`choice_letter` + uniqueness; rung 4 off wire)
- [x] Step 6 emit Gen2 shard — merged reviewed 816 items + 7,344 wire hints into live seeds; regenerated banks (987 items / 7,857 hints). Coach pass-through: `choice_letter` on `coach_context` + `react_loop` → `rungs_for_question`.
- [x] Step 6 quiz moment router — wrong pick → `loadHintLadder` + `setCoachChoiceLetter` → panel ladder + `sendCoachAsk` `choice_letter` (no/correct pick → item-level null).
- [ ] 184 quarantine: human key-ambiguity / mismatch review (out of this shard)
