---
type: checklist
title: Phase 5 S6 — mem0 retirement deletion checklist
description: Concrete file/line inventory for the post-24h-soak commit that removes every mem0 surface. Apply ONLY after Phase 5 S5 traffic shift has been stable for 24 hours with zero rollback events.
tags: [checklist, memory, mem0, retirement, cutover]
timestamp: 2026-06-22
status: held-pending-soak
plan_id: replace-mem0-pgvector
related:
  plan: "[replace_mem0_pgvector.plan.md](replace_mem0_pgvector.plan.md)"
  runbook: "[replace_mem0_pgvector.phase5.runbook.md](replace_mem0_pgvector.phase5.runbook.md)"
---

# Phase 5 S6 — mem0 retirement deletion checklist

> **PRE-CONDITION (HARD):** This checklist applies ONLY after Phase 5 S5 has shifted 100% traffic to the pgvector revision AND **24h of stable production** have elapsed with **zero rollback events**. Pre-soak deletion violates the agent execution contract's 24h-rollback rule. The Terraform state for `mem0_api_key` resources stays untouched until S6 — secret + accessor IAM remain in `secret-manager.tf` for fast rollback.

## Acceptance bar (must be true before deletion commit)

- [ ] 24 hours have elapsed since the traffic shift completed
- [ ] No production incident, rollback, or revision pin-back has occurred in that window
- [ ] `EventType.MEMORY_RECALLED` carrier count is non-zero in the last hour of traffic
- [ ] `EventType.MEMORY_STORED` carrier count has grown monotonically since cutover
- [ ] No `MemoryBackendError` spikes in the recall path

If any item above is false → **do not delete; investigate or roll back per runbook**.

## Production code deletions (Python)

| File | Action | Reason |
|---|---|---|
| `services/memory_backends/mem0.py` | DELETE entire file | The only `Mem0MemoryBackend` consumer was the composition selector, retired in Phase 4. |
| `tests/services/memory_backends/test_mem0_backend.py` | DELETE entire file | `_FakeMem0Sdk` fixture goes with it. Phase 2 contract suite already proves `PgVectorMemoryBackend` passes the same `MemoryBackend` Protocol contract. |
| `scripts/mem0_smoke.py` | DELETE entire file | Manual live-smoke for `Mem0MemoryBackend`. No analogue needed — pgvector contract is fully covered by `tests/services/memory_backends/test_pgvector_backend.py` Docker-fixture tests. |

## `pyproject.toml`

```diff
-    "mem0ai>=2.0,<3",
```

(line 28)

Run `uv lock` (or equivalent) to regenerate the lockfile after the deletion.

## Settings (`middleware/composition.py`)

Remove the two mem0 settings fields. Both are now unused after Phase 4's selector swap:

```diff
-    mem0_api_key: str = Field(default="", validation_alias="MEM0_API_KEY")
-    mem0_base_url: str = Field(
-        default="https://api.mem0.ai", validation_alias="MEM0_BASE_URL"
-    )
```

(roughly lines 522–524 — confirm with `grep -n`)

Update the module docstring (line 7) — drop `MEM0_*` from the env-var list.

Update the line-250 NOTE and line-120 NOTE references to mem0 — convert to historical pointers or remove if no longer load-bearing.

## Tests

| File | Action |
|---|---|
| `tests/middleware/test_agent_runtime_composition.py` | Remove the `TestMemoryBackendSelection::test_key_present_selects_mem0_backend` regression-guard test (Phase 4 added it to assert the legacy branch no longer fires; after deletion the assertion target itself is gone). Also remove the `mem0_api_key="..."` kwargs in setup. |
| `tests/middleware/test_composition.py` | Remove the R1 `test_v3_boots_with_mem0_api_key_absent` + `test_v2_boots_with_mem0_api_key_absent` tests (R1 contract no longer meaningful when MEM0_API_KEY is not a recognised env var). Update `V3_ENV` to drop `MEM0_API_KEY`. |
| `tests/middleware/test_server.py` | Update the Phase 3 docstring comment at line 48 (history note only — keep if useful for archeology, else trim). |
| `tests/architecture/test_middleware_layer.py` | Remove `"mem0"` and `"mem0ai"` from the SDK-isolation allowlist (lines 58–59). Update the M-no-cross docstring (line 31, 34, 222) — drop `mem0ai` from the SDK list. |

### Add new architecture assertion (REQUIRED — per plan §Architecture-test additions)

```python
def test_no_mem0_imports_anywhere() -> None:
    """Phase 5 S6 — mem0 is fully retired. No import survives."""
    violations = []
    for path in _python_files():
        text = path.read_text()
        if re.search(r"^\s*(import|from)\s+(mem0|mem0ai)\b", text, re.M):
            violations.append(str(path))
    assert not violations, "Stale mem0 imports:\n" + "\n".join(violations)
```

## Infrastructure (Terraform)

### `infra/dev-tier/`

| File | Lines | Action |
|---|---|---|
| `secret-manager.tf` | ~177–199 (the four `mem0_api_key` blocks: secret + version + accessor IAM + closing brace) | DELETE the entire block |
| `variables.tf` | 178 (`variable "mem0_api_key" { ... }`) | DELETE |
| `outputs.tf` | 57 (`mem0_api_key = ...` in secrets map) | DELETE the key/value pair |
| `terraform.tfvars.example` | the `mem0_api_key = "m0-REPLACE_ME"` line + Phase 5 S4 retention comment | DELETE both |
| `README.md` | 33 (secret-manager rotation list), 115 (sprint-0/1 reuse list) | DELETE the `mem0` mentions |
| `cloud-run.tf` | the Phase 5 S4 narrative comments at ~151, 155, 156, 257 | Optional: trim historical comments now that mem0 surface is gone |

### `infra/gcp/`

| File | Lines | Action |
|---|---|---|
| `secret-manager.tf` | ~195–222 (mem0 secret + version + accessor IAM blocks) | DELETE the entire block |
| `variables.tf` | 101 (`variable "mem0_api_key" { ... }`) | DELETE |
| `outputs.tf` | 48 (`mem0_api_key = ...`) | DELETE |
| `cloud-run-backend.tf` | the Phase 5 S4 narrative comments at ~156, 160, 161, 314 | Optional: trim historical comments |

### `infra/RUNBOOK.md`

Lines 132–133 and 309 — drop the mem0-renewal procedure rows.

## Verification (run before commit)

```bash
# 1) No mem0 references survive anywhere
grep -r "mem0\|mem0ai\|MEM0_" \
  --include="*.py" --include="*.toml" --include="*.tf" --include="*.md"
# MUST return 0 lines

# 2) Architecture tests green with the new assertion
.venv/bin/python -m pytest tests/architecture/ -q

# 3) Full suite still green
.venv/bin/python -m pytest tests/ -q

# 4) Terraform plans cleanly (both tiers)
cd infra/dev-tier && tofu plan
cd ../gcp && tofu plan
# Plans MUST show: mem0_api_key secret + version + accessor → destroyed.
# Nothing else MUST be touched.

# 5) okf_lint
.venv/bin/python scripts/okf_lint.py
```

## Commit shape

Single squash commit with subject:

```
feat(memory): Phase 5 S6 — retire mem0 surface entirely

After 24h stable soak on the pgvector cutover, drop every mem0 reference:
  * services/memory_backends/mem0.py + _FakeMem0Sdk test fixture
  * mem0ai dependency line in pyproject.toml
  * MEM0_API_KEY / MEM0_BASE_URL settings fields
  * Secret Manager resources, variables, outputs in both Terraform tiers
  * Architecture-test allowlist; new "no mem0 imports" assertion added
```

Co-author tag per agent convention.

## After the deletion commit lands

- Update `docs/plans/log.md` with the S6 entry
- Mark this checklist file with `status: completed` in the front-matter
- Author a `~/.claude/projects/.../memory/` entry capturing what was *non-obvious* about the cutover (surprises only)
- Update `docs/plans/index.md` `replace_mem0_pgvector.plan.md` status → `shipped`
