---
type: research-note
title: Memory-extractor calibration thresholds
description: The frozen-test-split acceptance thresholds (store-decision precision, PII-flip rate, kappa-vs-gold) that gate memory write-back via the enable-policy certificate.
tags: [research, memory_extractor, calibration, governance, thresholds]
---

# Memory extractor calibration thresholds

This is a reusable design reference for the acceptance bar that a memory-extractor
calibration run must clear before its certificate may enable autocapture write-back.
The thresholds below are the source of truth — gate every new run, scorer change, or
certificate emission against them rather than re-deriving the numbers per run.

## Thresholds

| Metric | Bar | Kind |
|---|---|---|
| Store-decision precision | `>= 0.90` | gate (minimum) |
| PII-flip rate | `== 0` | hard zero |
| Kappa vs gold | `>= 0.60` | inter-rater floor |

- **Store-decision precision `>= 0.90`** — of the items the extractor decided to store,
  at least 90% must be correct store decisions. This is the primary precision gate.
- **PII-flip rate must be a hard zero** — no calibration run may flip a PII item into a
  stored memory. This is not a soft target; any non-zero PII-flip fails the run outright.
- **Kappa vs gold `>= 0.60`** — agreement between the extractor's labels and the gold set
  must clear a Cohen's-kappa floor of 0.60, the inter-rater floor below which the run is
  not trustworthy enough to certify.

## Where the numbers come from and what they gate

These thresholds are measured on the **frozen test split** — the held-out split fixed for
calibration so the bar cannot be tuned to the data. A run that meets all three on the
frozen split is what authorizes the **enable-policy certificate**; that certificate is the
machine gate on memory write-back. The autocapture flag alone does not store: write-back
fails safe to shadow unless a passing certificate is present. So these thresholds are the
substance behind the certificate, and the certificate is the substance behind write-back.
