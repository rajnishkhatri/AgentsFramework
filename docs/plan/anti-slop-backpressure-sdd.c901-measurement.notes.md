# TASK-9 — ruff C901 baseline re-measurement + wire/defer decision

> **Status:** Read-only measurement complete (anti-slop spec **PI-6a**). The
> *decision* (wire vs defer) is a pending human call — this doc is the evidence
> for it. Companion to
> [`anti-slop-backpressure-sdd.spec.md`](anti-slop-backpressure-sdd.spec.md)
> (PI-6, FR-5, TASK-9/10).

**Measured:** `ruff 0.15.16`, `main` @ `9bf92f2` (2026-07-13). The Python tree is
identical to `main` at measurement time (the only uncommitted work in the tree was
frontend-only Epic-F WIP — no `.py` — so the working-tree count equals main's).

Re-run command:

```bash
.venv/bin/ruff check . --select C901 --config "lint.mccabe.max-complexity=<N>"
```

## Baseline distribution (whole repo)

| max-complexity | functions over |
|---|---|
| 10 (ruff default) | 109 |
| 15 | 42 |
| 20 | 26 |
| 25 | 16 |
| 30 | 10 |
| 35 | 5 |
| 40 | 4 |
| 50 | 4 |

**Ceiling = 4 functions above 40**, one extreme outlier:

| complexity | function | file |
|---|---|---|
| **176** | `build_graph` | `orchestration/react_loop.py` |
| 56 | `build_dev_app` | `middleware/__main__.py` |
| 56 | `build_combined_app` | `middleware/app_prod.py` |
| 56 | `_normalize_review_payload` | `meta/code_reviewer.py` |

Next tier (30–40): `build_app` (38, agent_ui_adapter), `route_node` (34) +
`evaluate_node` (30) + `_execute_tools_impl` (28) in `orchestration/react_loop.py`,
`grade` (34, scripts), `main` (32, the triplicated skill-mirror `relocate.py`).

## Where the @15 violations live (path-relief lens)

42 total @15. By top-level dir:

| dir | count | nature |
|---|---|---|
| `scripts/` | 12 | one-off analysis / annotation utilities — **not** prod hot path |
| `orchestration/` | 5 | runtime graph (`react_loop.py` — inherently branchy builders) |
| `middleware/` | 4 | app builders |
| `agent_ui_adapter/` | 4 | dev/standalone server |
| `meta/` | 3 | offline tooling (code reviewer) |
| `docs/` + `.cursor/` + `.claude/` | 3+3+3 | **same** `relocate.py`/`drift_report.py` triplicated by `make skills-sync` (1 real fn ×3) |
| `components/` | 2 | domain logic |
| `utils/` · `services/` · `explainability_app/` | 1 each | |

- **~29% (12/42) are in `scripts/`** — utility one-offs, not the prod path.
- **9 are skill-mirror triplicates** — 1 real function counted 3× (`.claude`/`.cursor`/`docs`).
- Excluding scripts + skills + docs → **21 @15 in real library/runtime code.**
- Core 4 layers + runtime → **19 @15.**

## FR-5 hard constraint (the reason this can't be a switch-flip)

Any wire-in must NOT turn `make check` red on pre-existing untouched code. There is
**no threshold below 177 that is green-on-arrival.** So a wire-in at any usable
threshold first requires either:
- (a) refactoring every offender under the line, or
- (b) `# noqa: C901` / a `per-file-ignores` block grandfathering the current set.

## The three real options

### Option A — Defer (record "measured, deferred")
No CI change. Cost: none. The convention layer already shipped (G9 gate + anti-slop
musts + the code-review anti-slop gate) governs defensive-complexity slop **by
review** — the same enforcement class G1/G3/G7 use. A mechanical C901 tooth adds
marginal value over that for a solo-operator loop, at real calendar cost.

### Option B — Grandfather + ratchet
Wire `C901` at a chosen threshold (15 or 20), grandfather the current offenders
with `# noqa: C901` (or `per-file-ignores`) so `make check` is green on day 1, and
any **new** over-threshold function fails. Cost: ~26 (@20) or ~42 (@15) annotations
+ the threshold pick. This is the "no new slop, tolerate old" ratchet — same shape
as `test_no_test_weakening`. Highest teeth-per-effort.

### Option C — Refactor-then-wire
Pick a threshold, refactor every offender under it, then wire clean. Cost: real
engineering on `build_graph` (176) + the three 56s. Weeks, not hours. Those are
stable builders, not churny slop — **not justified now.**

## Recommendation (for the human decision)

**A now; B if/when a specific over-complex function actually ships as slop.** Two
grounded reasons:
1. The spec deliberately shipped 100% convention first. Nothing measured here
   changes that calculus — no new hotspot, no churn signal.
2. **Complexity ≠ the slop G9 targets.** G9 is about *defensive fallbacks masking
   failures* — a review judgment. Cyclomatic complexity correlates weakly with it.
   A C901 ratchet is teeth on the wrong metric.

If *any* mechanical tooth is wanted, **B at max-complexity=20** is the cheapest
honest one (26 grandfathered; catches the genuinely-egregious new function).
