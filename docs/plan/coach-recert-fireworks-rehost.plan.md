# Plan — Coach leakage judge re-cert on Fireworks-hosted open-weight models

**Status:** Draft — 2026-07-06
**Owner:** Rajnish Khatri
**Derives from:** [spec](coach-recert-fireworks-rehost.spec.md) (12 FRs, APPROVED) ·
[brainstorm](coach-recert-reliability.brainstorm.md) (Stage-1 gate) ·
constitution `AGENTS.md` (8 invariants) + `services/AGENTS.md` (H2, AP-1).
**ADR:** [ADR-0019](../adr/0019-fireworks-host-adapter.md) — the ⚠️ Ask-first payload
(new trust-boundary host adapter + the model/host reversal of the `decisions.md`
glm-5.2/Z.ai choice).

---

## 1. Architecture — the shape of the change

The repo already has the whole direct-provider substrate; Fireworks is **one more
host behind the same port**, not a new mechanism:

```
                        select_judge_profile(pin=COACH_JUDGE_MODEL)      ← FR-6 (existing)
                                     │  picks a ModelProfile
                                     ▼
        get_llm(profile) ── profile.provider=="direct" ──► _DirectChatModel   (llm_config.py:524, existing)
                                     │
                                     ▼
        get_direct_provider(profile) ─────────────────────────────────┐       (__init__.py, EXTEND)
             │  dispatch by profile family                            │
             ├─ name.startswith("glm-5") & host==z.ai  ─► GLMDirectProvider(base_url=Z.AI)   (existing, FR-2)
             └─ name endswith "-fireworks"             ─► FireworksDirectProvider(base_url=FW) (NEW, FR-4)
                                     │                        └─ resolve_fireworks_api_key()   (config.py, NEW, FR-1)
                                     ▼
             POST https://api.fireworks.ai/inference/v1/chat/completions
                   model = profile.litellm_id = "accounts/fireworks/models/<m>"  (FR-5, carried by profile)
                   Authorization: Bearer $FIREWORKS_API_KEY
                                     │
                                     ▼
                          LLMCompletion  (trust/protocols.py — unchanged contract)
```

**Key design decision — dispatch by name/family, NOT a new `ModelProfile.host` field.**
`ModelProfile` (services/base_config.py:16) has no host/base_url/api_key_env field today;
`get_direct_provider` already derives the host from the model family (glm → Z.ai). Adding a
`host` field to `ModelProfile` touches a config type consumed by every layer for a two-host
need — heavier than warranted, and a schema change is itself an ⚠️ Ask-first. Instead a
Fireworks profile is recognized by a `-fireworks` name suffix and carries its wire id in
`litellm_id`. This mirrors the existing GLM dispatch exactly, needs **zero** schema change,
and keeps H2 (no host string in any caller — the host lives in `services/llm_providers/`).
The rejected `host`-field alternative is recorded in ADR-0019 §Options.

**Adapter reuse.** `GLMDirectProvider.__init__` already takes `base_url` as a constructor
param (glm_direct.py:42) and the wire body is plain OpenAI-shape (`model`, `messages`,
`tools`, `temperature`, `max_tokens`) — identical to Fireworks' OpenAI-compatible surface.
So the Fireworks adapter is **not** a copy of the whole REST/parse logic. Two options,
decided at task time by whichever is cleaner under test:
- **(A)** a thin `FireworksDirectProvider` subclass that only overrides the base_url default
  + the `provider=`/error label ("fireworks" not "glm" in `TrustProviderError`); inherits
  `acompletion`/`_parse_completion`.
- **(B)** generalize the shared REST/parse into a small `_openai_compat.py` helper both call.

Recommend (A) — least churn, keeps the proven glm parse path byte-identical; (B) only if the
`provider=` label leaking "glm" into a Fireworks error proves awkward. Either keeps the parse
(thinking-block stripping, tool-call mapping) in one tested place.

**Grammar-JSON (FR-8) is an adapter capability, off by default.** A later, optional
`response_format` param on `acompletion` (JSON-schema for the `PedagogyVerdict` required
fields). NOT built in the first pass — GLM passed the bar without it, and the research caveat
is that Fireworks `response_format` disables reasoning output (the rubric already lives in the
prompt). Scoped as a deferred task, gated behind a profile/param flag, never a harness branch.

## 2. File-level touchpoints

| # | File | Change | FR |
|---|------|--------|----|
| T1 | `services/llm_providers/config.py` | Add `resolve_fireworks_api_key()` → `os.environ.get("FIREWORKS_API_KEY")` (mirror of the GLM resolver). | FR-1 |
| T2 | `services/llm_providers/fireworks_direct.py` **(new)** *or* extend `glm_direct.py` | `FireworksDirectProvider` satisfying `LLMProvider`: `base_url` default `https://api.fireworks.ai/inference/v1`, `provider="fireworks"` in `TrustProviderError`. Option (A) subclass / (B) shared helper — decided under test. | FR-4 |
| T3 | `services/llm_providers/__init__.py` | Extend `get_direct_provider`: add a `name.endswith("-fireworks")` (or family=="fireworks") branch → `resolve_fireworks_api_key()`, raise `ConfigurationError` naming `FIREWORKS_API_KEY` if unset, else construct the Fireworks adapter with its base_url. Z.ai branch **unchanged** (FR-2). Export the new class. | FR-1, FR-2, FR-4 |
| T4 | `services/llm_config.py` | Add a `glm-5.2-fireworks` `ModelProfile` (`provider="direct"`, `litellm_id="accounts/fireworks/models/glm-5.2"`, `supports_temperature=True`) + the 3 cross-family candidate profiles (`deepseek-r1-fireworks`, `qwen3-235b-fireworks`, `ln-ultra-fireworks` — ids confirmed at screening, FR-7). New `_FIREWORKS_PROFILES` list + a `"fireworks"` entry in `_MODEL_PROFILE_SETS` (default = `glm-5.2-fireworks`). Add to `_ALL_PROFILES` union. | FR-5, FR-6, FR-7 |
| T5 | `scripts/run_coach_calibration.py` | FR-3 provenance: add `model: str` param to `replay_test_split_rows`, thread `profile.name` from `build_live_judges()`→`main`, stamp `"judge_model": model` into each dumped row. (Cert `model` is already `profile.name` — this makes every *row* self-describing so an env-drift like run1/run2 is visible per-row, not only in the cert header.) | FR-3 |
| T6 | `scripts/screen_coach_candidates.py` **(new)** | Screening harness (FR-7): for each candidate profile in the `fireworks` set, run the frozen `coach_recert_split_v1.json` once (temp-0), record TNR/TPR/κ/abstain to a JSON scoreboard; a profile Fireworks 404s is recorded `unavailable`, not fabricated. Reuses `replay_test_split_rows` + `cert_from_labels`; thin — delegates, no new domain logic. | FR-7 |
| T7 | `docs/adr/0019-fireworks-host-adapter.md` **(new)** + index.md + log.md | ADR (Context / Options incl. rejected `host`-field + rejected other hosts / Rationale incl. five-probe scoreboard + host research / Consequences). Link from `get_direct_provider` + `decisions.md`. | NFR |
| T8 | `docs/adr/decisions.md` | Append the glm-5.2/Z.ai → glm-5.2/Fireworks **reversal** line pointing at ADR-0019. | NFR |
| T9 | `docs/plan/coach-recert-fireworks-rehost.tasks.md` **(new)** | The atomic task list (Stage-3), 1:1 to the FRs. | — |

**Untouched by design:** `glm_direct.py` Z.ai constants (FR-2 — Z.ai path stays byte-identical
unless option (B) is chosen, in which case only the shared parse moves, not the Z.ai base_url);
`trust/protocols.py` (`LLMProvider`/`LLMCompletion` contract unchanged — FR-4 conforms, doesn't
alter); `subject_coach_judges.py` (judge logic unchanged — this is host/model only); the frozen
split + its L1 gates; `cert_from_labels`/FR-9 exit-bar logic (FR-9 UNCHANGED).

## 3. Tests (offline L1/L2 in `make check`; live FR-9 manual)

| Test | Asserts | FR |
|------|---------|----|
| `test_fireworks_key_missing_fails_closed` | select a `-fireworks` profile with `FIREWORKS_API_KEY` unset → `ConfigurationError` naming the var; NOT a Z.ai fallback. (monkeypatch env) | FR-1 |
| `test_zai_path_unchanged_by_fireworks` | glm-5.2 (Z.ai) profile still resolves `GLM_API_KEY`/`ZAI_API_KEY` + Z.ai base_url; Fireworks profile present doesn't perturb it. | FR-2 |
| `test_fireworks_adapter_posts_openai_shape` | `FireworksDirectProvider` via `httpx.MockTransport` POSTs `…/inference/v1/chat/completions`, Bearer `FIREWORKS_API_KEY`, body `{model, messages}`; maps a canned response → `LLMCompletion` (offline, no live call). | FR-4 |
| `test_fireworks_wire_model_id_from_profile` | the model id on the wire is the profile's `litellm_id` (`accounts/fireworks/models/glm-5.2`), not string-munged in the caller. | FR-5 |
| `test_pin_reaches_fireworks_profile` | `select_judge_profile(models=fireworks_set, model_pin="glm-5.2-fireworks")` returns the direct/Fireworks profile; absent pin → KeyError naming it. | FR-6 |
| `test_screen_records_unavailable_candidate` | screening harness records a 404/unserved candidate as `unavailable`, not a fabricated 0.0 score; a served candidate yields a TNR/TPR/κ row. (MockTransport 404 + 200) | FR-7 |
| `test_dumped_row_carries_judge_model` | a dumped label row includes `judge_model == profile.name` (stub judge, offline) — the FR-3 stamp. | FR-3 |
| `test_grammar_json_off_by_default` *(deferred w/ FR-8)* | absent the flag, the adapter sends NO `response_format`; with it, the schema is attached. | FR-8 |
| **live FR-9** (manual, creds-gated) | ≥3 temp-0 replays on the winner, every run TNR≥0.95 ∧ TPR≥0.90 ∧ κ≥0.75, zero-flip; committed labels replayed offline in CI. | FR-9 |

**TAP discipline:** failure paths first (FR-1 fail-closed, FR-7 unavailable). TAP-2: adapter
tests use `httpx.MockTransport` (one legit external boundary), not mock-piles. No live LLM in CI
(FR-11) — the live cert is manual, its labels committed + replayed offline.

## 4. Sequencing (dependency order)

1. **T1 → T3** (key resolver → factory branch → adapter) — the enabling seam. T2 lands with T3.
2. **T4** (profiles) — needs T1–T3 so a built profile resolves.
3. **T5** (provenance stamp) — independent of T1–T4; do-regardless (D0). Can land first.
4. **T6** (screening harness) — needs T4 (the fireworks profile set) + T5 (per-row model stamp).
5. **T7/T8** (ADR-0019 + decisions.md reversal) — authored alongside T1–T4 (the seam they govern);
   the `stop_adr_reminder` + `test_adr_ratchet` gate requires the ADR before merge.
6. **Offline gate:** `make check` + `pytest tests/architecture/ -q` green after each task.
7. **Live (out of this offline pass, creds-gated):** operator exports `FIREWORKS_API_KEY`, runs
   T6 screening → picks winner → runs the ≥3-replay FR-9 cert → commits labels. The agent cannot
   run these (secrets never through the agent); it prepares the exact commands + records outcomes.

## 5. Constitution cross-check (Stage-4 preview)

- **Inv #2 (trust kernel zero deps):** untouched — `trust/protocols.py` contract unchanged.
- **Inv #4 (services framework-agnostic):** the adapter imports only `trust/` + stdlib + httpx;
  no langgraph/langchain. ✅
- **Inv #7 (services ⊥ components):** adapter + factory know nothing of the judge. ✅
- **AP-1 (shared types in trust/):** `LLMCompletion`/`LLMProvider` stay in `trust/`; no new
  shared type in a service. ✅
- **H2 (no hardcoded host/model in callers):** host string confined to `services/llm_providers/`;
  selection via `COACH_JUDGE_MODEL` pin + profile set. ✅
- **⚠️ Ask-first → ADR:** T7/T8 satisfy the ratchet (new trust-boundary host + decisions.md
  reversal). No new `pyproject.toml` dependency (rides existing httpx). ✅
- **G8 (no test weakening):** all new tests are additive; no existing `def test_*` removed. ✅

## 6. Open items carried to tasks

- Exact Fireworks model ids for DeepSeek-R1 / Qwen3-235B / LN-Ultra — confirmed at screening
  (FR-7 records `unavailable` for any 404). The `glm-5.2-fireworks` id
  (`accounts/fireworks/models/glm-5.2`) is the lead and is assumed servable; screening confirms.
- Dedicated vs shared Fireworks endpoint (FR-10) — a shared-endpoint zero-flip failure is an
  honest recorded non-ENABLE, not a blocker to running the screen/cert.
- Adapter option (A) subclass vs (B) shared helper — decided under the T2 test.
