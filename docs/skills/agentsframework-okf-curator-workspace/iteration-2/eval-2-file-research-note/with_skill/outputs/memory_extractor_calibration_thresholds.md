---
type: reference
title: Memory extractor calibration thresholds
description: Reusable acceptance thresholds for memory-extractor store-decision calibration — precision gate, hard-zero PII-flip rate, and kappa-vs-gold floor — derived from the frozen test split and used to gate write-back via the enable-policy certificate.
tags: [research, memory-extractor, calibration]
---

# Memory extractor calibration thresholds

The store-decision precision gate should sit at `>= 0.90` and the PII-flip rate must be a
hard zero. Kappa vs gold `>= 0.60` is the inter-rater floor. These thresholds come from the
frozen test split and gate write-back via the enable-policy certificate.
