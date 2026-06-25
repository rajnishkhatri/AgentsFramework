#!/usr/bin/env python
"""Pre-deploy provider-key smoke (deploy plan Part 0).

Makes ONE real, cheap completion call per provider through the runtime's own
``services.llm_config.LLMService.get_llm`` path — the same ``ChatLiteLLM`` factory
the agent uses. LiteLLM reads provider keys from the PROCESS ENV (no api_key arg),
so this exercises the exact key + dispatch path the deployed Cloud Run container
will use. A revoked / wrong key 401s here in one call, before a full GCP cycle.

Validates the keys currently in ``.env`` — the same values that get pushed to
Secret Manager during the ``secrets`` deploy phase. Run BEFORE deploying.

SECURITY: never prints a key value — only provider / model / latency / token
usage / a short response snippet. Cheapest model per provider (fast tier) so the
whole smoke costs fractions of a cent.

Usage:
    .venv/bin/python scripts/smoke_provider_keys.py
    .venv/bin/python scripts/smoke_provider_keys.py --providers anthropic
Exit code 0 = every requested provider returned a non-empty completion; 1 = at
least one failed (bad key, network, etc.).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
AGENT_ROOT = SCRIPTS_DIR.parent
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(AGENT_ROOT / ".env")

from services.base_config import AgentConfig, ModelProfile  # noqa: E402
from services.llm_config import LLMService  # noqa: E402

# One cheap fast-tier model per provider + the env var LiteLLM reads for it.
# Keep these in sync with services/llm_config.py's registry litellm_ids.
_PROVIDERS: dict[str, dict[str, str]] = {
    "anthropic": {
        "name": "claude-haiku-4-5",
        "litellm_id": "anthropic/claude-haiku-4-5",
        "env": "ANTHROPIC_API_KEY",
    },
    "deepseek": {
        "name": "deepseek-v4-flash",
        "litellm_id": "deepseek/deepseek-v4-flash",
        "env": "DEEPSEEK_API_KEY",
    },
    "openai": {
        "name": "gpt-4o-mini",
        "litellm_id": "openai/gpt-4o-mini",
        "env": "OPENAI_API_KEY",
    },
}

_PROMPT = [{"role": "user", "content": "Reply with the single word: ok"}]


def _key_fingerprint(env_var: str) -> str:
    """Safe, value-free fingerprint of a key for the report (len + 6-char prefix)."""
    v = os.environ.get(env_var, "")
    if not v:
        return "ABSENT"
    return f"present len={len(v)} prefix={v[:6]}…"


async def _smoke_one(provider: str) -> tuple[bool, str]:
    spec = _PROVIDERS[provider]
    fp = _key_fingerprint(spec["env"])
    if fp == "ABSENT":
        return False, (
            f"  [{provider:9s}] {spec['env']} ABSENT in env — cannot call {spec['name']}"
        )

    profile = ModelProfile(
        name=spec["name"],
        litellm_id=spec["litellm_id"],
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
    )
    cfg = AgentConfig(default_model=spec["name"], models=[profile])
    svc = LLMService(config=cfg)

    started = time.monotonic()
    try:
        resp = await svc.invoke(profile, _PROMPT)
    except Exception as exc:  # noqa: BLE001 — surface ANY failure verbatim
        elapsed = (time.monotonic() - started) * 1000.0
        # The exception text may echo a 401 / auth error; it never contains the key.
        return False, (
            f"  [{provider:9s}] FAIL  {spec['name']}  ({elapsed:.0f}ms)  "
            f"key={fp}\n             {type(exc).__name__}: {str(exc)[:300]}"
        )
    elapsed = (time.monotonic() - started) * 1000.0

    content = getattr(resp, "content", "") or ""
    usage = getattr(resp, "usage_metadata", {}) or {}
    tin = usage.get("input_tokens", "?")
    tout = usage.get("output_tokens", "?")
    snippet = str(content).strip().replace("\n", " ")[:40]
    if not snippet:
        return False, (
            f"  [{provider:9s}] EMPTY {spec['name']}  ({elapsed:.0f}ms) — no content "
            f"(call succeeded but returned nothing)"
        )
    return True, (
        f"  [{provider:9s}] OK    {spec['name']}  ({elapsed:.0f}ms)  "
        f"tokens in/out={tin}/{tout}  key={fp}\n             reply: {snippet!r}"
    )


async def _main(providers: list[str]) -> int:
    print("Pre-deploy provider-key smoke (deploy plan Part 0)")
    print("=" * 64)
    results: list[bool] = []
    for provider in providers:
        ok, line = await _smoke_one(provider)
        print(line)
        results.append(ok)
    print("=" * 64)
    passed = sum(results)
    total = len(results)
    if all(results):
        print(f"PASS — {passed}/{total} providers returned a completion. Safe to deploy.")
        return 0
    print(
        f"FAIL — {passed}/{total} providers OK. Fix the failing key(s) in .env "
        f"BEFORE deploying (a revoked key would 401 on Cloud Run too)."
    )
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--providers",
        default="anthropic,deepseek",
        help="comma-separated subset of: anthropic,deepseek,openai "
        "(default: anthropic,deepseek — the rotated/new keys)",
    )
    args = parser.parse_args()
    requested = [p.strip() for p in args.providers.split(",") if p.strip()]
    unknown = [p for p in requested if p not in _PROVIDERS]
    if unknown:
        print(f"unknown provider(s): {unknown}; valid: {list(_PROVIDERS)}")
        sys.exit(2)
    sys.exit(asyncio.run(_main(requested)))
