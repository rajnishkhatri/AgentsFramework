# T3 Stage B — Case-by-case report (DOM ⨝ Langfuse)

Each fan-out case joined on the deterministic `trace_id`: the **browser** result (`cache/planning_stress/ui_batch.jsonl`, latest run per case) next to the **graph** carriers pulled live from Langfuse. The join makes the Stage-B split legible — a correct server-side fan-out *decision* whose *answer* never reached the browser.

> `chars`/`cards` = browser-side; `decision`/`br#`/`joins`/`join_chars`/`br c/t` = graph-side (Langfuse); `want` = corpus expectation. `joins`>1 = fanned out again under reflexion. These traces carry no `delegation_requested` obs — the `decision` + a real `fanout_join` carrier IS the fan-out signal.

**Verdict key:** `OK` = decision correct + answer delivered · `EXEC-EMPTY` = correct fan-out, empty browser answer (the defect) · `MISSED` = should have fanned out, ran sequential (cheap, un-gated) · `DECISION-WRONG` = fanned out a dependent chain (GAIA fp) · `NOT-RUN` = timed out / no trace.


## Independent family (10)

| Case | Fam | want | decision | br# | joins | join_chars | br c/t | chars | cards | fallback | shot | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FANOUT-independent-L2-decompose-10 | ind | True | fan_out | 3 | 2 | 1873 | 6/6 | 1571 | 0 | False | [png](../../cache/planning_stress/screenshots/FANOUT-independent-L2-decompose-10.png) | **OK** |
| FANOUT-independent-gift-shortlist-03 | ind | True | fan_out | 3 | 1 | 850 | 3/3 | 746 | 0 | False | [png](../../cache/planning_stress/screenshots/FANOUT-independent-gift-shortlist-03.png) | **OK** |
| FANOUT-independent-many-branch-09 | ind | True | fan_out | 6 | 3 | 225 | 6/6 | 225 | 0 | False | [png](../../cache/planning_stress/screenshots/FANOUT-independent-many-branch-09.png) | **OK** |
| FANOUT-independent-multidoc-extract-05 | ind | True | — | — | 0 | — | — | 359 | 4 | False | [png](../../cache/planning_stress/screenshots/FANOUT-independent-multidoc-extract-05.png) | **MISSED (cheap)** |
| FANOUT-independent-multidoc-summary-04 | ind | True | fan_out | 3 | 3 | 359 | 6/6 | 345 | 0 | False | [png](../../cache/planning_stress/screenshots/FANOUT-independent-multidoc-summary-04.png) | **OK** |
| FANOUT-independent-multitab-lookup-07 | ind | True | decline | 0 | 0 | — | — | 644 | 3 | False | [png](../../cache/planning_stress/screenshots/FANOUT-independent-multitab-lookup-07.png) | **MISSED (cheap)** |
| FANOUT-independent-policy-checks-06 | ind | True | fan_out | 3 | 3 | 1442 | 6/6 | 1393 | 0 | False | [png](../../cache/planning_stress/screenshots/FANOUT-independent-policy-checks-06.png) | **OK** |
| FANOUT-independent-restaurant-survey-02 | ind | True | fan_out | 3 | 3 | 495 | 9/9 | 400 | 0 | False | [png](../../cache/planning_stress/screenshots/FANOUT-independent-restaurant-survey-02.png) | **OK** |
| FANOUT-independent-trip-research-01 | ind | True | decline | 0 | 0 | — | — | 498 | 3 | False | [png](../../cache/planning_stress/screenshots/FANOUT-independent-trip-research-01.png) | **MISSED (cheap)** |
| FANOUT-independent-two-branch-08 | ind | True | — | — | 0 | — | — | 349 | 2 | False | [png](../../cache/planning_stress/screenshots/FANOUT-independent-two-branch-08.png) | **MISSED (cheap)** |

## Decline family (10)

| Case | Fam | want | decision | br# | joins | join_chars | br c/t | chars | cards | fallback | shot | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FANOUT-decline-benchmark-then-tune-03 | dec | False | decline | 0 | 0 | — | — | 1218 | 21 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-benchmark-then-tune-03.png) | **OK** |
| FANOUT-decline-fetch-then-transform-04 | dec | False | decline | 0 | 0 | — | — | 253 | 12 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-fetch-then-transform-04.png) | **OK** |
| FANOUT-decline-obvious-chain-07 | dec | False | decline | 0 | 0 | — | — | 1229 | 3 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-obvious-chain-07.png) | **OK** |
| FANOUT-decline-obvious-pipeline-08 | dec | False | decline | 0 | 0 | — | — | 204 | 14 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-obvious-pipeline-08.png) | **OK** |
| FANOUT-decline-pick-then-act-06 | dec | False | decline | 0 | 0 | — | — | 416 | 0 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-pick-then-act-06.png) | **OK** |
| FANOUT-decline-policy-dependent-10 | dec | False | decline | 0 | 0 | — | — | 543 | 0 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-policy-dependent-10.png) | **OK** |
| FANOUT-decline-restaurant-then-route-02 | dec | False | decline | 0 | 0 | — | — | 325 | 6 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-restaurant-then-route-02.png) | **OK** |
| FANOUT-decline-shared-write-05 | dec | False | decline | 0 | 0 | — | — | 725 | 5 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-shared-write-05.png) | **OK** |
| FANOUT-decline-single-multistep-09 | dec | False | decline | 0 | 0 | — | — | 390 | 5 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-single-multistep-09.png) | **OK** |
| FANOUT-decline-trip-dated-01 | dec | False | decline | 0 | 0 | — | — | 479 | 1 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-trip-dated-01.png) | **OK** |

## Fault family (5)

| Case | Fam | want | decision | br# | joins | join_chars | br c/t | chars | cards | fallback | shot | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FANOUT-fault-all-but-one-fail-03 | fau | True | fan_out | 3 | 3 | 727 | 9/9 | 721 | 3 | False | [png](../../cache/planning_stress/screenshots/FANOUT-fault-all-but-one-fail-03.png) | **CONTAMINATED (untrustworthy trace)** |
| FANOUT-fault-join-degraded-04 | fau | True | fan_out | 3 | 3 | 551 | 3/3 | 544 | 0 | False | [png](../../cache/planning_stress/screenshots/FANOUT-fault-join-degraded-04.png) | **OK** |
| FANOUT-fault-one-branch-errors-01 | fau | True | fan_out | 3 | 3 | 797 | 9/9 | 696 | 0 | False | [png](../../cache/planning_stress/screenshots/FANOUT-fault-one-branch-errors-01.png) | **OK** |
| FANOUT-fault-one-branch-times-out-02 | fau | True | fan_out | 3 | 3 | 476 | 9/9 | 503 | 0 | False | [png](../../cache/planning_stress/screenshots/FANOUT-fault-one-branch-times-out-02.png) | **OK** |
| FANOUT-fault-slow-branch-05 | fau | True | fan_out | 3 | 3 | 802 | 3/3 | 785 | 0 | False | [png](../../cache/planning_stress/screenshots/FANOUT-fault-slow-branch-05.png) | **OK** |

## Control family (4)

| Case | Fam | want | decision | br# | joins | join_chars | br c/t | chars | cards | fallback | shot | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FANOUT-control-L0-trivial-01 | con | False | — | — | 0 | — | — | 115 | 0 | False | [png](../../cache/planning_stress/screenshots/FANOUT-control-L0-trivial-01.png) | **OK** |
| FANOUT-control-ambiguous-trivial-04 | con | False | — | — | 0 | — | — | 110 | 2 | False | [png](../../cache/planning_stress/screenshots/FANOUT-control-ambiguous-trivial-04.png) | **OK** |
| FANOUT-control-single-read-03 | con | False | — | — | 0 | — | — | 310 | 11 | False | [png](../../cache/planning_stress/screenshots/FANOUT-control-single-read-03.png) | **OK** |
| FANOUT-control-single-write-02 | con | False | — | — | 0 | — | — | 69 | 1 | False | [png](../../cache/planning_stress/screenshots/FANOUT-control-single-write-02.png) | **OK** |

## Roll-up

- cases total: **29**, ran: **29**, not-run: **0**
- `CONTAMINATED (untrustworthy trace)`: **1**
- `MISSED (cheap)`: **4**
- `OK`: **24**
