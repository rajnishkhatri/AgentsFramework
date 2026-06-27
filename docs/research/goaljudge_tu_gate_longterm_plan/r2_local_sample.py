"""Locally regenerate TU conditions with the EXACT deployed prompt (local HEAD
== deployed commit e72920c) so candidate gates can be simulated offline.
Failed cases k=4, passing cases k=2. Saves raw conditions only."""

import asyncio
import json
import os
import sys

# load .env into the process env (keys never printed)
for line in open(".env"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v.strip().strip('"').strip("'"))
assert os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY missing from .env"

sys.path.insert(0, ".")
from components.task_understanding import _extract_json  # noqa: E402
from services.base_config import AgentConfig, default_fast_profile  # noqa: E402
from services.llm_config import LLMService  # noqa: E402
from services.prompt_service import PromptService  # noqa: E402

results = json.load(open("/tmp/shadow_2a_r2_results.json"))
tasks = json.load(open("/tmp/shadow_2a_r2_tasks.json"))
failed_idx = [
    r["i"] for r in results if r.get("span") and r.get("source") != "generated"
]
passing_idx = [r["i"] for r in results if r.get("source") == "generated"]
print(f"failed={failed_idx} passing_n={len(passing_idx)}")

config = AgentConfig(default_model="gpt-4o-mini", models=[default_fast_profile()])
llm = LLMService(config=config)
ps = PromptService()
profile = default_fast_profile()


async def sample_one(task: str):
    rendered = ps.render_prompt(
        "task_understanding_prompt", task_input=task, rejection_feedback=""
    )
    resp = await llm.invoke(profile, [{"role": "user", "content": rendered}])
    content = str(getattr(resp, "content", resp))
    try:
        data = json.loads(_extract_json(content))
        conds = [
            str(c).strip() for c in data.get("success_conditions", []) if str(c).strip()
        ]
        return conds
    except Exception as exc:
        return [f"<unparsed:{type(exc).__name__}>"]


async def main():
    out = {"failed": {}, "passing": {}}
    for i in failed_idx:
        sams = []
        for _ in range(4):
            sams.append(await sample_one(tasks[i]))
        out["failed"][str(i)] = {"task": tasks[i], "samples": sams}
        print(f"[F{i:02d}] {len(sams)} samples", flush=True)
    for i in passing_idx:
        sams = []
        for _ in range(2):
            sams.append(await sample_one(tasks[i]))
        out["passing"][str(i)] = {"task": tasks[i], "samples": sams}
        print(f"[P{i:02d}] ok", flush=True)
    json.dump(out, open("/tmp/r2_local_samples.json", "w"), indent=2)
    n = sum(len(v["samples"]) for d in out.values() for v in d.values())
    print(f"saved {n} samples -> /tmp/r2_local_samples.json")


asyncio.run(main())
