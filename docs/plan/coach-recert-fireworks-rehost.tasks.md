# Tasks — Coach leakage judge re-cert on Fireworks-hosted open-weight models

**Spec:** [coach-recert-fireworks-rehost.spec.md](coach-recert-fireworks-rehost.spec.md) ·
**Plan:** [coach-recert-fireworks-rehost.plan.md](coach-recert-fireworks-rehost.plan.md) ·
**ADR:** [ADR-0019](../adr/0019-fireworks-host-adapter.md)

Task groups **F1 → F6** (offline, TDD red→green, paste failing output first, all in
`make check`, no live LLM) + a manual **F7** live gate (creds-gated, agent prepares commands
only). Dependency order from plan §4: F0(provenance, independent) · F1→F2→F3(the host seam) ·
F4(profiles, needs F1–F3) · F5(screening, needs F3+F4+F0) · F6(ADR/docs, alongside) · F7(live).

## Checklist — every FR collapses to a measurable claim (Stage 3 gate)

| FR | Measurable claim | Test oracle |
|----|------------------|-------------|
| FR-1 | a `-fireworks` profile selected with `FIREWORKS_API_KEY` unset ⇒ `ConfigurationError` naming the var; NOT a Z.ai fallback | monkeypatch env unset → `pytest.raises(ConfigurationError, match="FIREWORKS_API_KEY")` |
| FR-2 | glm-5.2 (Z.ai) still resolves `GLM_API_KEY`/`ZAI_API_KEY` + Z.ai base_url; Fireworks profile present doesn't perturb it | assert Z.ai provider's `_base_url` == Z.ai URL with both profiles registered |
| FR-3 | each dumped label row carries `judge_model == profile.name` | stub judge + a dump path → parse JSONL, assert every row has the key/value |
| FR-4 | Fireworks adapter POSTs `…/inference/v1/chat/completions`, Bearer `FIREWORKS_API_KEY`, body `{model,messages}` → `LLMCompletion` | `httpx.MockTransport` captures the request; assert URL/header/body; canned 200 → assert mapped completion |
| FR-5 | wire model id == profile `litellm_id` (`accounts/fireworks/models/glm-5.2`), not munged in caller | MockTransport captures `payload["model"]`; assert exact string from the profile |
| FR-6 | `select_judge_profile(fireworks_set, model_pin="glm-5.2-fireworks")` → the direct/Fireworks profile; absent pin ⇒ KeyError naming it | exact-assert returned profile.name + provider; `pytest.raises(KeyError)` |
| FR-7 | screening records a 404/unserved candidate as `unavailable` (not a fabricated 0.0); a served candidate yields TNR/TPR/κ | MockTransport 404 → assert `status=="unavailable"`; 200 canned labels → assert metric row |
| FR-8 *(deferred)* | absent the flag the adapter sends NO `response_format`; with it, the schema is attached | MockTransport captures body; assert key absent by default / present when enabled |
| FR-9 | ≥3 temp-0 replays on the winner, every run TNR≥0.95 ∧ TPR≥0.90 ∧ κ≥0.75, zero-flip | **live/manual** (F7); committed labels replayed offline by the existing cert path in CI |
| FR-10 | shared-endpoint zero-flip failure ⇒ recorded non-ENABLE, never a floor relaxation | posture assertion in F7 runbook; the cert code already refuses below-floor (no change) |
| FR-11 | screen + cert are manual/local; CI replays committed labels only | no new live-LLM test in CI (grep gate already present); runbook notes `FIREWORKS_API_KEY` export |
| FR-12 | gpt-4o anchor on the same split retained as before/after diagnostic, non-gating | already recorded (findings doc); F7 re-notes it — no code change |

All offline FRs (1–8) collapse to exact-assert L1/L2 oracles with `httpx.MockTransport` as the
single external boundary → **no unmeasurable offline criterion**. FR-9/10/12 are the live gate
(F7). Proceed.

---

## F0 — provenance stamp (FR-3, independent / do-regardless)

**Files:** `scripts/run_coach_calibration.py`,
`tests/scripts/test_run_coach_calibration.py` (or the existing calibration test module).

- **Red:** `test_dumped_row_carries_judge_model` — drive `replay_test_split_rows` with a stub
  judge + a tmp dump path + `model="glm-5.2-fireworks"`; read the JSONL back; assert every row
  has `row["judge_model"] == "glm-5.2-fireworks"`. Run → paste failing output (KeyError / no
  such param).
- **Green:** add `model: str = ""` param to `replay_test_split_rows`; add
  `"judge_model": model` to the `row` dict (line ~228); thread `profile.name` from `main`
  (the `model` already returned by `build_live_judges`) into the call. Cert `model` is already
  `profile.name` — unchanged.
- **Verify:** the new test green; existing calibration tests unaffected; `make check`.

## F1 — Fireworks key resolver (FR-1 half)

**Files:** `services/llm_providers/config.py`,
`tests/services/llm_providers/test_config.py` (or new).

- **Red:** `test_resolve_fireworks_api_key_reads_env` (set/unset → value/None). Run → paste
  failing output (AttributeError / no such function).
- **Green:** add `resolve_fireworks_api_key() -> str | None: return os.environ.get("FIREWORKS_API_KEY")`.
- **Verify:** test green; `make check`.

## F2 — Fireworks adapter (FR-4, FR-5)

**Files:** `services/llm_providers/fireworks_direct.py` (new) **or** parameterized extension of
`glm_direct.py` (decide under test — plan §1 option A subclass vs B shared helper);
`tests/services/llm_providers/test_fireworks_direct.py` (new).

- **Red:** `test_fireworks_adapter_posts_openai_shape` — build the adapter with an
  `httpx.MockTransport` asserting the request is `POST …/inference/v1/chat/completions`, header
  `Authorization: Bearer test-key`, body `{"model": "...", "messages": [...]}`, and a canned 200
  maps to an `LLMCompletion` (content + usage). `test_fireworks_wire_model_id_passthrough` — the
  captured `payload["model"]` equals exactly what was passed (proves FR-5: no munging in the
  adapter). Run → paste failing output.
- **Green:** implement `FireworksDirectProvider` satisfying `LLMProvider` with base_url default
  `https://api.fireworks.ai/inference/v1` and `provider="fireworks"` in `TrustProviderError`.
  Prefer option (A): subclass `GLMDirectProvider`, override only the base_url default + the error
  label, inherit `acompletion`/`_parse_completion`. If the "glm" error label leaking into a
  Fireworks error is awkward, switch to (B): lift the shared REST/parse into `_openai_compat.py`.
- **Verify:** both tests green; TAP-2 (one MockTransport boundary, no mock-pile); `make check` +
  `pytest tests/architecture/ -q` (adapter imports only trust/ + stdlib + httpx).

## F3 — factory dispatch + fail-closed (FR-1 other half, FR-2)

**Files:** `services/llm_providers/__init__.py`,
`tests/services/llm_providers/test_get_direct_provider.py` (or existing).

- **Red:** `test_fireworks_key_missing_fails_closed` (a `-fireworks` profile + env unset →
  `ConfigurationError` matching `FIREWORKS_API_KEY`, and assert it's NOT a `GLMDirectProvider`);
  `test_zai_path_unchanged_by_fireworks` (glm-5.2 profile → `GLMDirectProvider` with Z.ai
  base_url, even with a fireworks profile in play); `test_fireworks_profile_builds_adapter`
  (key set → a `FireworksDirectProvider` with the Fireworks base_url). Run → paste failing
  output.
- **Green:** add a branch in `get_direct_provider`: `name.endswith("-fireworks")` (or a family
  check) → `resolve_fireworks_api_key()`, raise `ConfigurationError` naming `FIREWORKS_API_KEY`
  if unset, else `FireworksDirectProvider(api_key=key)` (base_url from the class default). Z.ai
  branch untouched (ordered before, keyed on `startswith("glm")` **without** the suffix — verify
  `glm-5.2-fireworks` doesn't match the Z.ai branch: the suffix check must win / be ordered
  first). Export the new class in `__all__`.
- **Verify:** all three tests green; `make check`. **Ordering guard:** add an assertion that
  `glm-5.2-fireworks` routes to Fireworks, not Z.ai (the name starts with "glm" *and* ends with
  "-fireworks" — the Fireworks branch must be checked first or the glm-branch must exclude the
  suffix).

## F4 — Fireworks profiles + profile set (FR-5, FR-6)

**Files:** `services/llm_config.py`,
`tests/services/test_llm_config.py` (or the model-registry test module).

- **Red:** `test_pin_reaches_fireworks_profile` (`select_judge_profile` isn't in this module —
  test the registry side: `build_model_registry("fireworks")` returns a set containing
  `glm-5.2-fireworks` with `provider=="direct"` and `litellm_id=="accounts/fireworks/models/glm-5.2"`);
  `test_fireworks_set_default` (default model of the set). Also a `select_judge_profile` test
  lives with `run_coach_calibration`: `test_pin_selects_fireworks` — pin `glm-5.2-fireworks`
  against the fireworks set → that profile; absent → KeyError naming it. Run → paste failing
  output.
- **Green:** add `_FIREWORKS_PROFILES` (glm-5.2-fireworks + the 3 candidate profiles —
  deepseek-r1-fireworks / qwen3-235b-fireworks / ln-ultra-fireworks, ids per FR-7, confirmed at
  screening; `provider="direct"`, `supports_temperature=True`, `max_output_tokens` sized for
  reasoning); a `"fireworks"` entry in `_MODEL_PROFILE_SETS` (default `glm-5.2-fireworks`); add
  to `_ALL_PROFILES` union.
- **Verify:** tests green; `make check`.

## F5 — screening harness (FR-7)

**Files:** `scripts/screen_coach_candidates.py` (new),
`tests/scripts/test_screen_coach_candidates.py` (new).

- **Red:** `test_screen_records_unavailable_candidate` (a candidate whose adapter 404s →
  scoreboard row `status="unavailable"`, no fabricated score);
  `test_screen_scores_served_candidate` (a canned-label candidate → a row with TNR/TPR/κ/abstain
  computed from `cert_from_labels`). Drive both offline with a stub judge / MockTransport. Run →
  paste failing output.
- **Green:** a thin harness: for each profile in the `fireworks` set, load the frozen
  `coach_recert_split_v1.json`, run one temp-0 pass via `replay_test_split_rows` (reused),
  compute per-candidate metrics via `cert_from_labels` (reused), write a JSON scoreboard;
  wrap each candidate so a `TrustProviderError`/404 records `unavailable` instead of raising.
  No new domain logic — delegates to the existing cert/replay functions.
- **Verify:** tests green; `pytest tests/architecture/ -q` (script imports don't cross layers);
  `make check`.

## F6 — ADR-0019 + decisions.md reversal (NFR, alongside F1–F4)

**Files:** `docs/adr/0019-fireworks-host-adapter.md` (✅ written),
`docs/adr/index.md` (✅), `docs/adr/log.md` (✅), `docs/adr/decisions.md` (✅ reversal line).

- **Verify:** `test_adr_ratchet` passes (a `docs/adr/*` file exists for the touched ⚠️ Ask-first
  seam — `services/llm_providers/`); cite-lint clean for ADR-0019; OKF triple present
  (frontmatter `type:` + index entry + log line). Link ADR-0019 from `get_direct_provider`
  (a `# See ADR-0019` comment at the Fireworks branch).

## F7 — live re-cert (FR-9/10/12, MANUAL, creds-gated — agent prepares, operator runs)

**Not an offline task.** The agent cannot run live LLM calls (secrets never through the agent).
The agent produces the exact command sequence + records outcomes into
`docs/IAA/coach/recert/coach_recert_findings.md`. Operator steps:

1. Export the key to the shell: `export FIREWORKS_API_KEY=…` (the repo does not auto-load `.env`).
2. **Screen** (F5): `MODEL_PROFILE_SET=fireworks python -m scripts.screen_coach_candidates --goldset tests/fixtures/coach_goldset/coach_recert_split_v1.json` → pick the winner (GLM-5.2 lead; a candidate beats it only on TNR/TPR/κ with the same zero-abstain).
3. **Cert ≥3× temp-0** on the winner (dedicated endpoint if provisioned — FR-10):
   `MODEL_PROFILE_SET=fireworks COACH_JUDGE_MODEL=<winner> python -m scripts.run_coach_calibration --goldset tests/fixtures/coach_goldset/coach_recert_split_v1.json --dump-labels docs/IAA/coach/recert/recert_labels_fw_run{1,2,3}.jsonl` — every run must clear TNR≥0.95 ∧ TPR≥0.90 ∧ κ≥0.75, zero-flip.
4. Commit the label JSONLs; CI replays them offline (FR-11). A shared-endpoint zero-flip failure
   is recorded as a non-ENABLE, not a floor change (FR-10).
5. `COACH_LEAKAGE_GATE_ENABLED` stays OFF — flipping it is a separate human Phase-5 step (spec §5).

---

## Exit

All F0–F6 green in `make check` + `pytest tests/architecture/ -q` → route to Stage-7 review
(**code-review** skill, fresh thread). F7 (live) is gated on the operator's `FIREWORKS_API_KEY`
and is the manual exit gate that produces the committed labels ADR-0019 / ADR-0018 depend on.
