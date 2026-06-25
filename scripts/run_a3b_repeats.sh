#!/usr/bin/env bash
# A3b N=3 cheap-arm repeats over the 10-row L1 corpus (the verdict is L1-only;
# L2/L3 are ungraded pending the gold-set process, so driving them wastes calls).
# Baseline gpt-4o-mini vs candidates {claude-haiku-4-5, deepseek-v4-flash}, x3.
# Scoring: L1 deterministic (hardened, failure-phrase guard) + provider-error guard.
# PACING: a delay between runs avoids the rate-limit/provider-error cascade that
# contaminated the v2 sweep (sustained sequential load -> litellm InternalServerError).
set -u
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent
set -a; [ -f .env ] && . ./.env 2>/dev/null; set +a

CORPUS=cache/model_ab_answer/l1_full.jsonl   # 10 L1 rows only
PY=.venv/bin/python
PACE_SECONDS="${PACE_SECONDS:-30}"            # delay between runs (override via env)

for cand in claude-haiku-4-5 deepseek-v4-flash; do
  for i in 1 2 3; do
    # re-seed deterministic fixtures before every drive (idempotent)
    $PY -m scripts.seed_model_ab_workspace >/dev/null 2>&1
    runid="a3b_l1_${cand//[^a-z0-9]/}_v3r${i}"
    echo "=== DRIVE $runid (baseline gpt-4o-mini vs $cand, run $i) ==="
    $PY -m scripts.model_ab_eval \
      --corpus "$CORPUS" \
      --baseline gpt-4o-mini --candidate "$cand" \
      --answer-score \
      --out cache/model_ab --run-id "$runid" 2>&1 \
      | grep -E "^VERDICT|answer accuracy|report:" || true
    echo "--- pacing ${PACE_SECONDS}s to avoid provider rate-limit cascade ---"
    sleep "$PACE_SECONDS"
  done
done
echo "=== ALL REPEATS DONE ==="
