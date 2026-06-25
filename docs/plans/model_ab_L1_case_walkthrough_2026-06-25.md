# Model A/B — GEN-L1 case-by-case answer walkthrough (2026-06-25)

## 1. What this is

A **read-only, case-by-case forensic walkthrough** of an offline model A/B
answer-quality sweep over the 10 deterministic **GEN-L1** file-IO tasks. For every
case, for every arm that ran it, this report shows the task input, the true answer,
the model's verbatim final output, whether the answer was graded correct/wrong, and
the *reasoning trajectory* that produced it — grounded in the local black-box
carriers (planning depth, model-selection rationale, every tool call + its result,
and the GoalJudge verdict).

- **Corpus**: `cache/model_ab_answer/l1_full.jsonl` (hash `686c418e50440905`), the 10
  rows of `frontend/e2e/fixtures/model_ab_corpus.json` with `family=="general"` and
  `difficulty=="L1"`. Each prompt reads/writes files under `/workspace/…`; the batch
  runner rewrites that prefix to `<repo>/workspace/`
  (`run_goaljudge_synthetic_batch._normalize_prompt_for_batch`) and the file-IO tool
  sandboxes to that absolute `WORKSPACE_DIR`. The fixtures are seeded with known
  content by `scripts/seed_model_ab_workspace.py::_seed` (the ground-truth answers).

- **Arms** (4 arm-runs across two completed run directories; `gpt-4o-mini` baseline
  appears in both):

  | run dir | baseline arm | candidate arm |
  |---|---|---|
  | `cache/model_ab/l1_haiku_081842/` | `gpt-4o-mini` | `claude-haiku-4-5` |
  | `cache/model_ab/l1_flash_082415/` | `gpt-4o-mini` | `deepseek-v4-flash` |

- **Data sources** (all local, already written — nothing was re-driven for this report):
  - `…/<arm>/evals.log` — JSONL eval-capture; `target=="call_llm"` records carry the
    final `ai_response`, `model`, `tokens_in/out`, `cost_usd`, `latency_ms`, `step`;
    `target=="goal_judge"` records carry `goal_met`/`criteria_met`/`per_criterion`/`rationale`.
  - `…/<arm>/recordings/<workflow_id>/trace.jsonl` — black-box `TraceEvent` JSONL:
    `step_planned`, `model_selected`, `tool_called`, `error_occurred`, `task_completed`.
  - `…/model_ab_report.{json,md}` — the harness verdict + answer block.
  - Grading logic: `scripts/model_ab_answer_score.py::_grade` (numeric = *any* number in
    the answer within `tol`; substring = every expected token must appear, case- and
    separator-insensitive).

- **The case → eval-record join**: `task_id == uuid5(NAMESPACE_DNS, case_id).hex`,
  which is also the workflow_id / black-box recording dir name and the would-be
  Langfuse trace key. The trace ref is given per case below.

### Langfuse limitation (read honestly)

`LANGFUSE_HOST/PUBLIC_KEY/SECRET_KEY` are set in `.env`, but these are **offline**
batch runs with the known **Hermes-path trace-join gap**: offline runs do not
reliably emit a joinable `mem:`/workflow-keyed trace, so a Langfuse lookup by the
`uuid5` trace id is **not guaranteed to resolve** and was **not** used as a source
here. **Every reasoning claim in this report is sourced from the LOCAL black-box
`trace.jsonl` carriers and the local `evals.log`**, which are complete. The per-case
"Trace ref" is the `uuid5` hex so a reader *can attempt* a Langfuse lookup; no
Langfuse-sourced content is asserted, and none was fabricated.

---

## 2. Summary (recomputed via `model_ab_answer_score.score_answers` over each arm's `evals.log`)

| arm | accuracy | correct/n | outcome breakdown | total $ | $/task |
|---|---|---|---|---|---|
| `gpt-4o-mini` (in haiku run) | **0.80** | 8/10 | 8 correct, 2 wrong | 0.010312 | 0.001031 |
| `claude-haiku-4-5` | **1.00** | 10/10 | 10 correct | 0.110585 | 0.011058 |
| `gpt-4o-mini` (in flash run) | **0.60** | 6/10 | 6 correct, 4 wrong | 0.011177 | 0.001118 |
| `deepseek-v4-flash` | **0.90** | 9/10 | 9 correct, 1 wrong | 0.018744 | 0.001874 |

Both run dirs returned **PROMOTE** (haiku Δ+0.2, flash Δ+0.3). Cost is surfaced, not
auto-gated: Haiku is **~10.7×** the baseline per task; Flash is **~1.7×**.

> **The single dominant signal**: the *same* `gpt-4o-mini` baseline scored 0.80 in one
> run and 0.60 in the other on identical fixtures. That ~stochastic 2-case swing on a
> 10-case corpus is itself the loudest caveat — see §4. The candidate uplift is real
> and rooted in a concrete capability gap (path handling), but the *magnitude* of any
> single Δ is inside the noise band of a 10-task corpus.

---

## 3. Case-by-case walkthrough

Notation per case: **Input** (prompt + true fixture/expected), then one block per
arm-run with **Output** (verbatim, trimmed), **Answer quality**, **Reasoning**
(carrier-grounded), and the **Trace ref**.

The recurring root cause to keep in mind: `gpt-4o-mini` calls tools with the **literal
`/workspace/…` path**, which the FileIO sandbox rejects with
`Path … is outside workspace boundary` (the OS root `/workspace` ≠ the repo
`workspace/` dir). Both candidate models instead call with the **rewritten absolute
`/Users/.../agent/workspace/…` path** and succeed. This one behavior explains almost
every baseline miss below. (Carrier: `tool_called.args.path` vs `error_occurred.error`.)

---

### GEN-L1-read-sum-01 — sum of three files
**Trace ref**: `991f78b375dd513abc3ea9f669545833`
**Input**: *"Read the three files /workspace/nums/a.txt, …/b.txt and …/c.txt — each holds a single integer. Report their sum."* Fixtures: `7`, `12`, `23`. **Expected (numeric): 42.**

**`gpt-4o-mini` (haiku run + flash run — identical failure)** — **WRONG (no usable answer)**
> "I attempted to read the three files specified, but I encountered errors indicating that the paths provided are outside the allowed workspace boundary. … I cannot provide the sum…"

Reasoning: depth `L0`. Three `file_io/read` calls on `/workspace/nums/{a,b,c}.txt`, all
three returned `Value error, Path /workspace/nums/a.txt is outside workspace boundary`
(carrier: 3× `error_occurred`). A second `step_planned` fired with `no_progress=true,
repeats=3`; the loop terminated `no_progress`. `task_completed`: `outcome=partial,
goal_met=false, score=0.714, criteria_met=0.333`. GoalJudge marked both file-read and
"report sum" criteria `met=false` (evidence: "paths … outside the allowed workspace
boundary"), but the third criterion "internally consistent / directly responds"
`met=true` and `graceful_failure=true` — it failed *honestly*. Genuine capability miss:
never retried with the absolute path.

**`claude-haiku-4-5`** — **CORRECT (42)**
> "I've read all three files: a.txt contains 7, b.txt contains 12, c.txt contains 23 … 7 + 12 + 23 = 42 — FINAL ANSWER: 42"

Reasoning: depth `L0`, 3 `file_io/read` on the **absolute** `/Users/.../workspace/nums/*.txt`,
**zero errors**, `outcome=success, goal_met=true, criteria_met=1.0`. Clean.

**`deepseek-v4-flash`** — **CORRECT (42)**
> "The sum of the integers is **42** (7 + 12 + 23)."

Reasoning: same as Haiku — 3 absolute-path reads, no errors, `success/goal_met=true`.

---

### GEN-L1-lookup-format-02 — email domain
**Trace ref**: `fd46d24351825792988b2d974d7c4a03`
**Input**: read `/workspace/contact.txt`, report the domain after `@`. Fixture email `dana.lee@example.com`. **Expected (substring): `example.com`.**

**`gpt-4o-mini` (both runs)** — **CORRECT (`example.com`)**
> "…the email address … is 'dana.lee@example.com'. … the domain is **example.com** — FINAL ANSWER: example.com"

Reasoning: depth `L1`. Here the baseline used a **`shell` `cat`** with the absolute path
(`cat /Users/.../workspace/contact.txt`) which **succeeded**, so it had the content —
then wasted 3 `file_io/write` calls on `/workspace/output.txt` etc. (all boundary
errors), but the read had already given it the answer. `task_completed=partial,
no_progress`, yet the answer text is correct → graded **correct**. Note the mismatch:
the *task* succeeded answer-wise while the *trajectory* logged `partial/no_progress`.

**`claude-haiku-4-5`** — **CORRECT (`example.com`)**
> "FINAL ANSWER: … domain … is **example.com** … the email address is `dana.lee@example.com` …"

Reasoning: `L1`, read `contact.txt` (absolute) OK, then tried a `python` tool (returns
`Unknown tool 'python'`, 2 errors) and a `shell python -c` — unnecessary, since it
already had the email. Answer correct. GoalJudge `goal_met=false, criteria_met=0.5`
(it dinged the extra failed tool calls / "wrote to output" expectation), but the
**answer scorer** only grades the final text → correct.

**`deepseek-v4-flash`** — **CORRECT (`example.com`)**
> "FINAL ANSWER: example.com"

Reasoning: cleanest of all — read `contact.txt`, one stray `/workspace/output.txt`
write error, then the terse correct answer.

---

### GEN-L1-count-lines-03 — non-empty line count
**Trace ref**: `b6caf46321c35e339fe69d02733e3daa`
**Input**: count non-empty lines in `/workspace/log.txt`. Fixture has 4 non-empty lines among blanks. **Expected (numeric): 4.**

**`gpt-4o-mini` (haiku run)** — **CORRECT (4)**
> "FINAL ANSWER: The log file contains 4 non-empty lines."

Reasoning: `L0`. Ran `shell grep -c . /Users/.../workspace/log.txt` (absolute → succeeded,
returned 4), then 3 failed `/workspace/output.txt` writes. Answer correct;
`goal_met=true, criteria_met=1.0` even though terminated `no_progress`.

**`gpt-4o-mini` (flash run)** — **WRONG (no answer)**
> "I was unable to access the file … to count the non-empty lines due to restrictions on file access. … you would typically use a command like `grep -cve …`"

Reasoning: **This is the divergence that explains the 0.80 vs 0.60 split.** Same model,
same fixture, *different tool choices this run*: it ran `grep -cve '^[[:space:]]*$' …`
which the shell guard rejected as a **shell metacharacter** (`Value error, Shell
metacharacter de…`), retried the same/`/workspace/log.txt` variants, and racked up
**6 errors**. It never fell back to a plain `grep -c .`. Gave up with no number →
**wrong**. A non-deterministic tool-formulation failure, not a different capability.

**`claude-haiku-4-5`** — **CORRECT (4)**
> "FINAL ANSWER: The file contains **4 non-empty lines** … The `grep -c .` command counts all lines that contain at least one character…"

Reasoning: read `log.txt` (absolute) then `grep -c .` (absolute) — both clean, `success/
goal_met=true`. Chose the metacharacter-free `grep -c .`, avoiding the trap the baseline
fell into.

**`deepseek-v4-flash`** — **CORRECT (4)**
> "**Answer:** The file contains **4** non-empty lines … (The file has 7 lines total, but 3 of them are blank/empty.)"

Reasoning: read `log.txt`, `wc -l` then `grep -c '.'` (absolute, allowed), `success/
goal_met=true, score=0.885`. Correct and well-explained.

---

### GEN-L1-pick-max-04 — highest-scoring name
**Trace ref**: `54fc53a1953b5919b647cbc2b5b03ed2`
**Input**: read `/workspace/scores.csv`, report the name with the highest score. Fixture: Alex 71, Priya 93, JordanK 88, Sam 64. **Expected (substring): `Priya`.**

**`gpt-4o-mini` (both runs)** — **CORRECT (`Priya`)**
> "…the name with the highest score is **Priya**, with a score of **93**. FINAL ANSWER: Priya, 93"

Reasoning: `L0`, `shell cat …/scores.csv` (absolute → succeeded), then failed
`/workspace/…` writes. Correct answer despite `partial/no_progress`; `goal_met=true`.

**`claude-haiku-4-5`** — **CORRECT (`Priya`)**
> "… Priya: 93 … **FINAL ANSWER:** Priya has the highest score with 93 points."

Reasoning: single clean `file_io/read` of `scores.csv` (absolute), `success/goal_met=true,
criteria_met=1.0`. GoalJudge evidence: "the final answer correctly identifies Priya as
having the highest score."

**`deepseek-v4-flash`** — **CORRECT per scorer, but the model MISREAD the task** ⚠️
> "**Answer:** 2 people (Priya with 93 and JordanK with 88)."

Reasoning: depth `L0` but a **7-tool thrash**: it read the CSV, then tried a `python`
tool (`Unknown tool 'python'`), a `python -c` shell with an embedded walrus/`exec` hack
(shell-rejected), wrote+ran a `count_scores.py`, then `rm`'d it. Crucially its code
**counted people with score > 80**, i.e. it answered a *different question* ("how many
scored above 80") — GoalJudge caught this exactly: `goal_met=false, criteria_met=0.0`,
evidence "reported two names (Priya and JordanK) instead of the single name with the
highest score." **The answer scorer still marked it CORRECT** because the substring
`priya` is present. **Scorer false-positive** (see §4) — the only one in the sweep, and
it flatters Flash's 0.90.

---

### GEN-L1-convert-unit-05 — miles → km, 1 dp
**Trace ref**: `1ccbe08268105e8ba1603ac003313794`
**Input**: read miles from `/workspace/distance.txt`, convert (1 mi = 1.60934 km), report rounded to 1 dp. Fixture `5`. **Expected (numeric): 8.0, tol 0.1** (absorbs an unrounded 8.0467).

**`gpt-4o-mini` (both runs)** — **WRONG (no answer)**
> "I attempted to read the distance … but I encountered repeated errors indicating that the path is outside the allowed workspace boundary. … I cannot perform the conversion…"

Reasoning: `L1`, 3× `file_io/read` on `/workspace/distance.txt` → 3 boundary errors,
`no_progress`. `goal_met=false, criteria_met=0.0` (haiku run) / `0.0` (flash run). Pure
path-handling miss; never produced a number. Honest give-up.

**`claude-haiku-4-5`** — **CORRECT (within tol)**
> "**FINAL ANSWER:** The distance file contains **5 miles**, which converts to **8.0467 kilometres**. (1 mile = 1.60934 km)"

Reasoning: read `distance.txt` (absolute, got `5`), tried `python -c` (shell-rejected
metachar), wrote+ran a `conversion.py`. Reported **8.0467**, *not* rounded to 1 dp.
GoalJudge: `goal_met=false, criteria_met=0.5` — criteria "read" and "convert" `met=true`,
but "report rounded to one decimal place" `met=false` (evidence: "reported as 8.0467 …
not rounded"). **The answer scorer passes it anyway** because `tol=0.1` absorbs 8.0467
(|8.0467−8.0|=0.0467 ≤ 0.1). So this is graded correct by a *deliberate* tolerance,
even though the model technically didn't follow the rounding instruction. Defensible
(it got the magnitude right) but worth flagging: GoalJudge and the answer scorer
disagree on this row.

**`deepseek-v4-flash`** — **WRONG** (the only candidate miss in the whole sweep)
> "**FINAL ANSWER:** I read the distance file … and found the value **5**. … assuming kilometers, common equivalents include: ~50-minute walk … Task complete."

Reasoning: read `distance.txt` (got `5`), used a `think` tool, then wrote a
`distance_analysis.txt` — but **never applied the 1.60934 conversion**. It hallucinated
that the `5` "could represent various units" and spun off walk/bike/drive trivia. No
number near 8.0 appears → **wrong**. GoalJudge agrees: `goal_met=false, criteria_met=0.25`,
evidence "did not perform any conversion … did not report any converted distance."
A genuine instruction-following + reasoning failure, distinct from the baseline's
path-failure on the same case.

---

### GEN-L1-write-readback-06 — write 'ready', read back
**Trace ref**: `e7942804dc7552e8836b73bace789774`
**Input**: write `ready` to `/workspace/status.txt`, read back, confirm. (Not pre-seeded — the task is to create it.) **Expected (substring): `ready`.**

**`gpt-4o-mini` (both runs)** — **CORRECT per scorer, but the write FAILED** ⚠️
> "I attempted to write the word 'ready' to the file … but I encountered errors indicating that the path is outside the allowed workspace boundary. … I cannot confirm whether the file contains the word 'ready'."

Reasoning: `L1`, `file_io/write` + `file_io/read` on `/workspace/status.txt` → boundary
errors, `no_progress`; `goal_met=false, criteria_met=0.333`. **The model never wrote the
file**, yet the answer scorer marks it **correct** because the literal token `'ready'`
appears in the prose ("write the word 'ready'"). **Scorer false-positive** — substring
matching on a self-referential prompt word (see §4). This inflates *both* baseline runs.

**`claude-haiku-4-5`** — **CORRECT (genuinely)**
> "I've successfully written 'ready' to … status.txt and confirmed that it contains the text \"ready\". FINAL ANSWER: … written … and verified."

Reasoning: `file_io/write` then `file_io/read` on the **absolute** status.txt, no errors,
`success/goal_met=true, criteria_met=1.0, score=0.876`. The write actually happened.

**`deepseek-v4-flash`** — **CORRECT (genuinely)**
> "FINAL ANSWER: The word **'ready'** has been successfully written to … status.txt and verified — reading it back shows `\"ready\"`. ✅"

Reasoning: it fumbled first — `ls /workspace/` and a couple of `ls …workspace …; echo
EXIT` shell probes (3 `exit code 1` errors while it figured out the path) — then wrote
and read the absolute status.txt successfully. `success/goal_met=true, criteria_met=1.0`.

---

### GEN-L1-extract-field-13 — JSON name field
**Trace ref**: `126800f164fe51fba5d068b24fc8834f`
**Input**: read `/workspace/profile.json`, report `name`. Fixture `{"name":"Morgan Avery",…}`. **Expected (substring): `Morgan Avery`.**

**`gpt-4o-mini` (both runs)** — **CORRECT (`Morgan Avery`)**
> "The value of the 'name' field … is \"Morgan Avery\". FINAL ANSWER: Morgan Avery"

Reasoning: `L0`, `shell cat …/profile.json` (absolute → succeeded) gave the content;
then failed `/workspace/output.txt` writes. Answer correct; `goal_met=true`.

**`claude-haiku-4-5`** — **CORRECT**
> "FINAL ANSWER: … the 'name' field … is **\"Morgan Avery\"**."

Reasoning: single clean `file_io/read` of profile.json (absolute), `success/goal_met=true,
criteria_met=1.0`.

**`deepseek-v4-flash`** — **CORRECT**
> "**FINAL ANSWER:** ```json { \"name\": \"Morgan Avery\", \"role\": \"engineer\", \"id\": 7 } ```"

Reasoning: single clean absolute read, `success/goal_met=true`. It echoed the whole
object rather than just the field, but `Morgan Avery` is present → correct.

---

### GEN-L1-sort-list-14 — sort words alphabetically
**Trace ref**: `0613cbe527e45056878aed74ff044bc4`
**Input**: read `/workspace/words.txt` (one word/line), report sorted comma-separated. Fixture `cherry,banana,date,apple`. **Expected (substring tokens): `apple, banana, cherry, date`** (token-set match, order/separator-insensitive).

**`gpt-4o-mini` (haiku run)** — **CORRECT**
> "The words … have been sorted … ```apple,banana,cherry,date``` FINAL ANSWER: … written to the output file."

Reasoning: `L0`. Tried `cat … | sort | tr '\n' ','` (**shell metacharacter rejected** —
pipes), then `file_io/read` of words.txt (absolute → succeeded), `ls`, etc. Despite the
trajectory ending `outcome=success` but `goal_met=false, criteria_met=0.0` (GoalJudge
considered the file-write part unmet), the final prose contains all four sorted tokens
→ **scorer correct**. Another answer-vs-GoalJudge disagreement.

**`gpt-4o-mini` (flash run)** — **WRONG (no answer)**
> "I was unable to access the file … or any related files in the workspace. … I cannot provide the sorted list…"

Reasoning: this run it leaned on `cat … | sort | tr | sed` (pipe/metachar rejected), then
`cat /workspace/words.txt` and `ls /workspace` (boundary), then `state_file` list/read
calls — **6 errors**, never read the file successfully, gave up. The second
non-deterministic baseline divergence behind the 0.80→0.60 gap (this case + count-lines-03
flip from correct to wrong between the two runs).

**`claude-haiku-4-5`** — **CORRECT**
> "FINAL ANSWER: … sorted alphabetically: 1. apple 2. banana 3. cherry 4. date … saved to … sorted_words.txt"

Reasoning: read words.txt (absolute), tried `python` (Unknown tool) and `python -c` and
a written `sort_words.py` (4 errors total), but ultimately listed all four tokens in
order. `outcome=success, goal_met=false, criteria_met=0.0` (GoalJudge unhappy with the
file-write evidence) — yet the answer text is right → scorer correct.

**`deepseek-v4-flash`** — **CORRECT**
> "FINAL ANSWER: … sorted alphabetically and written to … sorted_words.txt … ```apple\nbanana\ncherry\ndate```"

Reasoning: read words.txt, some `pwd && ls` probes (one rejected as `Command 'pwd' not
in allow…`), wrote+ran `sort_words.py`, read back `sorted_words.txt`. All four tokens
present, in order → correct. `goal_met=false, criteria_met=0.0` again on the
file-write criterion, scorer correct on the text.

---

### GEN-L1-bool-check-15 — even or odd
**Trace ref**: `eaab788c3c4750438f3da4d2628a9c55`
**Input**: read integer in `/workspace/n.txt`, report even/odd. Fixture `17`. **Expected (substring): `odd`.**

**`gpt-4o-mini` (both runs)** — **WRONG (no answer)**
> "I was unable to access the file … due to workspace boundary restrictions. … If you can provide the integer directly, I can help…"

Reasoning: `L0`, `file_io/read /workspace/n.txt` → boundary errors, `no_progress`. Never
saw `17`, never said even/odd. `goal_met=false, criteria_met=0.5`. Path-handling miss.

**`claude-haiku-4-5`** — **CORRECT**
> "The file contains the integer **17**. … 17 ÷ 2 = 8 remainder 1 … FINAL ANSWER: The integer 17 is **odd**."

Reasoning: single clean absolute read, `success/goal_met=true, criteria_met=1.0`.

**`deepseek-v4-flash`** — **CORRECT**
> "**FINAL ANSWER:** The integer in the file is **17**, which is **odd**. The result has been written to `result.txt`."

Reasoning: read n.txt (absolute), one stray `/workspace/result.txt` write error then
the absolute write, `success/goal_met=true, criteria_met=1.0`.

---

### GEN-L1-first-match-16 — first line containing 'denied'
**Trace ref**: `94fb54f779235dca8351edfc6c32f594`
**Input**: read `/workspace/access.log`, report first line containing `denied`. First match: `POST /admin 403 denied for user bob`. **Expected (substring tokens): `denied for user bob`.**

**`gpt-4o-mini` (both runs)** — **CORRECT**
> "The first line that contains the word 'denied' … ```POST /admin 403 denied for user bob``` …"

Reasoning: `L0`, `shell grep -m 1 'denied' /Users/.../workspace/access.log` (absolute →
succeeded), then failed `/workspace/output.txt` writes. Correct line quoted; `goal_met=true`.

**`claude-haiku-4-5`** — **CORRECT**
> "FINAL ANSWER: … ```POST /admin 403 denied for user bob```"

Reasoning: single clean `file_io/read` of access.log (absolute), `success/goal_met=true,
criteria_met=1.0`.

**`deepseek-v4-flash`** — **CORRECT**
> "The first line in the file that contains the word 'denied' is: **POST /admin 403 denied for user bob**"

Reasoning: single clean absolute read, `success/goal_met=true, criteria_met=1.0`.

---

## 4. Cross-cutting findings (honest + critical)

1. **The baseline's dominant failure mode is a single, mechanical bug, not weak
   reasoning: `gpt-4o-mini` calls tools with the literal `/workspace/…` path.** The
   FileIO sandbox rejects it (`Path … is outside workspace boundary`) and the model
   *gives up rather than retrying with the absolute path*. Every clean baseline miss
   (read-sum-01, convert-05, bool-15, and the flash-run count-03/sort-14 flips) is this.
   When the baseline instead reached for **`shell cat`/`grep` with the absolute path**
   (it sometimes does), it *succeeded* (lookup-02, pick-04, extract-13, first-16,
   count-03 in the haiku run). So the baseline's score is essentially a coin-flip on
   *which tool/path form it happens to pick first* — a routing/path-priors problem.
   Both candidates consistently use the rewritten absolute path on the first try.

2. **The 0.80 vs 0.60 baseline split is run-to-run non-determinism on the *same* model
   and fixtures, on just two cases** (count-lines-03 and sort-list-14 flipped from
   correct→wrong between the haiku-run and flash-run baselines). The difference is which
   shell formulation it tried (`grep -c .` succeeded; `grep -cve '^[[:space:]]*$'` and
   piped `cat | sort | tr` were rejected as **shell metacharacters**, and it didn't fall
   back). On a 10-case corpus this is a ±2-case (±0.2 accuracy) noise band — treat any
   single Δ accordingly. The candidate *uplift direction* is robust; the *magnitude* is not.

3. **Two answer-scorer false-positives — both favor a candidate or the baseline, none
   penalize them — so true candidate quality is slightly *over*-stated, baseline too:**
   - **write-readback-06 (`gpt-4o-mini`, both runs)**: graded **correct** although the
     file write *failed* and the model explicitly said it could not confirm. The
     expected substring `ready` is a word *in the prompt itself*, so the model's
     apology ("write the word 'ready' … but I encountered errors") trivially contains
     it. The GoalJudge carrier correctly says `goal_met=false, criteria_met=0.333`. This
     gives the baseline 2 undeserved "correct"s (one per run).
   - **pick-max-04 (`deepseek-v4-flash`)**: graded **correct** although the model
     answered a *different question* ("2 people scored above 80 — Priya and JordanK").
     The substring `priya` is present, so it passes. GoalJudge nailed it:
     `goal_met=false, criteria_met=0.0`, "reported two names … instead of the single
     name with the highest score." This is 1 of Flash's 9 "correct"s — Flash's true
     answer-quality on this corpus is closer to **8/10**.

   **Recommendation**: for substring cases whose expected token also appears in the
   prompt (write-readback) or where the model can satisfy the token while answering a
   different question (pick-max), cross-check the answer scorer against the GoalJudge
   `goal_met`/`per_criterion` carrier. The GoalJudge verdict was *more* accurate than the
   answer scorer on **both** false-positive rows.

4. **GoalJudge vs answer-scorer divergence is systematic on the write/sort tasks.** On
   lookup-02, sort-14, and convert-05 the candidates have `goal_met=false` /
   `criteria_met < 1.0` (GoalJudge expects a written output file or exact rounding) while
   the answer scorer marks the *final text* correct. This is by design — the answer
   scorer grades the reported answer, GoalJudge grades full task completion — but it
   means **"PROMOTE on accuracy" and "GoalJudge goal_met" are not the same bar**, and the
   md report's headline accuracy is the laxer of the two.

5. **convert-unit-05 is the one case that separates the two candidates on real
   capability.** Haiku got it (8.0467, passed by `tol=0.1` despite not rounding — itself
   a GoalJudge `met=false` on the rounding criterion). Flash *failed it outright*: read
   `5`, then hallucinated unit ambiguity and never applied the 1.60934 factor
   (`criteria_met=0.25`). This is Flash's only genuine miss and the reason Haiku (1.00)
   edges Flash (0.90 → ~0.80 after the pick-max correction).

6. **Cost/latency pattern.** Per-task: baseline ~$0.001, Flash ~$0.0019 (1.7×, mostly
   from larger prompts — Flash `tokens_in` ~2.2–3.7k vs baseline ~1.0–1.8k), Haiku
   ~$0.011 (10.7×). Latencies are comparable (~1–2.5 s/step); Haiku trends highest
   (often 2–2.5 s). On these trivial L1 tasks **Flash is the clear value pick** — near
   Haiku's reliability on the failure modes that matter (absolute-path handling) at ~1/6
   the cost — with the caveat that Flash blew the one arithmetic-conversion case Haiku
   handled, and tends to *over-tool* (7-call thrashes on pick-04, sort-14) chasing a
   `python` tool that doesn't exist (`Unknown tool 'python'`).

7. **Tooling friction common to candidates (not a model-quality issue, a harness one):**
   both candidates repeatedly invoke a non-existent **`python` tool** (`Unknown tool
   'python'`) and hit the **shell metacharacter / command-allowlist guard** (pipes,
   `pwd`, walrus tricks). They recover (write a `.py` file and run it, or read directly);
   the baseline does *not* recover from the analogous path error. Worth considering a
   first-class python-exec tool or a clearer path hint in the system prompt to cut the
   thrash.

8. **Langfuse join**: not used (offline Hermes-path gap). All reasoning above is from the
   local `recordings/*/trace.jsonl` carriers and `evals.log`; the `uuid5` trace ids are
   listed per case for best-effort manual lookup, but resolution is not guaranteed and
   nothing Langfuse-sourced was asserted.

---

_Source files: `cache/model_ab/l1_haiku_081842/{baseline,candidate}/{evals.log,recordings/}`,
`cache/model_ab/l1_flash_082415/{baseline,candidate}/{evals.log,recordings/}`,
`scripts/seed_model_ab_workspace.py`, `scripts/model_ab_answer_score.py`,
`frontend/e2e/fixtures/model_ab_corpus.json`. Read-only analysis; no scripts modified, no LLM calls, no re-drive._
