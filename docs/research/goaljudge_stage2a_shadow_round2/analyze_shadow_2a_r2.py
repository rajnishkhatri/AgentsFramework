"""Round-2 gate analysis: pull eval.task_understanding spans + compute the gate.

Gate (Stage 2a, unchanged): gate-pass (source=generated) >= 95%; branch
coverage >= 80% on multi-branch tasks (with the conservative metric filter).
Also reports: per-attempt retry recovery, shadow invariant, rejected_conditions.
"""

import base64
import json
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, "tests/components")
from components.plan_builder import _extract_branches  # noqa: E402
from components.task_understanding import _content_tokens  # noqa: E402


# --- conservative branch filter (mirror of the L3 test's _is_real_branch) ---
def _is_real_branch(branch: str) -> bool:
    if branch.strip().endswith(":"):
        return False
    return len(_content_tokens(branch)) >= 2


def _covers(conditions, task):
    branches = [b for b in _extract_branches(task) if _is_real_branch(b)]
    ctoks = [_content_tokens(c) for c in conditions]
    for b in branches:
        bt = _content_tokens(b)
        if not bt:
            continue
        if not any(bt & ct for ct in ctoks):
            return False
    return True


# --- langfuse creds from .env (never printed) ---
env = {}
for line in open(".env"):
    line = line.strip()
    if line.startswith("LANGFUSE_") and "=" in line:
        k, v = line.split("=", 1)
        env[k] = v.strip().strip('"').strip("'")
HOST = env["LANGFUSE_HOST"].rstrip("/")
AUTH = base64.b64encode(
    f"{env['LANGFUSE_PUBLIC_KEY']}:{env['LANGFUSE_SECRET_KEY']}".encode()
).decode()


def get(url):
    for _ in range(5):
        try:
            req = urllib.request.Request(
                url, headers={"Authorization": f"Basic {AUTH}"}
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2.0)
                continue
            raise
    raise RuntimeError("exhausted retries")


runs = [json.loads(l) for l in open("/tmp/shadow_2a_r2_runs.jsonl")]
results = []
for r in runs:
    trace = r["trace_id"]
    task = json.load(open("/tmp/shadow_2a_r2_tasks.json"))[r["case_idx"]]
    url = f"{HOST}/api/public/observations?traceId={trace}&name=eval.task_understanding&limit=50"
    data = get(url)
    obs = data.get("data", [])
    rec = {"i": r["case_idx"], "trace": trace[:8], "task": task, "span": bool(obs)}
    if obs:
        out = obs[0].get("output") or {}
        if isinstance(out, str):
            try:
                out = json.loads(out)
            except Exception:
                out = {}
        conds = out.get("success_conditions") or []
        rec.update(
            source=out.get("source"),
            mode=out.get("mode"),
            consumed=out.get("consumed"),
            attempts=out.get("attempts"),
            n_rejected=len(out.get("rejected_conditions") or []),
            fallback_reason=(out.get("fallback_reason") or "")[:200],
            n_cond=len(conds),
            coverage=_covers(conds, task) if out.get("source") == "generated" else None,
        )
    results.append(rec)
    time.sleep(1.5)

json.dump(results, open("/tmp/shadow_2a_r2_results.json", "w"), indent=2)

# --- gate computation ---
gen = [r for r in results if r.get("source") == "generated"]
fb = [r for r in results if r.get("source") == "deterministic"]
gate_pass = len(gen) / len(results)
mb = [
    r
    for r in gen
    if len([b for b in _extract_branches(r["task"]) if _is_real_branch(b)]) >= 2
]
cov_pass = sum(1 for r in mb if r["coverage"])
recovered = [r for r in gen if (r.get("attempts") or 1) > 1]
shadow_ok = sum(1 for r in results if r.get("consumed") is False)

print("=" * 60)
print(f"spans published        : {sum(1 for r in results if r['span'])}/{len(results)}")
print(f"GATE-PASS (generated)  : {len(gen)}/{len(results)} = {gate_pass:.1%}  (>=95%)")
print(f"  recovered via retry  : {len(recovered)}  (attempts>1)")
print(f"  fallbacks            : {len(fb)}")
print(
    f"COVERAGE (multi-branch): {cov_pass}/{len(mb)} = {cov_pass / len(mb) if mb else 0:.1%}  (>=80%)"
)
print(f"shadow invariant       : {shadow_ok}/{len(results)} consumed=false")
print("=" * 60)
if fb:
    print("\nFALLBACKS:")
    for r in fb:
        print(
            f"  [{r['i']:02d}] attempts={r.get('attempts')} {r.get('fallback_reason', '')[:120]}"
        )
        print(f"       task: {r['task'][:90]}")
if recovered:
    print("\nRETRY RECOVERIES:")
    for r in recovered:
        print(
            f"  [{r['i']:02d}] attempts={r['attempts']} n_rejected={r['n_rejected']} task: {r['task'][:70]}"
        )
