# Architecture Decision Records — bundle index

OKF bundle. Each entry is a typed Concept. See the convention in [CONVENTIONS_OKF.md](../CONVENTIONS_OKF.md).

ADRs are the only sanctioned way to deviate from a frontend style-guide §2 prescription or to swap a substrate / library (style guide §"Prescriptive tone"). Copy [0000-template.md](0000-template.md) for new records.

- [ADR template](0000-template.md) — Copy this to start a new ADR; sections: Context / Decision / Options / Rationale / Consequences.
- [ADR-0001: Tauri 2 (macOS) + Capacitor 7 (iOS) over Electron and native frameworks](0001-native-shell-tauri-capacitor.md) — Why the native shells wrap the single Next.js web app in the OS WebView rather than adopting Electron, React Native, Flutter, or SwiftUI; native feel = CSS, not shell; WKWebView is the one shared risk.
- [ADR-0002: Repo-wide ruff baseline (commit 3b89b4e) — G8 test-mass-rewrite audit](0002-ruff-baseline-g8-audit.md) — The G8 audit record proving the Track-A ruff baseline (598 files, 202 tests) was format-and-safe-fix only and weakened no assertion; the re-runnable audit commands; the contract that future large `--fix` passes carry the same audit.
