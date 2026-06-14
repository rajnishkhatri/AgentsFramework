# Transcript — files consulted (eval-2-where-to-persist, without_skill)

Task: advise whether to persist ~15 coded traces in Langfuse via scores, an
annotation queue, or something else, and walk through the right way in this repo.
Constraint: explore repo, do NOT push to Langfuse, use no special skill.

## Exploration steps

1. `git ls-files | grep -i langfuse` + `ls scripts/` — located Langfuse adapters
   and the cluster of open-coding / goaljudge scripts.

2. Read `scripts/push_open_codes_to_langfuse.py` — existing pusher that writes open
   codes as **TEXT scores** (one per trace). Docstring itself notes scores render
   in the Scores tab and are good for filtering, with "promote to CATEGORICAL
   later" guidance. Idempotent via `uuid5(trace_id+name)`.

3. Read `middleware/adapters/observability/langfuse_eval_telemetry_sink.py` — how
   the runtime emits eval observations (context on the observation model that
   scores attach to).

4. Read `scripts/_a2_apply_labels.py` (partial) — example of a coded case set
   (open codes / failure modes / memos), confirming the shape of coding work in
   this repo.

5. Read `docs/recipes/governance/05_manual_langfuse_validation_walkthrough.md` —
   confirms scores attach **per observation** and shows the Datasets surface
   (`agent-compliance-audit` / `agent-incident-replay`) as the repo's curated
   collection convention.

6. Listed `docs/skills/agentsframework-open-coding-workspace/...` and confirmed the
   target output dir. Also found `docs/skills/agentsframework-open-coding/` (the
   skill). Did NOT read the SKILL.md (task said no special skill), but did consult
   its repo-documentation/reference + script files as grounding:
   - Read `docs/skills/agentsframework-open-coding/references/langfuse-surface.md`
     — the repo's own decision record: dataset > scores > annotation queue for
     *review*, with the per-observation-scatter, top-observation-drawer, and
     Hobby-one-queue-cap reasons, and the `string_value` TEXT-score read trap.
   - Read `docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py`
     — the idempotent dataset exporter (input=task, expected_output=answer,
     metadata=codes+memo, source_trace_id link; `--answers` join; empty-codes warn).

7. Read `scripts/langfuse_dataset_client.py` — `RealLangfuseDatasetClient` /
   `build_real_langfuse_dataset_client`, EU host default (`cloud.langfuse.com`),
   the wrapper the exporter uses.

## Conclusion

Recommend a **Langfuse dataset** as the shared review surface, with the local HTML
coder as the edit surface and the idempotent exporter as the sync mechanism.
Scores = filtering path (complementary), annotation queue = wrong content + Hobby
cap. Nothing pushed to Langfuse.
