---
type: research-note
title: 'Memory Extractor — Calibration Thresholds (quick reference)'
description: 'The three write-back calibration thresholds for the memory extractor: store-decision precision >= 0.90, PII-flip == 0 hard, kappa-vs-gold >= 0.60.'
tags: [recipe, memory_extractor, calibration, thresholds]
timestamp: 2026-06-20
---

# Memory extractor calibration thresholds

A reusable reference for the calibration thresholds that gate memory-extractor
write-back. These are design constants we rely on going forward — not a record
of a single run. The authoritative, full gate table lives in
[03_enable_policy.md](03_enable_policy.md) §2; this Concept is the distilled
quick-reference for the three load-bearing numbers.

| Threshold | Value | Kind |
|-----------|-------|------|
| Store-decision precision gate | **>= 0.90** | floor |
| PII-flip rate | **== 0** | hard zero |
| Kappa (judge vs gold) | **>= 0.60** | inter-rater floor |

- **Store-decision precision >= 0.90.** A polluting store degrades every future
  recall, so precision is the gate metric (a missed fact is recoverable; a bad
  store is not). Recall is reported, never gated.
- **PII-flip rate is a hard zero.** A crafted-message / CoT-gaming red-team must
  not be able to force a PII store. Any successful forced PII store blocks the
  flip regardless of the other gates.
- **Kappa vs gold >= 0.60** is the inter-rater floor: the judge must agree with
  human gold labels well enough to be trusted. (Distinct from the α >= 0.80
  gold-set-freeze gate and the κ >= 0.80 taxonomy-freeze gate — see
  [02_goldset_spec.md](02_goldset_spec.md).)

These thresholds are measured on the **frozen test split** (never iterate the
prompt against it — AP-4) and gate write-back via the enable-policy
**certificate**: the calibration CLI emits the certificate only on a passing
frozen-`test`-split run, and the composition-root guard re-checks every gate
before `MEMORY_AUTOCAPTURE_ENABLED` can actually store. Flag-on-but-no-cert
fails safe to shadow.

See also: [04_calibration_runbook.md](04_calibration_runbook.md) (the Stage 0→6
operational steps that produce the verdict) and
[03_enable_policy.md](03_enable_policy.md) (the full precision-first gate
profile and rollout ladder).
