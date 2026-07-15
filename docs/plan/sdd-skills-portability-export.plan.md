# Plan — Workspace-neutral, multi-agent-portable SDD skills + `.skill` export

**Status:** Draft — 2026-07-15
**Realizes:** [sdd-skills-portability-export.spec.md](sdd-skills-portability-export.spec.md) · governed by [ADR-0032](../adr/0032-workspace-binding-contract.md)

Derived from the clarified spec + the constitution (`AGENTS.md` 8 invariants +
`tests/architecture/`). Simplest-thing-that-satisfies (A1): reuse the existing
sync/parity/zip mechanisms; add only the binding contract, the registry
generalization, and the emitter.

## Architecture

```
docs/skills/_sdd/                        ← the binding contract (new)
  binding.schema.md                      ← 13-key vocabulary + reference values + fill-prompts
  binding.reference.toml                 ← THIS repo's real values (the reference instance)

docs/skills/sdd-<name>/SKILL.md          ← canonical, REWRITTEN to placeholders + genericized examples
  (body uses {{constitution}} etc.; FIRST_RUN preamble describes auto-adapt)

scripts/sync_skills.py                   ← TARGETS 2-tuple → ADAPTER REGISTRY
  adapters = [ClaudeAdapter, CursorAdapter, CopilotAdapter]   ← Copilot = new entry
    Claude/Cursor.project = identity byte-copy  (byte-identical to today)
    Copilot.project        = emit .github/copilot-instructions.md + .instructions.md pointers

scripts/pack_skills.py                   ← NEW: zip docs/skills/<name>/ → <name>.skill
  make skills-pack ; --check drift guard ; bundles binding.template.toml + FIRST_RUN.md for SDD

.github/copilot-instructions.md          ← NEW (repo-wide pointer)
.github/instructions/sdd-<name>.instructions.md  ← NEW (per-skill thin pointer + applyTo)

tests/architecture/
  test_sdd_portable_core.py              ← NEW (FR-1/3/4: no leak, round-trip, skeleton preserved)
  test_sdd_binding_schema.py             ← NEW (FR-8: schema↔reference complete)
  test_skills_mirror_parity.py           ← GENERALIZED (FR-10/12: per-adapter, Claude/Cursor unchanged)
  test_sync_adapter_registry.py          ← NEW (FR-11: new adapter = one entry)
  test_copilot_instructions_parity.py    ← NEW (FR-13/14/15: pointer thinness, applyTo valid)
  test_skills_pack.py                    ← NEW (FR-16/18/19: emits six, --check drifts)
```

## File-level touchpoints

**New files (11):**
- `docs/skills/_sdd/binding.schema.md`, `docs/skills/_sdd/binding.reference.toml`
- `docs/skills/_sdd/binding.template.toml`, `docs/skills/_sdd/FIRST_RUN.md`
- `scripts/pack_skills.py`
- `.github/copilot-instructions.md` + 6× `.github/instructions/sdd-*.instructions.md`
- 5× new `tests/architecture/test_*.py`

**Modified files:**
- 6× `docs/skills/sdd-*/SKILL.md` — placeholder rewrite + example genericization
  (then `make skills-sync` propagates to `.claude/skills/` + `.cursor/skills/`).
- `scripts/sync_skills.py` — `TARGETS` → adapter registry; add `CopilotAdapter`.
- `tests/architecture/test_skills_mirror_parity.py` — generalize to per-adapter.
- `Makefile` — add `skills-pack` target; keep `skills-sync`.
- `docs/skills/README.md` — document the portable-SDD row + binding contract.

**Governance already done:** ADR-0032 written + registered in `index.md`/`log.md`.

## Migration order (red/green, dependency-respecting)

1. **Binding contract first** (schema + reference) — nothing depends on it yet;
   FR-8 guard authored red, then schema/reference make it green.
2. **Portable-core guard authored RED** (FR-1) against the *current* skills —
   proves the leak detector actually fires on today's `AGENTS.md`/`make check`.
3. **Rewrite the six skills** to placeholders + genericized examples → FR-1 goes
   green; FR-3 round-trip + FR-4 skeleton-preserved green.
4. **`make skills-sync`** propagates placeholders to mirrors; the *generalized*
   mirror-parity test (FR-10) must still show Claude/Cursor byte-identical to the
   freshly-synced canonical (regression anchor: run `--check` before/after).
5. **Adapter registry** (FR-9/11/12) — refactor `TARGETS`; Claude/Cursor adapters
   re-derive today's copy; `test_sync_adapter_registry` green.
6. **Copilot adapter** (FR-13/14/15) — add `CopilotAdapter`; emit pointers; parity
   guard green. (Format already verified against GitHub docs at spec time.)
7. **Emitter** (FR-16/18/19) — `pack_skills.py` + `make skills-pack` + `--check`;
   emit six archives; drift guard green.
8. `make check` + `pytest tests/architecture/ -q` fully green; paste output.

Order rationale: the binding contract (1) and the RED leak guard (2) must precede
the rewrite (3) so the rewrite is TDD-driven, not asserted. The registry (5)
precedes Copilot (6) because Copilot is an adapter *entry*. The emitter (7) is last
because it packages the finished portable skills + binding template.

## Invariant check (constitution)

- **Invariants #1–#8:** untouched — all new/changed code is `scripts/` + `docs/` +
  `tests/architecture/` + `.github/`, none in the `trust/`→`services/`→
  `components/`→`orchestration/` layers. No import-direction change.
- **⚠️ Ask-first — new abstraction:** the binding contract → **ADR-0032** (done).
- **No new dependency:** `zipfile` + `tomllib` are stdlib (3.13). `sync_skills.py`
  currently imports only `argparse`/`sys`/`pathlib`; `pack_skills.py` adds
  `zipfile`. Confirmed no `pyproject.toml` change.
- **🚫 Never:** no secrets, no live LLM in CI — all guards deterministic file ops.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Rewriting six LIVE skills breaks live SDD UX | FR-8a auto-resolve from reference binding; FR-3 round-trip test; Stage-7 review. |
| Placeholder guard false-positives on English "constitution" | Guard keys on exact binding *tokens* (`AGENTS.md`, `make check`), not words (§6). |
| Example genericization loses concreteness for THIS repo | Concrete instances move to binding `examples`; reference binding restores them for this-repo readers. |
| Copilot path-specific support is cloud-agent/code-review-only today | Documented limitation (§6); repo-wide file covers the rest; not a blocker. |
| Zip `--check` flaky across machines | Fixed member order + normalized mtime (FR NFR §7). |
