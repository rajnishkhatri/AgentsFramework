"""Round-3 gate analysis (n=101) with FALLBACK SEGMENTATION.

Same gate as rounds 1-2 (gate-pass = source==generated >= 96/101; coverage
>= 80% on multi-branch) PLUS: every fallback is classified by its
``fallback_reason`` so the known short-task grounding defect (governance
audit 4b8c3f68 — all-or-nothing grounding rejects a legitimate generic
"≤N words" condition on low-vocabulary tasks) is separated from genuine R3
failures (parse/transport/other). Reports BOTH the raw gate-pass and the
R3-attributable rate so the punctuation fix can be read through the
short-task noise (the "drive now, segment" decision, 2026-06-13).

Binomial power is quoted at the chosen n (process rule #3).
"""

import base64
import csv
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, "tests/components")
from components.plan_builder import _extract_branches  # noqa: E402
from components.task_understanding import _content_tokens  # noqa: E402


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


_GROUNDING = re.compile(r"grounding gate: condition \d+ shares no content token")


def _classify_fallback(reason: str, task: str) -> str:
    """Bucket a fallback by root cause. ``short_task_grounding`` is the known
    open defect; everything else is R3-attributable and must be inspected."""
    if not reason:
        return "no_reason_recorded"
    if "ValidationError" in reason and _GROUNDING.search(reason):
        # The known defect signature: grounding rejection on a low-vocabulary
        # task where the offender is the generic format condition. Flag by
        # task brevity so a genuine off-topic invention isn't excused.
        return (
            "short_task_grounding"
            if len(_content_tokens(task)) <= 6
            else "grounding_other"
        )
    if "ValidationError" in reason:
        return "validation_other"  # count/length/dupe — genuine R3 concern
    if "JSON" in reason or "Decode" in reason or "not a JSON" in reason:
        return "parse_error"
    return "transport_or_other"


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


with open(
    "docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_combined_sheet.csv",
    encoding="utf-8",
) as fh:
    GOLD = [r["task"].strip() for r in csv.DictReader(fh) if r.get("task", "").strip()]

runs = [json.loads(l) for l in open("/tmp/shadow_2a_r3_runs.jsonl")]
results = []
for r in runs:
    trace = r["trace_id"]
    task = GOLD[r["case_idx"]]
    rec = {
        "i": r["case_idx"],
        "trace": (trace or "")[:8],
        "task": task,
        "run_status": r["status"],
        "span": False,
    }
    if trace:
        url = f"{HOST}/api/public/observations?traceId={trace}&name=eval.task_understanding&limit=50"
        obs = get(url).get("data", [])
        rec["span"] = bool(obs)
        if obs:
            out = obs[0].get("output") or {}
            if isinstance(out, str):
                try:
                    out = json.loads(out)
                except Exception:
                    out = {}
            conds = out.get("success_conditions") or []
            source = out.get("source")
            rec.update(
                source=source,
                mode=out.get("mode"),
                consumed=out.get("consumed"),
                attempts=out.get("attempts"),
                n_rejected=len(out.get("rejected_conditions") or []),
                fallback_reason=(out.get("fallback_reason") or "")[:300],
                n_cond=len(conds),
                coverage=_covers(conds, task) if source == "generated" else None,
                fallback_bucket=(
                    _classify_fallback(out.get("fallback_reason") or "", task)
                    if source != "generated"
                    else None
                ),
            )
    results.append(rec)
    time.sleep(1.5)

json.dump(results, open("/tmp/shadow_2a_r3_results.json", "w"), indent=2)

# --- gate computation ---
n = len(results)
gen = [r for r in results if r.get("source") == "generated"]
fb = [r for r in results if r.get("source") == "deterministic"]
no_span = [r for r in results if not r["span"]]

# segment fallbacks
buckets = {}
for r in fb:
    buckets.setdefault(r.get("fallback_bucket", "unknown"), []).append(r)
known_defect = buckets.get("short_task_grounding", [])
# R3-attributable = everything that isn't the known short-task defect
r3_fail = [r for r in fb if r.get("fallback_bucket") != "short_task_grounding"]

raw_pass = len(gen)
# R3-attributable pass: credit the short-task-defect rows back (they fail for
# a known, separately-tracked reason, not an R3 regression)
adj_pass = len(gen) + len(known_defect)

mb = [
    r
    for r in gen
    if len([b for b in _extract_branches(r["task"]) if _is_real_branch(b)]) >= 2
]
cov_pass = sum(1 for r in mb if r["coverage"])
recovered = [r for r in gen if (r.get("attempts") or 1) > 1]
shadow_ok = sum(1 for r in results if r.get("consumed") is False)


def p_pass(N, p, need):
    return sum(math.comb(N, k) * p**k * (1 - p) ** (N - k) for k in range(need, N + 1))


print("=" * 66)
print(f"spans published         : {sum(1 for r in results if r['span'])}/{n}")
print(
    f"RAW GATE-PASS           : {raw_pass}/{n} = {raw_pass / n:.1%}   (gate >=96/101)"
)
print(
    f"R3-ATTRIBUTABLE PASS    : {adj_pass}/{n} = {adj_pass / n:.1%}   "
    f"(crediting {len(known_defect)} known short-task-grounding fallbacks)"
)
print(f"  recovered via retry   : {len(recovered)} (attempts>1)")
print(
    f"COVERAGE (multi-branch) : {cov_pass}/{len(mb)} = {cov_pass / len(mb) if mb else 0:.1%}  (>=80%)"
)
print(f"shadow invariant        : {shadow_ok}/{n} consumed=false")
print("-" * 66)
print("FALLBACK SEGMENTATION:")
for b, rs in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
    tag = (
        "  (KNOWN DEFECT — audit 4b8c3f68)"
        if b == "short_task_grounding"
        else (
            "  (R3 CONCERN — inspect)"
            if b in ("validation_other", "parse_error", "grounding_other")
            else ""
        )
    )
    print(f"  {b:24s}: {len(rs)}{tag}")
if no_span:
    print(
        f"  {'NO_SPAN (run failed)':24s}: {len(no_span)}  (drive transport/timeout — re-run these)"
    )
print("-" * 66)
print("BINOMIAL POWER at n=101, need>=96 (process rule #3):")
for p in (0.95, 0.96, 0.97, 0.98, 0.99):
    print(f"  true p={p:.2f}  ->  P(pass) = {p_pass(101, p, 96):.2f}")
print("=" * 66)

if r3_fail:
    print(
        "\nR3-ATTRIBUTABLE FALLBACKS (inspect each — NOT the known short-task defect):"
    )
    for r in r3_fail:
        print(
            f"  [{r['i']:03d}] bucket={r.get('fallback_bucket')} attempts={r.get('attempts')}"
        )
        print(f"        reason: {r.get('fallback_reason', '')[:140]}")
        print(f"        task:   {r['task'][:90]}")
if known_defect:
    print(
        f"\nKNOWN SHORT-TASK-GROUNDING FALLBACKS ({len(known_defect)} — fixed by the generic-condition exemption):"
    )
    for r in known_defect:
        print(f"  [{r['i']:03d}] task: {r['task'][:80]}")
if no_span:
    print(
        f"\nNO-SPAN RUNS ({len(no_span)} — drive-side failure, re-run before trusting the gate):"
    )
    for r in no_span:
        print(f"  [{r['i']:03d}] run_status={r['run_status']} task: {r['task'][:70]}")
