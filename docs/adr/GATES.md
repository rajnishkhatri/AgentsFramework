---
type: reference
title: 'Forced-engagement comprehension gates (G1/G3/G4/G7/G8)'
---

# Forced-engagement comprehension gates

> The gate *names* live in `AGENTS.md` (Decision records). This file holds the
> gate *mechanism* — the cognitive-forcing **preamble** that turns a named trigger
> into an actual comprehension check. Harness v2 plan items 2.2 (re-add G3/G7) and
> 2.3 (rotate the wording).

## Why a preamble, not just a trigger

A trigger ("state what the abstraction buys") can be satisfied by a one-line
summary the agent already wrote — that is **recognition**, not **generation**.
The playbook's evidence base (Slamecka & Graf, generation effect; Rozenblit &
Keil, illusion of explanatory depth; Buçinca et al., cognitive forcing) shows the
mechanism is **answer-before-reveal, in your own words**. So every gate below is
phrased to force a *generated* explanation before any rationale is pasted back.

**Honest limit (carried from AGENTS.md):** Claude Code hooks can `ask`/`block`
but cannot capture a *typed human answer* (no controlling terminal). These gates
are therefore **convention + PR-review**, mechanically *triggered* by
`tests/architecture/test_adr_ratchet.py` (the ADR.1 ratchet) but not
*answer-enforced*. The forcing is on the author's discipline; the ratchet only
ensures the seam can't pass silently without an ADR.

## The universal preamble

Before the rationale is written or any explanation is pasted back, answer **in
your own words**:

1. **What** does this change do at the load-bearing line — name that line.
2. **Why** is it correct / safe — the reasoning, not a restatement of the diff.
3. **What is the one assumption most likely to be wrong**, and what breaks if it is.

Recognition ("looks right") is not an answer. If you can't generate 1–3 without
re-reading the diff, the gate has caught real comprehension debt.

## The gates

| Gate | Trigger | Scope |
|------|---------|-------|
| **G1** | A new abstraction / indirection layer | What it buys vs. what you considered instead (→ ADR if load-bearing). |
| **G3** | A change at a **security boundary** | Any edit to a guardrail, tool validator, auth/trust check, command allowlist, path sandbox, or a path the lethal-trifecta touches (untrusted input × private data × exfiltration). |
| **G4** | The crypto / signing path (`trust/`) | What the algorithm does and why the change is correct, *before* pasting the impl. |
| **G7** | An **architecture** change | Anything touching a layer boundary, a dependency-direction rule, or an `Architecture Invariant` (even when `tests/architecture/` still passes — a green test is not comprehension). |
| **G8** | A large test rewrite / deletion | Why each weakened assertion is still sound (mechanically sensed by `test_no_test_weakening.py`). |

G3 and G7 are the highest-stakes gates: they map to the lethal trifecta and the
architecture invariants the repo cares most about. `⚠️ Ask first` makes you
*approve* a change; a gate makes you *explain* it — do not conflate the two.

## Rotating wordings (2.3)

Rote prompts stop forcing generation — the brain pattern-matches the question and
emits a cached answer. Rotate the phrasing so the gate stays a genuine prompt.
Pick a different framing each time a gate fires (the underlying ask is identical):

**G3 — security boundary**
- *Adversary framing:* "If I handed this diff to someone trying to exfiltrate
  data or escape the sandbox, what's the first thing they'd try, and does this
  change open or close it?"
- *Trifecta framing:* "Trace one path where untrusted input could reach a private
  capability through this change. Where is it stopped?"
- *Invariant framing:* "Name the security invariant this code is responsible for,
  and the exact line that enforces it now."
- *Regression framing:* "What did the OLD code prevent that a careless edit here
  could silently re-enable?"

**G7 — architecture**
- *Arrow framing:* "Which dependency arrow does this change rely on, and which
  layer would break first if that arrow reversed?"
- *Invariant framing:* "Name the architecture invariant nearest this change and
  why it still holds — without running `tests/architecture/`."
- *Seam framing:* "If a teammate deleted this whole layer, what would stop
  compiling, and is that the coupling you intended?"
- *Future framing:* "Six months from now, what about this placement will look
  wrong, and why is it still the right call today?"

**G1 — new abstraction**
- "What concrete duplication or change-amplification does this abstraction remove
  — name the two call sites that prove it earns its place?"
- "What's the simpler thing you rejected, and what did it cost that this doesn't?"

**G4 — crypto/signing** (detail in `trust/AGENTS.md`)
- "Re-derive the signed-field set from first principles; does this change move a
  field across the signed/unsigned boundary?"
- "What input would make this verification wrongly return true, and why can't it
  occur?"

**G8 — test rewrite**
- "For the assertion you weakened, write the bug it would now MISS."
- "Which of these rewritten tests, if it had existed, would have failed for the
  last real regression in this area?"
