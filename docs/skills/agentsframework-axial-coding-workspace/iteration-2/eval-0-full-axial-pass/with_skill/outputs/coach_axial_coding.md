# Coach Axial Coding — iteration-2 eval-0 full pass

Stage-2 (axial) pass over `tests/fixtures/axial_coding_eval/coded_slice.jsonl`
(30 pre_submit coach traces, 21 distinct open codes, 90 code occurrences).
Goal: a partitioned, testable failure taxonomy ready to hand to rubric design.

**Units discipline (quote correctly).** *Traces* = distinct coach turns (N=30).
*Occurrences* = raw code hits (a category's codes can co-occur on one trace, so
occurrences ≥ traces). Prevalence is quoted as **traces / denominator**; occurrence
counts are shown only where they diverge, and never as "N of 30 traces".

---

## 1. Axis partition (the validity precondition)

Every code carries exactly one axis (assigned **by cause**), per `inventory.csv`.

| Axis | # codes | Role |
|------|--------:|------|
| `agent-behavior` | 20 | Real coach reasoning/pedagogy — feeds taxonomy + rubric |
| `environment-confound` | 1 | `truncated-reply` — generation cutoff artifact (validity precondition) |
| `judge-reliability` | 0 | No verdict/label defects were coded in this slice |

`truncated-reply` (3 traces: `05fa7a88`, `1b4ce6ca`, `2dfe11e7`) is
`environment-confound` **by cause** (the reply was cut mid-word by the generator,
not a coach choice). Its **consequence** is decided per-trace at count time — see §4.

`agent_denominator = 30`, `confound_only_excluded = 0`: all three truncated traces
*also* carry an agent-behavior code, so none is a pure-confound drop from the
overall denominator. The confound label still bites the **leak** sub-rate (§4).

---

## 2. Category map (7 agent-behavior categories)

Ran honestly to 7 (target is ~5–6, not a gate). Every category has a `binary_check`
in `categories.csv` and passed `axial_checker.py` (exit 0).

| Category | Polarity | Member codes | Gradient |
|----------|:--------:|--------------|----------|
| **answer-leak** | ± | teaches-rule-no-leak, preserves-the-last-step *(no-leak pole)* → rule-naming-as-leak → leak-strong-implication → hands-over-conclusion | **yes** (how-much-inference-handed-over) |
| **hint-calibration** | ± | right-sizes-the-hint (+), overshoots-the-ask (−) | no |
| **elicitation-quality** | ± | elicits-evidence (+), no-teach-back (−) | no |
| **learner-state-uptake** | ± | builds-on-learner-hypothesis (+), switches-strategy-when-stuck (+), ignores-learner-hypothesis (−) | no |
| **scaffolding-move** | + | gives-concrete-move, names-specific-locus, addresses-real-confusion | no |
| **boundary-holding** | + | resists-answer-begging, declines-to-confirm-answer, redirects-off-topic | no |
| **affective-response** | ± | validates-frustration (+), empty-praise (−) | no |

`answer-leak` is the taxonomy's spine: it is the **±** gradient category, holding both
the no-leak good pole and the three worsening leak rungs. Its `binary_check` records a
check at **each boundary** (`|`-separated in the CSV).

---

## 3. Prevalence — trace counts (quote these as "N/30")

From `axial_matrix.py`. Trace counts are the prevalence numbers; occurrence counts
shown only where they differ.

| Category | Traces | (Occurrences) | Rate over N=30 |
|----------|-------:|--------------:|---------------:|
| scaffolding-move | 21 | 27 | 70% |
| answer-leak | 20 | 24 | 67% |
| elicitation-quality | 15 | 15 | 50% |
| hint-calibration | 9 | 9 | 30% |
| boundary-holding | 6 | 6 | 20% |
| learner-state-uptake | 4 | 4 | 13% |
| affective-response | 2 | 2 | 7% |

> **Watch the unit.** `answer-leak` = **20 traces** (67%), not the 24 *occurrences* —
> quoting 24/30 (80%) would overstate. `scaffolding-move` = **21 traces**, not 27.

`answer-leak` at 20 traces is the *category touch* count (includes the no-leak pole
codes `teaches-rule-no-leak` / `preserves-the-last-step`). The **leak sub-rate** — the
number a rubric actually wants — is smaller and is computed in §4.

---

## 4. The graded leak split + the denominator call (the sharp move)

`answer-leak` is a gradient, so a collapsed rate hides the story. Split by rung
(traces touching each leak rung; the good-pole codes are the "no-leak" bucket):

| Rung (worsening →) | Traces | Note |
|--------------------|-------:|------|
| no-leak pole (teaches-rule / preserves-last-step) | 8 | judgment fully learner-owned |
| rule-naming-as-leak (mildest leak) | 6 | names operative rule, learner still applies it |
| leak-strong-implication | 6 | rule applied to item → ~1 option live |
| hands-over-conclusion (worst) | 4 | answer stated outright |
| **any leak rung** | **12** | union of the three leak rungs |
| **strong-implication or worse** | **6** | the leaks that actually give it away |

**Leak denominator — the straddle rule applied per trace.** Three replies were
truncated (`environment-confound`). For the *leak question* their scorability is
decided by whether the leak was observable **before** the cut:

- `1b4ce6ca` — leaked (`rule-naming-as-leak`) before the cut → observed → **keep**.
- `2dfe11e7` — leaked (`strong-implication`+`hand-over`) before the cut → **keep**.
- `05fa7a88` — cut off **before** any leak; coder withheld the leak code (item is
  rhetoric, "naming clause type likely leaves options live"). Leak status = **unknown**,
  not "no" → **drop from the leak denominator** (unscorable for this question).

So the honest leak-rate is:

> **any-leak = 12 / 29 (41%)**, and **strong-implication-or-worse = 6 / 29 (21%)**.

Not 12/30 (folds in the unscorable `05fa7a88`) and not 10/27 (would wrongly over-drop
the two traces that leaked before their cut). Give **both** numbers to rubric design:
the coarse 41% and the "actually gives it away" 21%.

---

## 5. Minimal pairs (relational gold)

From `axial_minimal_pairs.py` (axis-blind v1 — divergences below are all confirmed on
**agent-behavior** codes, i.e. real, not confound/judge noise). These same-prompt,
divergent-behavior pairs prove the failure is **contingent, not forced** by the prompt —
the strongest evidence a rubric author can get.

**Pair A — "if I had to explain this sentence to a friend, I honestly couldn't"**
(the Feynman moment). Same learner utterance, two leak rungs:
- `0d3f493f` → `leak-strong-implication` + `hands-over-conclusion` (states the crux)
- `104ba6ae` → `rule-naming-as-leak` (names rule, milder)
→ The leak severity is a coach choice on identical input. **Gold for the answer-leak
gradient rubric.**

**Pair B — "I think it's between B and C"** (learner discloses a hypothesis).
Same input, opposite `learner-state-uptake` polarity:
- `1e28adc2` → `ignores-learner-hypothesis` (restarts its script)
- `2b4cf8ce` → `builds-on-learner-hypothesis` (works inside the B/C shortlist)
→ Clean **± minimal pair** for learner-state-uptake — the positive mirror is *available*
on the same utterance, so ignoring it is a real miss, not a forced move.

**Pair C — "give me a hint but a small one"** (3 members). All hold
`right-sizes-the-hint`; they diverge on whether a probe is added
(`elicits-evidence` present in `0b9d1f60`/`2f19d809`, absent in `3ce9e4a8`). Divergence is
on the *second-order* elicitation move, not on calibration — a softer pair; useful for
elicitation-quality, weaker for hint-calibration.

**Pair D — "if I swap the underlined part … what should I be checking?"** Both members
(`1b4ce6ca`, `3108cc62`) share `rule-naming-as-leak` + `gives-concrete-move`; the only
divergence is `truncated-reply` (environment-confound). **Not a minimal pair** — the
agent behavior is identical; the split is a sandbox artifact. Excluded per the
axis-blind-v1 caveat.

---

## 6. Template-economy cross-cut (memo signal, not a code)

Coder memos flag heavy **template reuse**: the "cover-the-phrase / of-the-runners"
subject probe recurs near-verbatim across `0b9d1f60`, `102f9f57`, `1e28adc2` — and in
`1e28adc2` it fires *unconditioned on the learner's disclosed hypothesis*
(→ `ignores-learner-hypothesis`). Likewise a "return-crux-leader" template cluster and an
"arithmetic-detour redirect" family. **Implication for rubric design:** canned replies can
score well on `scaffolding-move` while failing `learner-state-uptake` — the two must be
scored independently, or template reuse will pass a lumped rubric.

**Dataset hygiene flags (from memos, not coach failures).** Multiple memos flag
`question_id`↔item churn (the same item content appears under different `question_id`s,
and "redundancy" framing recurs across 5 of 6 ids). This is a **generator/item-bank**
issue to fix before the corpus is used as a gold set — it is *not* an agent behavior and
carries no axis here.

---

## 7. Emit — rubric-assertion candidates (for rubric design)

Each traces to a partitioned, gated category. Prose, human judgment.

1. **[answer-leak, graded]** In `pre_submit`, the reply MUST leave the deciding
   judgment to the learner. Fail at each rung: names the operative rule for the item
   (mild) / applies the rule so ~1 option is implied (strong) / states the answer outright
   (worst). *Exemplars:* `12cb0896` (pure rule-naming), `0d3f493f` (hand-over),
   `0f24f449` (clean no-leak). *Gradient pair:* Pair A.
2. **[boundary-holding]** An answer-begging / confirm-my-pick / off-topic bid MUST be
   declined without leaking and without scolding. *must_catch:* `06c2aa58`, `2da8c5cd`,
   `33a9fcfa`. *failure_if:* refusal that then leaks (`2c21ab67`, `48129021` — refuse by
   name, then hand over the crux in Socratic clothing).
3. **[learner-state-uptake]** When the learner discloses a hypothesis/strategy state,
   the reply MUST acknowledge and build on it rather than restart a fixed script.
   *± pair:* Pair B (`1e28adc2` fail vs `2b4cf8ce` pass).
4. **[hint-calibration]** A scoped ask (small hint / name-only) MUST NOT be exceeded with
   unrequested item content. *failure_if:* `3f79f49c` (name+definition+application+answer
   for a name-only ask). *must_catch:* `47346e20`.
5. **[elicitation-quality]** A volunteered teach-back MUST be elicited, not answered for
   the learner. *failure_if:* `no-teach-back` on a volunteered Feynman moment (`0d3f493f`,
   `08…`); *pass:* `elicits-evidence` with a genuine probe.
6. **[affective-response]** Praise MUST be specific and earned; generic praise that
   ratifies unverified eliminations is a fail. *failure_if:* `3fec3834` (empty-praise +
   implicitly ratifies uninspected eliminations).

Judge test-case candidates: the four minimal-pair members (A/B) are the highest-value
seed cases — same prompt, adjudicated divergence — plus the two "refuse-then-leak"
boundary cases (`2c21ab67`, `48129021`) as hard negatives.
