# Plan — `coach_goldset_v1` assembly (Task 3.7)

**Spec:** [coach-goldset-v1-assembly.spec.md](coach-goldset-v1-assembly.spec.md) ·
**Precedent:** `services/governance/goaljudge_goldset_dataset.py` +
`scripts/assemble_goaljudge_goldset.py` (mirror both) ·
**No ADR** — no new dependency / service / trust type / invariant deviation
(a governance dataset module alongside the existing GoalJudge one).

## 1. Approach

Mirror the GoalJudge gold-set module 1:1 in structure, specialized to the coach
`answer_leakage` label. A new `services/governance/coach_goldset_dataset.py` holds
the pure `CoachGoldsetItem` + `CoachGoldsetManifest` types, the firewall/hash
functions, and `build_coach_goldset_manifest`. A new
`scripts/assemble_coach_goldset.py` is the thin CLI (mirrors
`assemble_goaljudge_goldset.py`'s `--provisional` mode) that seeds from the 22
corrected `cases.jsonl` rows and writes a local JSON artifact. All pure/offline →
L1, in `make check`. The 200-row + α floors are present but skipped under
`--provisional`, stamping the manifest honest.

## 2. File-level touchpoints

| File | Change | Layer / gate |
|---|---|---|
| `services/governance/coach_goldset_dataset.py` | **NEW.** `CoachGoldsetItem` (`extra="forbid"`, FR-6 fields incl. `mistake_location_pass`); reuse `GoldsetSplit`/`GoldsetProvenance` from the GoalJudge module (same layer — import-safe) or mirror if not; **`LeakChannel` mirrored LOCALLY** (Invariant #7 — no `components/` import); firewall `model_validator` (FR-1), `answer_leakage` required (FR-2), taxonomy `field_validator` for `leak_channel`/`failure_mode` (FR-3); `CoachGoldsetManifest`; `compute_test_split_hash` (FR-5, copy the GoalJudge SHA-256-over-sorted-canonical-JSON); `build_coach_goldset_manifest` (FR-4/7/8/9); leak-class share reporter (FR-7 — report-only, no oversample at N=21); `alpha_answer_leakage` helper that **calls `services.governance.iaa.krippendorff_alpha_nominal`** and maps its `NaN`→`None` (FR-9, AP-6 — reuse, never reimplement). | `services/governance/` — **Invariant #7** |
| `scripts/assemble_coach_goldset.py` | **NEW.** CLI mirroring `assemble_goaljudge_goldset.py`: `--cases` (default the corrected `cases.jsonl`), `--out`, `--frozen-at`, `--provisional` (skip floors, stamp `provisional=true`), `--rubric-version` (default `coach_rubric_v1_revised`). Seeds `CoachGoldsetItem`s from cases rows (FR-10), writes local JSON (FR-11). Non-zero exit on any firewall/parse violation (never writes a bad artifact). | `scripts/` |
| `tests/services/governance/test_coach_goldset_dataset.py` | **NEW.** FR-1..FR-9 L1 tests (failure-path first: firewall, missing-leakage, unknown-channel/failure_mode, provisional-flag, hash determinism + tamper, extra-forbid, α-null). | tests/ |
| `tests/scripts/test_assemble_coach_goldset.py` | **NEW.** FR-10/11: seeds from cases.jsonl; writes local artifact; makes NO network call (inject a no-op/in-memory client like the GoalJudge test). | tests/ |
| `tests/fixtures/coach_goldset/coach_goldset_v1.json` (or `cache/`) | **NEW (generated).** The committed provisional artifact (rows + manifest). Path matches the GoalJudge convention. | fixture (generated) |
| `docs/plan/subject-coach-agent.plan.md` | Ledger row 3.7 → DONE (provisional) + remaining human-α gate noted. | docs |

## 3. ADR / gate triggers

**None fire.** No new `pyproject.toml` dependency (Pydantic + stdlib). No new
horizontal *service* (it is a dataset module in the existing `services/governance/`
package, same class as `goaljudge_goldset_dataset.py` which shipped without its own
ADR). No new graph node, no `trust/` type. `test_adr_ratchet.py` is satisfied: no
trigger path changed. The one invariant in play (#7, services↛components) is
*respected*, not deviated from — so no ADR, but §2 flags it as the thing to not
break.

## 4. Build order (evidence-gated, TDD)

**Stage A — the pure type + functions (offline, red/green).**
1. Red: firewall (FR-1), missing-`answer_leakage` (FR-2), unknown-channel/failure_mode
   (FR-3) rejection tests on `CoachGoldsetItem`. Watch fail (type doesn't exist).
2. Green: define `CoachGoldsetItem` (`extra="forbid"`, enums, validators, local
   `LeakChannel` mirror). `pytest tests/architecture/ -q` green (no components import).
3. Red→green: `compute_test_split_hash` determinism + tamper (FR-5); manifest field
   set + `rubric_version` (FR-8); provisional-flag (FR-4); α-null/undecidable (FR-9).

**Stage B — the assembler CLI.**
4. Red: `test_seeds_from_cases_jsonl` (FR-10) + `test_writes_local_artifact_no_network`
   (FR-11). Watch fail.
5. Green: `assemble_coach_goldset.py` — load cases → map to items → split (60/40,
   synthetic dev-only) → `build_coach_goldset_manifest(--provisional)` → write JSON.

**Stage C — produce + commit the provisional artifact.**
6. Run the assembler on the 22 corrected `cases.jsonl`; commit
   `coach_goldset_v1.json` with `provisional=true`, `human_alpha=null`, row_count=22,
   `rubric_version=coach_rubric_v1_revised`. Paste the run output.
7. `make check` green. Ledger row 3.7 → DONE (provisional).

## 5. Risk + iteration

- **Layer slip (Invariant #7):** the tempting shortcut is `from components.schemas
  import LeakChannel`. FORBIDDEN. Mirror the 5 values locally; a tiny drift-sensor
  test (values match the components enum by *value*, checked without importing across
  the layer — read the file text, cf. ADR-0017 FR-12) keeps them aligned. **This is
  the one real risk** — `tests/architecture/` is the backstop.
- **Provisional honesty:** the artifact MUST refuse the cert. If a bug lets a
  22-row set look cert-ready, 3.8 would falsely certify. FR-4's `provisional=true`
  stamp + FR-9's α-null are the guards; test both reject-paths first.
- **Split degeneracy at N=22:** 40% test ≈ 9 rows, few leak positives. Acceptable —
  it is provisional; the real split is the human 200–300-row set. The hash + firewall
  logic is what's being proven now, not the statistical power.

## 6. Out of scope

- The **human double-labeling** pass + real α computation (feeds FR-9 later, gates 3.8).
- The **Langfuse push** of `coach_goldset_v1` (creds-gated, manual, later).
- The **cert** itself (`evaluate_coach_enable_gates`) — that is Task 3.8.
- Harvesting the 292-turn corpus into gold rows (needs the human coding pass first).
