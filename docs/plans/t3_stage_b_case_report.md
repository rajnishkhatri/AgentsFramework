# T3 Stage B — Case-by-case report (DOM ⨝ Langfuse)

Each fan-out case joined on the deterministic `trace_id`: the **browser** result (`cache/planning_stress/ui_batch.jsonl`, latest run per case) next to the **graph** carriers pulled live from Langfuse. The join makes the Stage-B split legible — a correct server-side fan-out *decision* whose *answer* never reached the browser.

> `chars`/`cards` = browser-side; `decision`/`br#`/`joins`/`join_chars`/`br c/t` = graph-side (Langfuse); `want` = corpus expectation. `joins`>1 = fanned out again under reflexion. These traces carry no `delegation_requested` obs — the `decision` + a real `fanout_join` carrier IS the fan-out signal.

**Verdict key:** `OK` = decision correct + answer delivered · `EXEC-EMPTY` = correct fan-out, empty browser answer (the defect) · `MISSED` = should have fanned out, ran sequential (cheap, un-gated) · `DECISION-WRONG` = fanned out a dependent chain (GAIA fp) · `NOT-RUN` = timed out / no trace.


## Independent family (10)

| Case | Fam | want | decision | br# | joins | join_chars | br c/t | chars | cards | fallback | shot | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FANOUT-independent-L2-decompose-10 | ind | True | fan_out | 3 | 2 | 1771 | 3/3 | 47 | 0 | True | [png](../../cache/planning_stress/screenshots/FANOUT-independent-L2-decompose-10.png) | **EXEC-EMPTY (decision ok, answer lost)** |
| FANOUT-independent-gift-shortlist-03 | ind | True | fan_out | 3 | 1 | 875 | 3/3 | 47 | 0 | True | [png](../../cache/planning_stress/screenshots/FANOUT-independent-gift-shortlist-03.png) | **EXEC-EMPTY (decision ok, answer lost)** |
| FANOUT-independent-many-branch-09 | ind | True | fan_out | 6 | 3 | 217 | 6/6 | 47 | 0 | True | [png](../../cache/planning_stress/screenshots/FANOUT-independent-many-branch-09.png) | **EXEC-EMPTY (decision ok, answer lost)** |
| FANOUT-independent-multidoc-extract-05 | ind | True | — | — | 0 | — | — | 363 | 4 | False | [png](../../cache/planning_stress/screenshots/FANOUT-independent-multidoc-extract-05.png) | **MISSED (cheap)** |
| FANOUT-independent-multidoc-summary-04 | ind | True | fan_out | 3 | 3 | 265 | 6/6 | 45 | 1 | False | [png](../../cache/planning_stress/screenshots/FANOUT-independent-multidoc-summary-04.png) | **CONTAMINATED (untrustworthy trace)** |
| FANOUT-independent-multitab-lookup-07 | ind | True | fan_out | 3 | 3 | 755 | 3/3 | 47 | 0 | True | [png](../../cache/planning_stress/screenshots/FANOUT-independent-multitab-lookup-07.png) | **EXEC-EMPTY (decision ok, answer lost)** |
| FANOUT-independent-policy-checks-06 | ind | True | fan_out | 3 | 3 | 1382 | 9/9 | 47 | 0 | True | [png](../../cache/planning_stress/screenshots/FANOUT-independent-policy-checks-06.png) | **EXEC-EMPTY (decision ok, answer lost)** |
| FANOUT-independent-restaurant-survey-02 | ind | True | fan_out | 3 | 3 | 492 | 9/9 | 47 | 0 | True | [png](../../cache/planning_stress/screenshots/FANOUT-independent-restaurant-survey-02.png) | **EXEC-EMPTY (decision ok, answer lost)** |
| FANOUT-independent-trip-research-01 | ind | True | decline | 3 | 4 | 982 | 3/3 | 511 | 3 | False | [png](../../cache/planning_stress/screenshots/FANOUT-independent-trip-research-01.png) | **CONTAMINATED (untrustworthy trace)** |
| FANOUT-independent-two-branch-08 | ind | True | — | — | 0 | — | — | 546 | 2 | False | [png](../../cache/planning_stress/screenshots/FANOUT-independent-two-branch-08.png) | **MISSED (cheap)** |

## Decline family (10)

| Case | Fam | want | decision | br# | joins | join_chars | br c/t | chars | cards | fallback | shot | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FANOUT-decline-benchmark-then-tune-03 | dec | False | decline | 0 | 0 | — | — | 168 | 6 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-benchmark-then-tune-03.png) | **OK** |
| FANOUT-decline-fetch-then-transform-04 | dec | False | decline | 0 | 0 | — | — | 772 | 22 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-fetch-then-transform-04.png) | **OK** |
| FANOUT-decline-obvious-chain-07 | dec | False | decline | 0 | 0 | — | — | 424 | 4 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-obvious-chain-07.png) | **OK** |
| FANOUT-decline-obvious-pipeline-08 | dec | False | — | — | 0 | — | — | 0 | 0 | False | — | **OK** |
| FANOUT-decline-pick-then-act-06 | dec | False | decline | 0 | 0 | — | — | 430 | 0 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-pick-then-act-06.png) | **OK** |
| FANOUT-decline-policy-dependent-10 | dec | False | decline | 0 | 0 | — | — | 520 | 0 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-policy-dependent-10.png) | **OK** |
| FANOUT-decline-restaurant-then-route-02 | dec | False | decline | 0 | 0 | — | — | 296 | 1 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-restaurant-then-route-02.png) | **OK** |
| FANOUT-decline-shared-write-05 | dec | False | decline | 0 | 0 | — | — | 189 | 3 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-shared-write-05.png) | **OK** |
| FANOUT-decline-single-multistep-09 | dec | False | — | — | — | — | — | — | — | — | — | **NOT-RUN** |
| FANOUT-decline-trip-dated-01 | dec | False | decline | 0 | 0 | — | — | 418 | 1 | False | [png](../../cache/planning_stress/screenshots/FANOUT-decline-trip-dated-01.png) | **OK** |

## Fault family (5)

| Case | Fam | want | decision | br# | joins | join_chars | br c/t | chars | cards | fallback | shot | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FANOUT-fault-all-but-one-fail-03 | fau | True | — | — | — | — | — | — | — | — | — | **NOT-RUN** |
| FANOUT-fault-join-degraded-04 | fau | True | — | — | — | — | — | — | — | — | — | **NOT-RUN** |
| FANOUT-fault-one-branch-errors-01 | fau | True | — | — | — | — | — | — | — | — | — | **NOT-RUN** |
| FANOUT-fault-one-branch-times-out-02 | fau | True | — | — | — | — | — | — | — | — | — | **NOT-RUN** |
| FANOUT-fault-slow-branch-05 | fau | True | — | — | — | — | — | — | — | — | — | **NOT-RUN** |

## Control family (4)

| Case | Fam | want | decision | br# | joins | join_chars | br c/t | chars | cards | fallback | shot | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FANOUT-control-L0-trivial-01 | con | False | — | — | — | — | — | — | — | — | — | **NOT-RUN** |
| FANOUT-control-ambiguous-trivial-04 | con | False | — | — | — | — | — | — | — | — | — | **NOT-RUN** |
| FANOUT-control-single-read-03 | con | False | — | — | — | — | — | — | — | — | — | **NOT-RUN** |
| FANOUT-control-single-write-02 | con | False | — | — | — | — | — | — | — | — | — | **NOT-RUN** |

## Roll-up

- cases total: **29**, ran: **19**, not-run: **10**
- `CONTAMINATED (untrustworthy trace)`: **2**
- `EXEC-EMPTY (decision ok, answer lost)`: **6**
- `MISSED (cheap)`: **2**
- `NOT-RUN`: **10**
- `OK`: **9**
