# English Coach — Adaptive Lesson · final delivery

The adaptive skill-lesson design line, packaged. One skill's teaching content, re-sequenced to the learner's moment — with the McKinsey SCQA ordering engine running invisibly underneath.

## standalones/ — open in any browser, offline
Double-click. Fully self-contained (design system + runtime inlined).
- **English Coach - Lesson (Adaptive).html** — **the final design.** Minimal, no-card, color-coded. A learner-mode switcher (New skill / Returning / Refresher / Worked / Diagnostic / Annotated) re-orders the four teaching beats; no framework labels ever show.
- **English Coach - Lesson (SCQA).html** — the same, with the framework **visible** (S/C/Q/A labels, ordering codes, diagnostic + rationale). Internal explainer for how the sequencing works.
- **English Coach - Lesson (Typographic).html** — the type-as-signal study (serif passages, bold/italic/underline/color conventions).

## sources/ — the editable Design Components (.dc.html)
Run inside the project (they load the AgentsFramework design system + the DC runtime; the composers also mount `LessonBlock` at runtime).
- `English Coach - Lesson (Adaptive).dc.html` — source of the final design.
- `English Coach - Lesson (SCQA).dc.html` — labeled explainer source.
- `English Coach - Lesson (Minimal).dc.html` — minimal no-card lesson (composes `LessonBlock`).
- `English Coach - Lesson (Typographic).dc.html` — typographic study.
- `English Coach - Lesson Composer.dc.html` — schema-driven composer (desktop): context switcher → block recipe.
- `English Coach - Lesson Composer (iPhone & iPad).dc.html` — the composer on both device frames.
- `LessonBlock.dc.html` — the reusable block component every composer mounts.

## specs/ — the contracts
- **Adaptive-Lesson-Protocol.md** — beat model, mode→ordering table, schema, mode-selection protocol, and the invisibility contract (`AL-*` requirements + acceptance).
- **Lesson-Block-Schema.md** + **lesson-blocks-schema.json** — the block catalog: 9 tags, color roles, context recipes, runtime contract.

## tests/ — automated style validation
- **adaptive-lesson.spec.js** — Playwright suite validating the Adaptive lesson against the protocol: beat colour code, mode→ordering (per mode + element-drop + end-on-resolution), no-card style, serif study text, theme flip, and the invisibility contract (no SCQA surface in any mode). Targets `standalones/English Coach - Lesson (Adaptive).html`; run from the project `tests/` folder (`npm install && npx playwright install chromium && npm test`).

## reading order
1. Open `standalones/English Coach - Lesson (Adaptive).html` → try the modes.
2. Open `standalones/English Coach - Lesson (SCQA).html` to see the framework that drives it.
3. `specs/Adaptive-Lesson-Protocol.md` for the contract, `Lesson-Block-Schema.md` for the block system.
4. `tests/adaptive-lesson.spec.js` for the validation rubric.
