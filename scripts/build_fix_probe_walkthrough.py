#!/usr/bin/env python3
"""build_fix_probe_walkthrough.py — case-by-case walkthrough report for the F1–F7 fix probes.

Assembles, per probe, the four evidence sources into one markdown report:
  1. Task input        — the prompt(s) sent through the real composer (capture JSONL)
  2. Answer            — the settled DOM response text (capture JSONL)
  3. Trace reasoning   — the tool/error/decision trajectory (BlackBox recording) +
                          the carrier verdict from analyze_fix_probes.py, with a
                          clickable Langfuse trace link
  4. Screenshot        — the Playwright full-page capture (repo-relative link)

Read-only over existing artifacts; does not drive any run. Langfuse is hit only to
resolve each trace's project URL (clickable link) — skipped with --no-langfuse.

Usage:
  .venv/bin/python scripts/build_fix_probe_walkthrough.py \
      --jsonl cache/fix_probe_eval/ui_batch.jsonl \
      --recordings cache/black_box_recordings \
      --out docs/research/toolcalling/F1F7_live_walkthrough.md
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.request
import urllib.error
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
AGENT_ROOT = SCRIPTS_DIR.parent

# Reuse the exact carrier scorer so the walkthrough verdict == the scorecard verdict.
import sys

sys.path.insert(0, str(SCRIPTS_DIR))
from analyze_fix_probes import (  # noqa: E402
    _assert_probe,
    _resolve_blackbox_events,
)


def _load_rows(jsonl: Path) -> list[dict]:
    rows = [json.loads(l) for l in jsonl.read_text().strip().split("\n") if l]
    # last-write-wins per probe (append-only artifact)
    latest: dict[str, dict] = {}
    for r in rows:
        latest[r.get("probe_id", "")] = r
    return list(latest.values())


def _langfuse_url(trace_id: str, cache: dict[str, str | None]) -> str | None:
    """Resolve the clickable Langfuse trace URL (htmlPath). Cached project path."""
    host = (
        os.environ.get("LANGFUSE_HOST") or os.environ.get("LANGFUSE_BASE_URL") or ""
    ).rstrip("/")
    pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    sk = os.environ.get("LANGFUSE_SECRET_KEY", "")
    if not (host and pk and sk):
        return None
    tok = base64.b64encode(f"{pk}:{sk}".encode()).decode()
    url = f"{host}/api/public/traces/{trace_id}"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {tok}"})
    # The read API rate-limits a tight sequential loop (8 traces back-to-back trips
    # 429); retry with backoff so every case gets its clickable link.
    import time

    t = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
                t = json.loads(r.read().decode())
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 4:
                retry_after = exc.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after else 2.0**attempt)
                continue
            return None
        except (urllib.error.URLError, TimeoutError):
            return None
    if t is None:
        return None
    html_path = t.get("htmlPath")
    cache["_cost"] = t.get("totalCost")
    cache["_latency"] = t.get("latency")
    return f"{host}{html_path}" if html_path else None


def _trajectory(events: list[dict]) -> list[str]:
    """Human-readable reasoning trajectory from the BlackBox carriers: the model's
    decisions (model.selected rationale), each tool call, each error_class, and the
    terminal verdict. This is the 'trace reasoning' column."""
    lines: list[str] = []
    step = 0
    turn = 0
    for e in events:
        et = e.get("event_type", "")
        d = e.get("details", {}) or {}
        if et.endswith("task_started"):
            turn += 1
            lines.append(f"- **▼ turn {turn} begins** (`task_started`)")
        elif et.endswith("model_selected"):
            reason = d.get("reason") or d.get("rationale") or ""
            if reason:
                lines.append(f"- **model** → `{d.get('model', '?')}` ({reason})")
        elif et.endswith("tool_called"):
            step += 1
            args = d.get("args")
            arg_s = json.dumps(args) if isinstance(args, (dict, list)) else str(args)
            lines.append(f"- **tool[{step}]** `{d.get('tool', '?')}` ← `{arg_s[:120]}`")
        elif et.endswith("error_occurred"):
            ec = d.get("error_class")
            src = d.get("source", "?")
            err = (d.get("error") or "").split("\n")[0][:110]
            tag = f"`error_class={ec}`" if ec else "*(no error_class)*"
            lines.append(f"  - ↳ **error** [{src}] {tag} — {err}")
        elif et.endswith("task_completed"):
            lines.append(
                f"- **completed** → outcome=`{d.get('outcome')}` "
                f"goal_met=`{d.get('goal_met')}` criteria_met=`{d.get('criteria_met')}`"
            )
    return lines


FIX_TITLES = {
    "F1": "Masked-validation un-mask (path boundary)",
    "F1b": "Shell error taxonomy (validation vs timeout)",
    "F2": "Validation repair-hint seam",
    "F3": "Hallucinated-tool nudge (unknown_tool)",
    "F6": "Corrupt-success floor (empty answer)",
    "F7a": "Multi-turn dropped-user-message (GLM)",
    "F7b": "Multi-turn mid-convo error cascade (GLM)",
}

VERDICT_GLYPH = {"PASS": "✅ PASS", "FAIL": "❌ FAIL", "SKIP": "⏭️ SKIP"}


def _rel(p: str | None, out_dir: Path) -> str | None:
    """The capture stores screenshot_path repo-root-relative, but a markdown image
    link resolves relative to the REPORT file. Re-base it to out_dir so the link
    works wherever the report is written."""
    if not p:
        return None
    abs_p = (AGENT_ROOT / p).resolve()
    try:
        return os.path.relpath(abs_p, out_dir.resolve())
    except ValueError:
        return p


def build(args: argparse.Namespace) -> str:
    rows = _load_rows(args.jsonl)
    rows.sort(key=lambda r: r.get("case_id", r.get("probe_id", "")))

    out: list[str] = []
    out.append("# F1–F7 Tool-Calling Fixes — Live-LLM Case-by-Case Walkthrough\n")
    out.append(
        "> Each case drove a real prompt through the chat UI against a **live model** "
        "on localhost (current `HEAD`), then reconciled the DOM answer against the "
        "**BlackBox trace carriers** + **Langfuse spans**. Verdict column is the exact "
        "output of `scripts/analyze_fix_probes.py` (carriers, not prose).\n"
    )
    out.append(
        "_Generated by `scripts/build_fix_probe_walkthrough.py` from "
        "`cache/fix_probe_eval/ui_batch.jsonl` + `cache/black_box_recordings/`. "
        "Re-run the probe batch + this script to refresh._\n"
    )
    out.append("### How to read each case")
    out.append(
        "- **Task input** — the exact prompt(s) sent through the real composer "
        "(multi-turn cases show each turn).\n"
        "- **Answer** — the settled response text captured from the live DOM region.\n"
        "- **Trace reasoning** — the model→tool→error→completion trajectory rebuilt "
        "from BlackBox carriers; `error_class=…` is the taxonomy field the fixes "
        "added. `▼ turn N begins` marks a new `task_started` (multi-turn).\n"
        "- **Carrier verdict** — the positive carrier(s) asserted + negative controls.\n"
        "- **Langfuse trace** — clickable span view (cost/latency).  **Screenshot** — "
        "the Playwright full-page capture.\n"
    )
    out.append("### Interpreting PASS / SKIP")
    out.append(
        "- **PASS** — the fix's carrier fired on the live trace and the pre-fix "
        "failure was absent. The headline is **F1**: the boundary-violating path "
        "now stamps `error_class=validation` (pre-fix it was masked as a plain "
        "`Error:` string with no class).\n"
        "- **SKIP (live-unforcible)** — F3 (hallucinated tool) and F6 (empty answer) "
        "depend on a model *misbehaving*; the capable pinned models refused to "
        "(e.g. DeepSeek reasoned a fake `read` tool away and used `file_io`), so the "
        "seam never fired. These fixes are covered by the unit suite — a SKIP here "
        "is **not** a regression.\n"
        "- **F7 nuance** — the fix is that **turn 2 reaches the model with no GLM "
        "provider rejection**; the trajectory shows `▼ turn 2 begins` + a model "
        "selection with zero `llm_call` errors, which is the proof. (The captured "
        "answer is turn 1's; GLM's empty-output on turn 2 yields no further tools.)\n"
    )

    # Summary table.
    verdicts: dict[str, tuple[str, list[dict]]] = {}
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}
    for r in rows:
        events = _resolve_blackbox_events(args.recordings, r)
        v, _ = _assert_probe(r, events)
        verdicts[r["probe_id"]] = (v, events)
        counts[v] += 1

    out.append("## Summary\n")
    out.append(
        f"**{counts['PASS']} PASS · {counts['FAIL']} FAIL · {counts['SKIP']} SKIP**\n"
    )
    out.append("| Case | Fix | Seam | Pin | Verdict |")
    out.append("|---|---|---|---|---|")
    for r in rows:
        v = verdicts[r["probe_id"]][0]
        out.append(
            f"| `{r['probe_id']}` | {r['fix']} | {FIX_TITLES.get(r['fix'], '')} "
            f"| `{r.get('pinned_model') or 'default'}` | {VERDICT_GLYPH[v]} |"
        )
    out.append("")

    lf_meta: dict[str, str | None] = {}
    # Per-case detail.
    for i, r in enumerate(rows, 1):
        pid = r["probe_id"]
        v, events = verdicts[pid]
        _, reasons = _assert_probe(r, events)
        if not args.no_langfuse and i > 1:
            import time

            time.sleep(0.4)  # space reads so the batch doesn't trip the 429 limit
        lf_url = None if args.no_langfuse else _langfuse_url(r["trace_id"], lf_meta)

        out.append(
            f"\n---\n\n## {i}. `{pid}` — {FIX_TITLES.get(r['fix'], '')}  {VERDICT_GLYPH[v]}\n"
        )
        out.append(
            f"**Fix:** {r['fix']}  ·  **Pinned model:** `{r.get('pinned_model') or 'default'}`  "
            f"·  **Join id:** `{r.get('case_id')}`  ·  **trace_id:** `{r['trace_id']}`\n"
        )

        # 1. Task input
        out.append("### Task input")
        prompts = r.get("prompts") or []
        if len(prompts) == 1:
            out.append(f"> {prompts[0]}\n")
        else:
            for ti, p in enumerate(prompts, 1):
                out.append(f"> **Turn {ti}.** {p}\n")

        # 2. Answer
        out.append("### Answer (settled DOM response)")
        ans = (r.get("response_text") or "").strip()
        out.append(f"> {ans if ans else '*(empty)*'}\n")

        # 3. Trace reasoning
        out.append("### Trace reasoning (BlackBox carriers)")
        traj = _trajectory(events)
        if traj:
            out.extend(traj)
        else:
            out.append("- *(no trace recorded for this trace_id)*")
        out.append("")
        out.append("**Carrier verdict:**")
        for reason in reasons:
            out.append(f"- {reason}")
        out.append("")

        # Langfuse link + cost/latency
        if lf_url:
            cost = lf_meta.get("_cost")
            lat = lf_meta.get("_latency")
            extra = []
            if cost is not None:
                extra.append(f"cost ${cost}")
            if lat is not None:
                extra.append(f"latency {lat}ms")
            suffix = f" ({', '.join(extra)})" if extra else ""
            out.append(
                f"🔗 **Langfuse trace:** [{r['trace_id'][:16]}…]({lf_url}){suffix}\n"
            )
        else:
            out.append(
                f"🔗 **Langfuse trace:** `{r['trace_id']}` "
                "(set LANGFUSE_* env for the clickable link)\n"
            )

        # 4. Screenshot
        shot = _rel(r.get("screenshot_path"), args.out.parent)
        if shot:
            out.append("### Playwright screenshot")
            out.append(f"![{pid}]({shot})\n")
            out.append(f"`{shot}`\n")

    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--jsonl",
        type=Path,
        default=AGENT_ROOT / "cache" / "fix_probe_eval" / "ui_batch.jsonl",
    )
    ap.add_argument(
        "--recordings", type=Path, default=AGENT_ROOT / "cache" / "black_box_recordings"
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=AGENT_ROOT
        / "docs"
        / "research"
        / "toolcalling"
        / "F1F7_live_walkthrough.md",
    )
    ap.add_argument(
        "--no-langfuse", action="store_true", help="skip the Langfuse URL fetch"
    )
    args = ap.parse_args()

    if not args.jsonl.exists():
        print(f"no capture at {args.jsonl}")
        return 2

    report = build(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report)
    print(f"wrote {args.out} ({len(report)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
