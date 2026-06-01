#!/usr/bin/env python3
"""BlackBox → Langfuse end-to-end validation CLI.

Drives synthetic scenarios through the authenticated frontend BFF (Route A)
and asserts the resulting traces, observations, scores, and compliance
dataset items in Langfuse Cloud.

Usage:
    # Run all scenarios:
    python scripts/validate_blackbox_langfuse.py \
        --frontend-url https://your-app.vercel.app \
        --cookie-env WOS_SESSION_COOKIE

    # Run a specific scenario:
    python scripts/validate_blackbox_langfuse.py \
        --frontend-url https://your-app.vercel.app \
        --cookie-env WOS_SESSION_COOKIE \
        --scenario S1

    # Generate report without running (dry run):
    python scripts/validate_blackbox_langfuse.py --report --dry-run

Environment variables required:
    WOS_SESSION_COOKIE  — session cookie from browser (Route A auth)
    LANGFUSE_PUBLIC_KEY — Langfuse project public key
    LANGFUSE_SECRET_KEY — Langfuse project secret key
    LANGFUSE_HOST       — Langfuse base URL (default: https://cloud.langfuse.com)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_ROOT))

from tests.synthetic.blackbox.dataset import (
    ALL_SCENARIOS,
    SCENARIO_ORDER,
    Scenario,
    ScenarioID,
)
from tests.synthetic.blackbox.langfuse_assertions import (
    AUDIT_DATASET,
    ComplianceDatasetReport,
    INCIDENT_DATASET,
    LANGFUSE_POLL_INTERVAL_S,
    LANGFUSE_POLL_MAX_ATTEMPTS,
    ScenarioVerification,
    poll_for_observation,
    print_ui_checklist,
    verify_compliance_datasets,
    verify_scenario,
)


# ─────────────────────────────────────────────────────────────────────
# BFF Client (Route A)
# ─────────────────────────────────────────────────────────────────────


class BFFClient:
    """HTTP client for the frontend BFF's /api/run/stream endpoint."""

    def __init__(self, frontend_url: str, session_cookie: str) -> None:
        self._base_url = frontend_url.rstrip("/")
        self._session_cookie = session_cookie

    async def post_run_stream(self, payload: dict) -> tuple[str | None, str]:
        """POST to /api/run/stream and capture trace_id from SSE.

        Returns (trace_id, raw_response_text).
        The trace_id is extracted from:
          1. SSE event data containing trace/workflow identifiers
          2. Backend logs (stream_ended trace=<uuid>)
        """
        import httpx

        url = f"{self._base_url}/api/run/stream"
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Cookie": f"wos-session={self._session_cookie}",
        }

        trace_id: str | None = None
        response_lines: list[str] = []

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST", url, headers=headers, json=payload
            ) as response:
                if response.status_code == 401:
                    raise RuntimeError(
                        "401 Unauthorized — session cookie expired or invalid. "
                        "Re-copy the wos-session cookie from your browser."
                    )
                if response.status_code != 200:
                    body = await response.aread()
                    raise RuntimeError(
                        f"BFF returned {response.status_code}: {body.decode()[:500]}"
                    )

                async for line in response.aiter_lines():
                    response_lines.append(line)
                    if trace_id is None:
                        trace_id = _extract_trace_id(line)

        raw_text = "\n".join(response_lines)
        return trace_id, raw_text


def _extract_trace_id(line: str) -> str | None:
    """Extract trace_id from an SSE event line.

    The AG-UI protocol serializes events as:
      data: {"type":"RUN_STARTED","run_id":"...","raw_event":{"trace_id":"..."}}

    The BlackBox workflow_id (== Langfuse trace_id) is carried in
    raw_event.trace_id per plan §4.3 Option B. The top-level run_id
    is an AG-UI correlation ID and must NOT be used for Langfuse lookups.
    """
    if not line.startswith("data:"):
        return None

    data_str = line[5:].strip()
    if not data_str:
        return None

    try:
        event_data = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None

    raw_event = event_data.get("raw_event") or event_data.get("rawEvent")
    if isinstance(raw_event, dict):
        for field_name in ("trace_id", "traceId", "workflow_id"):
            val = raw_event.get(field_name)
            if val and isinstance(val, str) and len(val) >= 8:
                return val

    for field_name in ("trace_id", "traceId"):
        val = event_data.get(field_name)
        if val and isinstance(val, str) and len(val) >= 8:
            return val

    metadata = event_data.get("metadata", {})
    if isinstance(metadata, dict):
        for field_name in ("trace_id", "workflow_id"):
            val = metadata.get(field_name)
            if val and isinstance(val, str) and len(val) >= 8:
                return val

    return None


# ─────────────────────────────────────────────────────────────────────
# Scenario Runner
# ─────────────────────────────────────────────────────────────────────


async def run_scenario(
    client: BFFClient,
    scenario: Scenario,
    *,
    gate: bool = True,
) -> ScenarioVerification | None:
    """Run a single scenario: POST → capture trace → assert Langfuse.

    If gate=True, pauses for human confirmation after printing UI checklist.
    """
    print(f"\n{'='*70}")
    print(f"  SCENARIO {scenario.id.value}: {scenario.description[:60]}")
    print(f"{'='*70}\n")

    print("[1/4] Sending request to BFF...")
    try:
        trace_id, raw_response = await client.post_run_stream(scenario.bff_payload)
    except RuntimeError as e:
        print(f"  ERROR: {e}")
        return None

    if trace_id is None:
        print("  WARNING: Could not extract trace_id from SSE stream.")
        print("  Attempting to find trace_id from response...")
        uuid_pattern = re.compile(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        )
        matches = uuid_pattern.findall(raw_response)
        if matches:
            trace_id = matches[0]
            print(f"  Found candidate trace_id: {trace_id}")
        else:
            hex_pattern = re.compile(r"[0-9a-f]{32}")
            hex_matches = hex_pattern.findall(raw_response)
            if hex_matches:
                trace_id = hex_matches[0]
                print(f"  Found candidate trace_id (hex): {trace_id}")
            else:
                print("  FATAL: No trace_id found. Cannot verify.")
                return None

    print(f"  trace_id = {trace_id}")

    terminal_obs = "task.completed"
    print(
        f"\n[2/4] Polling for '{terminal_obs}' "
        f"(up to {LANGFUSE_POLL_MAX_ATTEMPTS} attempts, "
        f"{LANGFUSE_POLL_INTERVAL_S}s apart)..."
    )
    if not poll_for_observation(trace_id, terminal_obs):
        print(
            f"  WARNING: '{terminal_obs}' not seen after polling; "
            "assertions may fail if relay is still flushing."
        )

    print("[3/4] Running automated Langfuse assertions...")
    verification = verify_scenario(scenario, trace_id)

    for assertion in verification.assertions:
        status = "PASS" if assertion.passed else "FAIL"
        print(f"  [{status}] {assertion.description}")
        if assertion.details:
            print(f"         {assertion.details}")

    print(f"\n  {verification.summary}")

    print(f"\n[4/4] UI Checklist:")
    checklist = print_ui_checklist(scenario, trace_id)
    print(checklist)

    if gate:
        print("\n  --- GATE: Human confirmation required ---")
        response = input("  Verified in UI? [y/N/skip]: ").strip().lower()
        if response == "skip":
            print("  Skipped.")
        elif response != "y":
            print("  NOT confirmed. Continuing anyway (logged as unconfirmed).")

    return verification


async def run_scenario_s8_concurrent(
    client: BFFClient,
    scenario: Scenario,
    *,
    gate: bool = True,
) -> list[ScenarioVerification]:
    """Special handler for S8: run two workflows concurrently."""
    print(f"\n{'='*70}")
    print(f"  SCENARIO S8: Two concurrent workflows")
    print(f"{'='*70}\n")

    print("[1/5] Sending TWO concurrent requests to BFF...")

    async def _send(label: str) -> tuple[str | None, str]:
        trace_id, raw = await client.post_run_stream(scenario.bff_payload)
        return trace_id, raw

    results = await asyncio.gather(
        _send("S8-A"), _send("S8-B"), return_exceptions=True
    )

    verifications: list[ScenarioVerification] = []
    trace_ids: list[str] = []

    for i, result in enumerate(results):
        label = f"S8-{'AB'[i]}"
        if isinstance(result, Exception):
            print(f"  {label} ERROR: {result}")
            continue
        trace_id, raw = result
        if trace_id is None:
            print(f"  {label} WARNING: No trace_id extracted")
            continue
        print(f"  {label} trace_id = {trace_id}")
        trace_ids.append(trace_id)

    if len(trace_ids) < 2:
        print("  FATAL: Need 2 trace_ids for S8 isolation assertion.")
        return verifications

    print(f"\n[2/5] Asserting trace isolation: {trace_ids[0]} != {trace_ids[1]}")
    assert trace_ids[0] != trace_ids[1], "Two concurrent runs share the same trace_id!"
    print("  PASS: Distinct trace_ids confirmed.")

    relay_wait_s = 5
    print(f"\n[3/5] Waiting {relay_wait_s}s for relay to flush...")
    time.sleep(relay_wait_s)

    print("[4/5] Running assertions for each workflow...")
    for trace_id in trace_ids:
        v = verify_scenario(scenario, trace_id)
        verifications.append(v)
        print(f"\n  {v.summary}")

    if gate:
        print("\n[5/5] UI Checklist for S8:")
        for tid in trace_ids:
            checklist = print_ui_checklist(scenario, tid)
            print(checklist)
            print()

        print("  --- GATE: Human confirmation required ---")
        input("  Verified both traces in UI? [y/N]: ")

    return verifications


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BlackBox → Langfuse E2E validation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--frontend-url",
        required=True,
        help="Frontend BFF base URL (e.g., https://your-app.vercel.app)",
    )
    parser.add_argument(
        "--cookie-env",
        default="WOS_SESSION_COOKIE",
        help="Env var name holding the wos-session cookie value (default: WOS_SESSION_COOKIE)",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=[s.value for s in ScenarioID],
        help="Run a single scenario (default: all)",
    )
    parser.add_argument(
        "--gate",
        choices=["per-action", "none"],
        default="per-action",
        help="Approval granularity: per-action pauses for human, none runs unattended",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print final pass/fail summary report",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print scenario info without executing",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()

    if args.dry_run:
        print("DRY RUN — listing scenarios:\n")
        for sid in SCENARIO_ORDER:
            scenario = ALL_SCENARIOS[sid]
            print(f"  {sid.value}: {scenario.description}")
            print(f"         Observations: {len(scenario.expected_observations)}")
            print(f"         Compliance: {scenario.compliance.dataset_name}")
            print()
        return 0

    cookie_value = os.environ.get(args.cookie_env, "")
    if not cookie_value:
        print(
            f"ERROR: {args.cookie_env} environment variable not set.\n"
            "Sign in at the frontend URL, copy the wos-session cookie, and export it.",
            file=sys.stderr,
        )
        return 1

    for env_var in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        if not os.environ.get(env_var):
            print(f"ERROR: {env_var} not set.", file=sys.stderr)
            return 1

    client = BFFClient(args.frontend_url, cookie_value)
    gate = args.gate == "per-action"

    scenarios_to_run: list[ScenarioID]
    if args.scenario:
        scenarios_to_run = [ScenarioID(args.scenario)]
    else:
        scenarios_to_run = list(SCENARIO_ORDER)

    verifications: list[ScenarioVerification] = []
    trace_map: dict[str, str] = {}

    for sid in scenarios_to_run:
        scenario = ALL_SCENARIOS[sid]

        if sid == ScenarioID.S8:
            s8_results = await run_scenario_s8_concurrent(
                client, scenario, gate=gate
            )
            for i, v in enumerate(s8_results):
                verifications.append(v)
                trace_map[f"S8-{'AB'[i]}"] = v.trace_id
        else:
            result = await run_scenario(client, scenario, gate=gate)
            if result:
                verifications.append(result)
                trace_map[sid.value] = result.trace_id

    # ─────────────────────────────────────────────────────────────────
    # Phase 5 — Compliance datasets + scores
    # ─────────────────────────────────────────────────────────────────

    print(f"\n{'='*70}")
    print("  PHASE 5: Compliance Datasets + Scores")
    print(f"{'='*70}\n")

    print(f"  Trace map ({len(trace_map)} entries):")
    for k, v in sorted(trace_map.items()):
        print(f"    {k}: {v}")
    print()

    compliance_report = verify_compliance_datasets(trace_map)

    print("  agent-compliance-audit:")
    for r in compliance_report.audit_results:
        status = "PASS" if r.passed else "FAIL"
        print(f"    [{status}] {r.description}")
        if r.details:
            print(f"           {r.details}")

    print(f"\n  agent-incident-replay:")
    for r in compliance_report.incident_results:
        status = "PASS" if r.passed else "FAIL"
        print(f"    [{status}] {r.description}")
        if r.details:
            print(f"           {r.details}")

    print(f"\n  {compliance_report.summary}")

    if gate:
        print("\n  --- GATE: Phase 5 human confirmation ---")
        print("  Verify in Langfuse UI:")
        print(f"    1. Open Datasets → '{AUDIT_DATASET}' — items for S1–S4, S6, S8")
        print(f"    2. Open Datasets → '{INCIDENT_DATASET}' — item for S5")
        print("    3. Each audit item has hash_chain_valid=1.0 score")
        response = input("  Verified? [y/N]: ").strip().lower()
        if response != "y":
            print("  NOT confirmed (logged as unconfirmed).")

    # ─────────────────────────────────────────────────────────────────
    # Final Report
    # ─────────────────────────────────────────────────────────────────

    print(f"\n{'='*70}")
    print("  FINAL REPORT")
    print(f"{'='*70}\n")

    all_passed = True
    for v in verifications:
        print(f"  {v.summary}")
        if not v.all_passed:
            all_passed = False

    print(f"\n  {compliance_report.summary}")
    if not compliance_report.all_passed:
        all_passed = False

    total = len(verifications)
    passed = sum(1 for v in verifications if v.all_passed)
    print(f"\n  Scenarios: {passed}/{total} fully passed")
    print(f"  Phase 5 compliance: {'PASS' if compliance_report.all_passed else 'FAIL'}")

    if all_passed:
        print("\n  RESULT: ALL CHECKS PASSED")
        return 0
    else:
        print("\n  RESULT: SOME CHECKS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
