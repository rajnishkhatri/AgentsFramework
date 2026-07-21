# PreACT English Coach — Locked Spec Artifacts

Direction **2b** (hint ladder + conversation) is locked for the /learn/* wide-layout + coach-panel
parity pass. These two files are everything a coding agent needs to implement it — nothing left
to interpretation.

## Contents

1. **Coach Layout Options - Locked Design + Redlines (standalone).html**
   Self-contained, opens offline. Pan/zoom canvas with 5 turns:
   - Turns 1-4: exploration + validation (coach-column directions, full quiz split, iPad
     landscape/drawer, iPhone) — kept for context on why 2b was chosen.
   - **Turn 5 (top): engineering redlines** — dimension lines (red) and DS token callouts on the
     locked desktop split, iPad delta, drawer delta, and iPhone delta.

2. **PreACT-English-Coach-LOCKED-Spec.md**
   The authoritative implementation spec: the one 900px breakpoint rule, sidebar behavior, the
   full Zone A/B/C coach-column contract (hint ladder, collapsible answers, pinned composer),
   drawer mechanics, iPhone behavior, the Feedback bridge, state model, design tokens used,
   20 EARS acceptance criteria, and a test matrix (Playwright/unit, mapped 1:1 to each criterion).
   **Supersedes** the earlier draft spec from this project.

## Reading order
Open the HTML, jump to turn 5 for the visual redlines, then read the Markdown spec top to bottom —
section numbers in the doc match what's diagrammed. Hand both to the implementing engineer/agent
together.
