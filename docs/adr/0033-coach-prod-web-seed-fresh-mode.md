---
type: decision-record
title: 'ADR-0033: Seed a reviewed web corpus into the production /learn substrate in fresh mode'
status: accepted
created: 2026-07-15
updated: 2026-07-15
owner: Rajnish Khatri
related: eng-coach-gcp-deploy.spec.md, eng-coach-gcp-deploy.brainstorm.md, 0005-native-shell-persistence.md, 0010-on-device-sqlite-engine-db.md, 0021-subject-coach-test-item-bank-blueprint-read-seam.md
tags: [decision-record]
---

# ADR-0033: Seed a reviewed web corpus into the production `/learn` substrate in `fresh` mode

**Status:** Proposed — 2026-07-15.
**Related:** [eng-coach-gcp-deploy.spec.md](../plan/eng-coach-gcp-deploy.spec.md) (FR-1..5), [brainstorm D7 + D0-b](../plan/eng-coach-gcp-deploy.brainstorm.md), ADR-0005/0010 (on-device SQLite native path), ADR-0021 (governed test-item bank).
**Audience:** anyone reconsidering the coach data plane on the Cloud Run web frontend, or the on-device SQLite / Capacitor native track.

---

## Context

The coach `/learn` route-group ships inside the deployed `agent-frontend` Cloud Run
service. In a **production** build the engine substrate is
[`composition_engine_browser.ts:257-262`](../../frontend/lib/composition_engine_browser.ts):
`buildBrowserEngineAdapters()` with no `engineDb` → a fresh **empty**
`InMemoryEngineDb`. Every seed (`seedDevCorpus`/`seedDevTaxonomy`/`seedTestItemBank`/
`seedHintBank`/`seedLessonContent`) is gated behind `NODE_ENV !== "production"`
(line 216), because the dev corpus "must not ship." The *intended* production data
path is on-device SQLite (ADR-0005/0010) — but that is **unbuilt and Capacitor-only**
(the native mobile/desktop shell), not the Cloud Run web frontend.

Net: a web deploy today yields a working-auth, **zero-content** coach — no skills, no
questions, permanently. That makes the deploy not worth shipping (the Stage-1 D0-b
blocker).

Separately, the frontend already has a `seedMode` latch (`demo` | `fresh`):
authenticated WorkOS sessions resolve `seedMode = "fresh"`
([`resolve_learn_identity.ts:59-63`](../../frontend/lib/learn/resolve_learn_identity.ts)),
and the **non-prod** `fresh` branch already runs `seedDevTaxonomy → seedTestItemBank
→ seedHintBank → seedLessonContent` with `questionSource: "bank"`
(composition_engine_browser.ts:241-255) — taxonomy + governed item bank + hints +
lessons, and crucially **no Garvit mastery** (that is the separate `seedDevCorpus`,
the `demo` branch). The reviewed corpus we want on the web already exists and is
already assembled behind the prod gate.

## Decision

**Lift the production seed gate for authenticated `seedMode = "fresh"` sessions
only:** the prod branch builds an `InMemoryEngineDb`, runs the same
`seedDevTaxonomy → seedTestItemBank → seedHintBank → seedLessonContent` pack the
non-prod `fresh` branch runs, and builds the bag with `questionSource: "bank"`. Every
**non-`fresh`** production path (demo / unset / undecidable) keeps building an
**empty** bag — `seedDevCorpus` and every dev-seed call stay unreachable on those
branches (spec FR-1). The learner's progress slate stays empty (content, not history).

This is a **web-vs-native split**: the reviewed in-bundle corpus is the web frontend's
data plane; on-device SQLite (ADR-0005/0010) remains the **native** (Capacitor) end
state on its own track. The two do not merge here.

## Options considered & rejected

| Option | Why not |
|---|---|
| **Keep the empty prod substrate; wait for on-device SQLite** | SQLite is unbuilt AND Capacitor-only — it never runs on the Cloud Run web frontend. Waiting means shipping a permanently empty coach. This is the D0-b blocker. |
| **Ship the Garvit demo corpus to prod** | `seedDevCorpus` carries demo mastery + accuracy history — violates the learner-identity fresh-slate FR and the "dev corpus must not ship" rule. Rejected by FR-1. |
| **Build a new prod-only seed path** | The reviewed `fresh` pack already exists and is already assembled; a parallel path is duplicate machinery (G1) with drift risk against the non-prod branch. |
| **Static import of the corpus into the prod bundle** (candidate) | Simplest, but makes ~12K lines (`_test_item_bank.ts` 7.5K + `_hint_bank.ts` 4.6K), today dead-code-eliminated, part of First-Load JS for every `/learn` visitor — a real §18 bundle-budget hit. **Deferred to the plan** (measure `ANALYZE=true`, decide static vs lazy dynamic import against `.bundle-baseline.json`). |

## Rationale

The mechanism is a **scoped un-gating of a pre-existing, reviewed path**, not new
content and not a new build. It discriminates on `seedMode === "fresh"` (an
authenticated session), which structurally excludes the Garvit demo dump. It closes
D0-b — a genuinely usable `/learn` — **without** adding a `DATABASE_URL`, a secret, or
any credential-bearing call to the BFF (F-R9 holds), and **without** the unbuilt SQLite
native path. It is the least machinery that satisfies FR-3 (A1).

## Consequences

- **Commits us to:** the reviewed corpus is the web coach's data plane until (if ever)
  a web durable/served path is chosen. The corpus is now prod-reachable, so its review
  quality is load-bearing (it is the product, not a fixture).
- **Bundle cost (accepted, measured in the plan):** ~12K lines become prod-reachable.
  The plan runs `ANALYZE=true pnpm build` and picks static import (if under the +10%
  baseline gate) or a lazy dynamic chunk fetched post-auth (FE-AP-20 / §18). Either
  keeps the requirement; the plan picks the mechanism against the measured number.
- **Progress is honestly empty** on first `fresh` seed — expected, not a bug.
- **Web vs native stay separate:** on-device SQLite (ADR-0005/0010) is untouched; this
  ADR does not advance or block it. When the native path lands it supplies the native
  substrate; the web keeps this in-bundle corpus unless a later ADR changes it.
- **Failure mode is a blank `/learn`, never leaked demo content** — the `seedMode`
  discriminator fails toward empty (AP-6), which FR-1's architecture test locks in.

## Supersedes / related

Realizes [eng-coach-gcp-deploy.spec.md](../plan/eng-coach-gcp-deploy.spec.md) FR-1..5.
Names the web-vs-native boundary against ADR-0005/0010 (native SQLite) and reuses the
ADR-0021 governed item bank. Pairs with ADR-0034 (Q3 durability time-box).
