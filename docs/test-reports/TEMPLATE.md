# Frontend Test Session Report — TEMPLATE

> Copy this file to `docs/test-reports/YYYY-MM-DD-<short-name>.md` after
> each significant Playwright session (release gate, nightly, ad-hoc
> validation). Fill in every section. Pair the report with the link to
> the Playwright HTML artifact.

---

## 1. Session Metadata

| Field | Value |
|-------|-------|
| **Session date** | YYYY-MM-DD HH:MM TZ |
| **Trigger** | release gate / nightly / on-demand / PR |
| **Operator** | name |
| **Branch** | `<branch>` |
| **Commit SHA** | `<sha>` |
| **Tier(s) executed** | T1 / T2 / T3 / cross-browser |
| **Frontend BASE_URL** | `http://localhost:3000` or staging URL |
| **MIDDLEWARE_URL** | `http://localhost:8000` or `mock` |
| **Backend version** | git SHA / docker tag |
| **Playwright version** | `playwright --version` output |
| **Node version** | `node --version` output |
| **OS** | `uname -a` output |

---

## 2. Environment Configuration

```bash
# Paste the exact env vars used for the run
E2E_AUTHENTICATED=
E2E_USER_EMAIL=
BASE_URL=
MIDDLEWARE_URL=
MOCK_MIDDLEWARE=
NODE_ENV=
```

Browser projects executed:

- [ ] chromium-desktop
- [ ] webkit-desktop
- [ ] firefox-desktop
- [ ] mobile-safari (iPhone 14)
- [ ] ipad

---

## 3. Result Summary

| Tier | Specs run | Passed | Failed | Skipped | Flaky | Duration |
|------|-----------|--------|--------|---------|-------|----------|
| T1 (security) | | | | | | |
| T1 (UI features) | | | | | | |
| T1 (a11y / mobile) | | | | | | |
| T2 (BFF integration) | | | | | | |
| T3 (full-stack) | | | | | | |
| Cross-browser matrix | | | | | | |
| **TOTAL** | | | | | | |

Overall verdict: **PASS / FAIL / PARTIAL**

---

## 4. Coverage by FRONTEND_VALIDATION.md Section

Tick PASS / FAIL / SKIP for each section against the executed tier(s).

| SS | Section | Linked spec | T1 | T2 | T3 | Notes |
|----|---------|-------------|----|----|----|-------|
| 2.1 | Auth flow | `smoke.spec.ts` | n/a | n/a | | |
| 2.2 | Chat shell layout | `chat-shell.spec.ts` | | | | |
| 2.3 | Composer | `composer.spec.ts` | | | | |
| 2.4 | Streaming markdown | `streaming.spec.ts` | | | | |
| 2.5 | Run controls | `run-controls.spec.ts` | | | | |
| 2.6 | Thread sidebar | `thread-sidebar.spec.ts` | | | | |
| 2.7 | Theme toggle | `theme.spec.ts` | | | | |
| 2.8 | Tool cards | `tool-cards.spec.ts` | | | | |
| 2.9 | Generative UI | `generative-ui.spec.ts` | | | | |
| 2.10 | Trust badge | `full-stack/trust-badge.spec.ts` | n/a | n/a | | |
| 2.11 | Observability | `observability.spec.ts` | | | | |
| 2.12 | Mobile responsive | `mobile-responsive.spec.ts` | | | | |
| 2.13 | Accessibility | `accessibility.spec.ts` | | | | |
| 2.14 | Performance / TTFT | `full-stack/ttft-benchmark.spec.ts` | n/a | n/a | | |
| 2.15 | Error & resilience | `error-resilience.spec.ts` | | | | |
| 3.1 | Strict CSP | `security/csp.spec.ts` | | | | |
| 3.2 | Iframe sandbox | `security/iframe-sandbox.spec.ts` | | | | |
| 3.3 | JWT storage | `security/jwt-storage.spec.ts` | | | | |
| 3.4 | dangerouslySetInnerHTML | `security/xss-surface.spec.ts` | | | | |
| 3.5 | trace_id provenance | `security/trace-id.spec.ts` + `integration/bff-stream-proxy.spec.ts` | | | | |
| 3.8 | Sealed envelopes | `full-stack/trust-badge.spec.ts` | n/a | n/a | | |
| 3.9 | Other security headers | `security/headers.spec.ts` | | | | |
| 4 | Cross-browser matrix | `cross-browser/matrix.spec.ts` | | | | |

---

## 5. Auto-Reject Anti-Pattern Status

These six anti-patterns from `docs/STYLE_GUIDE_FRONTEND.md` §22 are
release blockers. ALL must be PASS or FAIL with explicit waiver.

| ID | Description | Result | Evidence |
|----|-------------|--------|----------|
| FE-AP-4 | Iframe without `sandbox="allow-scripts"` only | | `security/iframe-sandbox.spec.ts` |
| FE-AP-6 | Mutating sealed envelope | | `full-stack/trust-badge.spec.ts` |
| FE-AP-7 | Browser-generated `trace_id` | | `security/trace-id.spec.ts` |
| FE-AP-12 | `dangerouslySetInnerHTML` on agent output | | `security/xss-surface.spec.ts` |
| FE-AP-18 | JWT in `localStorage` / `sessionStorage` | | `security/jwt-storage.spec.ts` |
| FE-AP-19 | CSP `'unsafe-inline'` / `'unsafe-eval'` | | `security/csp.spec.ts` |

---

## 6. Failures (Detail)

For each failed test, fill in:

### Failure 1 — `<spec file> > <test name>`

- **Severity**: S0 / S1 / S2 / S3 (per `docs/FRONTEND_VALIDATION.md` §0.4)
- **Reproduction**: command and steps
- **Observed**:
- **Expected**:
- **Trace / screenshot**: link to `playwright-report/`
- **Hypothesis**:
- **Owner / ticket**: GitHub issue link

### Failure 2 — ...

(repeat as needed)

---

## 7. Performance Numbers (T3 only)

If `full-stack/ttft-benchmark.spec.ts` ran:

| Run | TTFT (ms) |
|-----|-----------|
| 1 | |
| 2 | |
| 3 | |
| 4 | |
| 5 | |
| **p50** | |

Threshold: < 500 ms (SS2.14). Verdict: PASS / FAIL.

---

## 8. Cross-Browser Matrix Results

| Section | chromium-desktop | webkit-desktop | firefox-desktop | mobile-safari | ipad |
|---------|------------------|----------------|-----------------|----------------|------|
| 1 Smoke | | | | | |
| 2.3 Composer | | | | | |
| 2.4 Streaming | | | | | |
| 2.7 Theme | | | | | |
| 2.8 Tool cards | | | | | |
| 2.9 Generative UI | | | | | |
| 2.13 A11y | | | n/a | n/a | n/a |

Tick = PASS, blank = NOT RUN, X = FAIL (file ticket).

---

## 9. Sign-off Gates

Per `docs/FRONTEND_VALIDATION.md` §5:

- [ ] **Gate 1** — Automation precondition (`pnpm typecheck && pnpm lint && pnpm test && pnpm test:arch && pnpm check:csp && ...`)
- [ ] **Gate 2** — Manual feature checks (every box in §2.1 through §2.15 is YES on at least one project)
- [ ] **Gate 3** — Trust and security (§3.1 through §3.9 are YES)
- [ ] **Gate 4** — Cross-browser matrix (one row per browser/device cell)
- [ ] **Gate 5** — Staging E2E (T3 against staging)

---

## 10. Artifacts

- Playwright HTML report: `playwright-report/index.html` → archived to: ...
- Traces: `test-results/` → archived to: ...
- Console logs: `<path>`
- Screenshots of any UI defects: `<path>`

---

## 11. Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| QA | | | |
| Eng on-call | | | |
| Release manager | | | |
