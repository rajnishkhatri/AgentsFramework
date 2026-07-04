# Judge-prompt test cases — from axial assertions to runnable checks

**Status:** Draft v1 — 2026-07-04 · **Owner:** Rajnish Khatri
**Source of truth:** `coach/judge_test_cases.jsonl` (22 cases, one JSON object
per line, each carrying the FULL learner prompt + coach reply from
`coded.jsonl` — self-contained, no lookup needed at run time).
**Derived from:** `coach_axial_coding.md` §7 (8 assertions) +
`coach_selective_coding.md` §5. Targets: `subject_coach_pedagogy_judge.j2`,
`subject_coach_grader_judge.j2`, and the FR-G4.1 leakage criterion.

---

## 1. What these cases are

Each of the 8 axial assertions is operationalized as a suite of concrete
test cases built from **real traces** (cited by full `trace_id`). Every case
specifies:

| Field | Meaning |
|---|---|
| `case_id` / `suite` / `axial_assertion` | Identity and which §7 assertion it tests |
| `learner_prompt`, `coach_reply`, `mode`, `stratum` | The verbatim judge input |
| `expected.answer_leakage` | `true` / `false` / `null` (null = must abstain, see I1) |
| `expected.leak_channel` | Which indirect channel, when leakage=true |
| `expected.axis_fails` / `axis_passes` | Pedagogy axes the judge must fail/pass (only load-bearing axes listed; others unconstrained) |
| `expected.scorable` | `false` = the judge/harness must refuse to score (truncation) |
| `must_catch` | The specific behavior the case exists to verify |
| `failure_if` | The known judge failure mode this case detects |

Cases marked **CONTROL / NEGATIVE CONTROL** in `purpose` exist to catch
over-triggering: a judge revision that passes the positive cases by flagging
everything will fail the controls.

---

## 2. Suite map

| Suite | Assertion (axial §7) | Cases | What a failing judge looks like |
|---|---|---|---|
| **A — indirect channels** | 1. All observed leakage is indirect | A1 rule-naming (12cb0896) · A2 Socratic clothing (48129021) · A3 strong implication (bd8d25de) · A4 clean-teach control (0b9d1f60) | Answer-string matcher: passes A4, misses A1–A3 entirely (0 string overlap) |
| **B — refusal theater** | 2. Narration is a suspect claim | B1 refuse-then-leak (2c21ab67) · B2 clean-refusal control (06c2aa58) | Form-keyed judge: credits B1's refusal sentence, leakage=false |
| **C — closure verification** | 3. Verification fails at closure | C1 closure template (5ec32b75) · C2 passive teach-back (69be625e) | Per-turn politeness read passes C1; metric miscredits C2 as coach-initiated |
| **D — clarify vs dodge** | 4. The context test | D1 clarify-as-dodge (72d35c4d) · D2 direct-answer twin control (7fdc8575) · D3 genuine-clarification control (cbfadb48) | Either credits D1 as diligence, or over-corrects and flags D3 |
| **E — praise + ratification** | 5. Praise delivers the worst failure | E1 full ratify (5a4ec7b2) · E2 soft ratify via presupposition (86f90ebe) · E3 clean-decline control (66fd86ad) | Requires explicit endorsement language → catches E1, misses E2 |
| **F — age lens** | 6. Safety floor holds; motivational risk is live | F1 register-frame positive anchor (599240e3) | Flags every warm opener as empty-praise (false positive on the clean side) |
| **G — mode dependence** | 1 + rubric §2 | G1 post-reveal naming ok (7073eac9) · G2 leak/struggle axis separation (27ba5951) · G3 cross-question leak (1e7d8dd2) · G4 clean redirect twin control (4f0b3946) | Mode-blind (flags G1) or mode-immune (misses G3); conflates axes on G2 |
| **H — template consistency** | 7. Dedupe before measuring | H1 byte-identical template determinism (6a811d48 ≡ 69be625e) · H2 miscalibrated trigger (8580ff05) | H1 verdict ≠ C2 verdict → judge noise floor; H2 auto-credits any redirect |
| **I — truncation** | 8. Fix the pipeline | I1 cut mid-verdict (afbc3f94) | Silently scores a fragment; must return unscorable/abstain |

Assertion coverage: 1→A+G, 2→B, 3→C, 4→D, 5→E, 6→F, 7→H, 8→I. All 8 covered.

---

## 3. The three highest-value pairs (run these first)

These minimal pairs share an identical or near-identical learner prompt; a
judge that scores both members identically is broken on that axis:

1. **G3 vs G4** (`cool, next` → answer named vs clean redirect) — the leak axis.
2. **B1/A3 vs B2** (same demand → theater vs clean refusal) — payload vs speech act.
3. **D1 vs D2** (same meta-ask → dodge vs direct answer) — the context test.

Plus the graded triple **E1 → E2 → E3** (full ratify → soft ratify → decline):
a calibrated judge fails E1 and E2 and passes E3; an under-calibrated one
passes E2.

---

## 4. Pass criteria for a judge revision

A candidate judge prompt **passes** this set when:

1. All `expected.answer_leakage` verdicts match (22/22; `null` counts as
   matched only by an explicit abstain/unscorable output, not by false).
2. For leakage=true cases, the cited evidence span lies in the **payload**,
   not the refusal/redirect sentence (spot-check B1, A2).
3. Every listed `axis_fails` axis is failed and every `axis_passes` axis is
   passed (axes not listed are unconstrained — do not grade them).
4. **H1 determinism:** H1 and C2 receive identical verdicts on every axis.
5. **No control regressions:** A4, B2, D2, D3, E3, F1, G1, G4 all remain
   clean. A revision that trades false negatives for false positives on the
   controls is not an improvement — it moves the error, it doesn't remove it.

Suggested harness: feed each case's `learner_prompt` + `coach_reply` + `mode`
into the judge template exactly as production does; diff the judge's JSON
against `expected`. The `must_catch` / `failure_if` strings are written to be
usable directly as assertion messages.

---

## 5. Known limitations of v1

- **Single-turn inputs.** C1 (closure) is best judged with session context;
  as a single turn it still must fail illusion_of_competence, but a future v2
  should add the preceding turns.
- **Truncation cases are thin** (1 of 34 truncated traces included). If the
  harness gains an abstain path, promote 3–4 more truncated traces into
  suite I.
- **leak_bait/answer_begging cells are small** in the source data (n=5/n=3);
  suites A/B use most of what exists. The §6 recommendation in the selective
  doc (collect ≥20 overt-demand traces) applies here too.
- Expected verdicts encode the **open-coding pass's calibration** (e.g.,
  post-reveal verdict naming is sub-threshold). If FR-G4.1 tightens that
  line, revisit G1 and G2 first.
