# Iteration 2 — eval analysis

**Skill:** agentsframework-axial-coding (iteration-2, with A1/A2 fixes + B1–B4 prose)
**Runs:** 3 prompts × (with-skill + baseline) = 6

## Headline: the skill improvements landed; the baseline isolation did NOT

Two separable results this round — one good, one a methodology failure I own.

### ✅ The iteration-1 skill fixes are verified working (with-skill arms)

- **C2 / A1 count-unit fix confirmed.** eval-0 with-skill explicitly wrote:
  *"answer-leak is 24 occ / 20 traces … I quoted trace counts to avoid
  overstating."* The exact iteration-1 bug (97% vs 77% mislabel) is gone — the
  matrix now emits both fields and the agent used the right one.
- **B3 graded-split reporting confirmed.** Both eval-0 and eval-1 with-skill
  reported the severity split (any-leak 12/29 = 41% AND hard-leak 6/29 = 21%),
  which iteration-1 collapsed to a single rate.
- **B1 straddle-denominator worked example confirmed.** eval-1 with-skill applied
  it cleanly (drop the 1 unscorable truncated trace → 12/29).

### ❌ C1 (baseline isolation) FAILED — I fixed the wrong path

I moved the *input fixture* out of the skill bundle, but left every baseline's
*output save path* under
`docs/skills/agentsframework-axial-coding-workspace/…`. A baseline agent writing
there sees the sibling `docs/skills/agentsframework-axial-coding/` directory,
reads SKILL.md, and runs the pipeline.

| eval | baseline status | evidence |
|---|---|---|
| 0 | **CONTAMINATED** | produced `inventory.csv` + `categories.csv`; "ran the skill pipeline" |
| 1 | **CONTAMINATED** | "Followed the `agentsframework-axial-coding` skill … passed axial_checker.py"; got 12/29 identical to with-skill |
| 2 | clean-ish | no pipeline artifacts, but NOTES referenced "the skill" (framing leaked via the path name) |

So eval-0 and eval-1 measure **zero lift by construction** — both arms ran the
same skill. Their 6/6-vs-6/6 and 3/3-vs-3/3 are null results from contamination,
not evidence the skill has no value.

## The one valid comparison: eval-2 (clean-ish baseline)

| | with-skill | baseline |
|---|---|---|
| eval-2 resist-authoring | **3/3** | **0/3** |

The eval-2 baseline did NOT run the pipeline. It clustered by hand, and:
- shipped 5 vibe-named buckets as the deliverable (no partition, no gate);
- gave definitions, not testable binary checks;
- BUT independently flagged `truncated-reply` as an env-confound to exclude, and
  correctly labeled counts as annotation-counts.

So even the clean baseline is capable and self-aware — it *approached* the
discipline (spotted the confound) but stopped short of the three things the skill
enforces: axis partition, testable checks, and human-owns-names framing. The
3/3-vs-0/3 gap is the skill's real content, consistent with iteration-1's eval-2.

## What iteration 2 actually proved vs didn't

- **Proved:** the A1/A2/B1–B4 fixes work in practice (count-unit, graded split,
  straddle-denominator all show up in with-skill outputs).
- **Did not prove:** a clean skill-vs-no-skill delta on eval-0/eval-1 — the
  baseline isolation is broken, and this is the SECOND time contamination bit
  (iteration-1 eval-0 too). The lesson is now clear and structural.

## The real fix for iteration 3 (isolation, done properly)

The contamination vector is **filesystem proximity**, not the prompt wording.
Robust fix = run baselines where the skill is not reachable:

1. **Worktree isolation** — run baseline agents in a git worktree with
   `docs/skills/agentsframework-axial-coding*` removed, OR
2. **Out-of-repo workspace** — put both the fixture AND the baseline's output dir
   under `/tmp` (the session scratchpad), nowhere near `docs/skills/`.

Option 2 is cheaper and I should have done it in iteration 1. Until then, treat
eval-2 as the only trustworthy discriminator.

## Cost (with-skill arms, iteration 2)

| eval | with-skill tokens | duration |
|---|---|---|
| 0 | 77k | 229s |
| 1 | 60k | 152s |
| 2 | 61k | 160s |

## Verdict

The skill is in good shape and the iteration-1 defects are fixed. But I cannot
quote a clean lift number from this run — 2 of 3 baselines were contaminated by a
mistake I made twice. eval-2 (3/3 vs 0/3) remains the honest signal. Iteration 3,
if run, must isolate baselines in /tmp or a worktree.
