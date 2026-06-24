---
type: log
title: 'Architecture Decision Records — bundle log'
---

# Architecture Decision Records — bundle log

Chronological history, newest first (ISO-8601).

- 2026-06-25 — Expanded [ADR-0001](0001-native-shell-tauri-capacitor.md) with the full trade-off analysis (decision unchanged: keep Tauri + Capacitor). Added: what the agentic leaders actually ship (Anthropic/Cursor/OpenAI/Slack — Electron-leaning desktop, native/PWA mobile) + the "how primary is mobile" axis; a weighted scoring rubric (Tauri+Cap 7.85 vs Cap→Electron 7.05 vs Electron+Cap 6.95 vs Swift+Cap 5.55) with measured perf/tooling numbers; a heavy-integrations table flagging **WebGPU/GPU-compute as the one real Tauri capability gap** (WebGL charts + LibreOffice/OnlyOffice sidecar favour or tie with Tauri); and a switching-cost section grounded in the real ~580-LOC Rust shell (Tauri→Electron ≈ 1–2 weeks; Capacitor→RN ≈ 2–4 months — mobile is the expensive switch, desktop is cheap). Added two decision-triggers (WebGPU-on-desktop → Capacitor-under-Electron; mobile-becomes-premium → native) with a "don't pre-pay the switch" conclusion.
- 2026-06-24 — Declared `docs/adr/` an OKF bundle (the directory the frontend style guide already references for §2 deviations and substrate/library swaps): added `index.md`, this `log.md`, the `0000-template.md` template, and the first record [ADR-0001](0001-native-shell-tauri-capacitor.md) recording the Tauri 2 (macOS) + Capacitor 7 (iOS) shell choice over Electron / React Native / Flutter / SwiftUI, with the 2026 landscape rationale and the WKWebView shared-risk consequence. Registered the bundle in `scripts/okf_lint.py`.
