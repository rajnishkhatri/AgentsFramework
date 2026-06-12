"""Prototype the evidence-quote mechanism: model must cite a verbatim task
span per condition (one declared-generic allowed). Deterministic substring
check. 5 failed + 3 passing tasks, k=2."""
import asyncio, json, os, sys
for line in open(".env"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v.strip().strip('"').strip("'"))
sys.path.insert(0, ".")
from components.task_understanding import _extract_json  # noqa: E402
from services.base_config import AgentConfig, default_fast_profile  # noqa: E402
from services.llm_config import LLMService  # noqa: E402

PROMPT = """You are a precise task analyst. Before an AI agent begins work, define the
success checklist a judge will later score the final answer against. You see
ONLY the task - no answer exists yet.

# Task
{task}

# Instructions
Produce 2 to 6 checklist conditions. For EACH condition also provide
"evidence": a short span copied VERBATIM (character-for-character) from the
Task text above that the condition is grounded in. At most ONE condition may
instead set "evidence": null - use that only for a generic completion check.
Each condition is one sentence, max 200 chars, observable and YES/NO-checkable.

# Output format
Output ONLY a JSON object:
{{"success_conditions": [{{"text": "<condition>", "evidence": "<verbatim span or null>"}}, ...]}}"""

results = json.load(open("/tmp/shadow_2a_r2_results.json"))
tasks = json.load(open("/tmp/shadow_2a_r2_tasks.json"))
failed_idx = [r["i"] for r in results if r.get("span") and r.get("source") != "generated"]
sample_idx = failed_idx + [0, 11, 26]

config = AgentConfig(default_model="gpt-4o-mini", models=[default_fast_profile()])
llm = LLMService(config=config)
profile = default_fast_profile()

async def main():
    out = []
    for i in sample_idx:
        task = tasks[i]
        for s in range(2):
            resp = await llm.invoke(profile, [{"role": "user", "content": PROMPT.format(task=task)}])
            content = str(getattr(resp, "content", resp))
            try:
                data = json.loads(_extract_json(content))
                conds = data.get("success_conditions", [])
            except Exception:
                print(f"[{i:02d}] s{s} UNPARSED"); continue
            n_null = sum(1 for c in conds if c.get("evidence") is None)
            bad = [c for c in conds
                   if c.get("evidence") is not None
                   and str(c.get("evidence", "")).lower() not in task.lower()]
            verdict = "PASS" if (n_null <= 1 and not bad and 2 <= len(conds) <= 7) else "FAIL"
            print(f"[{i:02d}] s{s} {verdict}  n={len(conds)} null={n_null} nonverbatim={len(bad)}")
            for c in bad:
                print(f"      BAD-QUOTE: '{str(c.get('evidence'))[:60]}' for: {str(c.get('text'))[:60]}")
            out.append({"case": i, "sample": s, "verdict": verdict, "conds": conds})
    json.dump(out, open("/tmp/r2_evidence_proto.json", "w"), indent=2)
    n_pass = sum(1 for r in out if r["verdict"] == "PASS")
    print(f"\nartifact pass: {n_pass}/{len(out)}")

asyncio.run(main())
