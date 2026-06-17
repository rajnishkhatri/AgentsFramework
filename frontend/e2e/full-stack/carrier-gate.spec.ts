/**
 * Tier 3 — governance carrier-gate shadow validation against the deployed stack.
 *
 * The carrier gate (services/governance/carrier_gate.py, wired in
 * orchestration/react_loop.py) runs an inline, deterministic check at each phase
 * boundary and records a `guardrail_checked` carrier with
 * `details.source == "carrier_gate"`. It is SHADOW/WARN — it never blocks — so it
 * is invisible in the UI. This spec is therefore a pure DRIVER + CAPTURE: it
 * sends a handful of generic prompts through the real composer and asserts only
 * that a non-empty answer rendered (the DOM "outcome"). ALL governance scoring is
 * the trace-analysis half (scripts/analyze_planning_traces.py --phase carrier),
 * which pulls each captured trace_id from Langfuse and scores per-phase carrier
 * coverage + the batch gap-rate (the §5 calibration verdict).
 *
 * Unlike the planning-stress spec, the carrier gate is UNCONDITIONAL (no loops-on
 * flag) — it fires on every run — so this validates against the PROD frontend; no
 * tagged stress revision is required.
 *
 * Plan: docs/plans/governance_carrier_gate_e2e_validation.plan.md.
 * Methodology: docs/skills/playwright-agentic-e2e §5 (verify the run server-side).
 *
 * On-demand only; never per-commit CI (real model, non-deterministic).
 *   BASE_URL=<deployed frontend URL>   (or TEST_PROFILE=prod)
 *   E2E_AUTHENTICATED=1                (+ WorkOS creds in repo-root .env)
 *
 * Optional:
 *   CARRIER_CASE_FILTER=GJ-STRESS-901  — single case
 *   CARRIER_LIMIT=2                     — cap batch size
 *   CARRIER_JSONL / CARRIER_SCREENSHOT_DIR — override output paths
 *
 * JSONL schema (one row per case): case, gj_id, trace_id, prompt, used_tool,
 *   response_text, response_chars, tool_card_count, latency_ms, screenshot_path,
 *   outcome ("pass"|"fail"), error (fail only), finished_at, base_url.
 */

import fs from "node:fs";
import path from "node:path";
import { test, expect } from "../fixtures/auth.fixture";
import {
  sendMessage,
  waitForResponse,
  waitForComposerReady,
} from "../fixtures/helpers";

/**
 * Generic prompts that exercise the wired phase boundaries. The gate fires on
 * every run regardless of content, so no oracle / want_* is needed — on healthy
 * traffic the expectation is "every wired phase records a `pass` carrier". The
 * mix is chosen for COVERAGE: plain-answer prompts exercise INITIALIZATION /
 * ROUTING / MODEL_INVOCATION / OUTPUT_VALIDATION; tool-using prompts add
 * TOOL_EXECUTION (the conditional Validation pillar).
 *
 * gj_id uses the GJ-STRESS-NN shape the middleware thread-bridge regex
 * (^GJ-STRESS-\d+$) requires; the 9xx range keeps these distinct from the
 * planning-stress corpus ids.
 */
interface CarrierCase {
  case: string;
  gj_id: string;
  prompt: string;
  used_tool: boolean; // expected to drive a tool (TOOL_EXECUTION coverage)
}

const ALL_CASES: CarrierCase[] = [
  {
    case: "carrier-plain-capital",
    gj_id: "GJ-STRESS-901",
    prompt: "What is the capital of France? Answer in one sentence.",
    used_tool: false,
  },
  {
    case: "carrier-plain-explain",
    gj_id: "GJ-STRESS-902",
    prompt: "Briefly explain what a hash chain is, in two sentences.",
    used_tool: false,
  },
  {
    case: "carrier-tool-write",
    gj_id: "GJ-STRESS-903",
    prompt:
      "Create a file named notes.txt containing the text 'hello carrier gate', " +
      "then tell me you have created it.",
    used_tool: true,
  },
  {
    case: "carrier-tool-multi",
    gj_id: "GJ-STRESS-904",
    prompt:
      "Write a file plan.txt with three short lines, then read it back and " +
      "summarize what it contains.",
    used_tool: true,
  },
  {
    case: "carrier-multistep",
    gj_id: "GJ-STRESS-905",
    prompt:
      "List three benefits of deterministic governance checks, then pick the " +
      "single most important one and explain why in one sentence.",
    used_tool: false,
  },
];

function selectCases(): CarrierCase[] {
  let cases = ALL_CASES;
  const filter = process.env.CARRIER_CASE_FILTER;
  if (filter) cases = cases.filter((c) => c.gj_id === filter || c.case === filter);
  const limit = process.env.CARRIER_LIMIT ? Number(process.env.CARRIER_LIMIT) : undefined;
  if (limit !== undefined) cases = cases.slice(0, limit);
  return cases;
}

const CASES = selectCases();

const OUTPUT_JSONL =
  process.env.CARRIER_JSONL ??
  path.join(process.cwd(), "..", "cache", "carrier_gate", "ui_batch.jsonl");

const OUTPUT_SCREENSHOT_DIR =
  process.env.CARRIER_SCREENSHOT_DIR ??
  path.join(path.dirname(OUTPUT_JSONL), "screenshots");

const REPO_ROOT = path.resolve(process.cwd(), "..");

// Rotate the artifact ONCE per batch (one file == one batch); back up the prior
// file timestamped. Mirrors the planning-stress superposition-guard rationale.
function rotateArtifactOnce(): void {
  if (process.env.CARRIER_JSONL_APPEND === "1") return;
  try {
    if (fs.existsSync(OUTPUT_JSONL) && fs.statSync(OUTPUT_JSONL).size > 0) {
      const stamp = new Date().toISOString().replace(/[:.]/g, "-");
      fs.renameSync(OUTPUT_JSONL, `${OUTPUT_JSONL}.${stamp}.bak`);
    }
  } catch {
    // best-effort; never block the batch.
  }
}
rotateArtifactOnce();

function appendCapture(row: Record<string, unknown>): void {
  fs.mkdirSync(path.dirname(OUTPUT_JSONL), { recursive: true });
  fs.appendFileSync(OUTPUT_JSONL, `${JSON.stringify(row)}\n`, "utf8");
}

function screenshotRelPath(absPath: string): string {
  const resolved = path.resolve(absPath);
  if (resolved.startsWith(`${REPO_ROOT}${path.sep}`)) {
    return path.relative(REPO_ROOT, resolved);
  }
  return resolved;
}

/**
 * Fresh 32-hex trace_id per run → one Langfuse trace per run (no superposition).
 * The static-trace_id reuse defect blended every run's carriers under one trace
 * (Stage-B report-integrity defect); a unique id keeps one trace == one run.
 */
function freshTraceId(): string {
  const g = (globalThis as { crypto?: Crypto }).crypto;
  if (g?.getRandomValues) {
    const buf = new Uint8Array(16);
    g.getRandomValues(buf);
    return Array.from(buf, (b) => b.toString(16).padStart(2, "0")).join("");
  }
  let s = "";
  while (s.length < 32) s += Math.floor(Math.random() * 16).toString(16);
  return s.slice(0, 32);
}

/**
 * Encode the join key into thread_id as `gj:{gj_id}:{trace_id}` so the middleware
 * derives a deterministic server-side trace_id (the GoalJudge-batch bridge). This
 * is what lets the analyzer pull each case's trace from Langfuse. FE-AP-7: never
 * send a client-generated trace_id field.
 */
function installThreadBridge(
  page: import("@playwright/test").Page,
  gjId: string,
  runTraceId: string,
): void {
  const threadId = `gj:${gjId}:${runTraceId}`;
  page.route("**/api/run/stream", async (route) => {
    const request = route.request();
    const raw = request.postData() ?? "{}";
    let body: Record<string, unknown>;
    try {
      body = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      await route.continue();
      return;
    }
    if ("trace_id" in body) {
      throw new Error("carrier-gate batch must not send client-generated trace_id");
    }
    body.thread_id = threadId;
    await route.continue({
      postData: JSON.stringify(body),
      headers: { ...request.headers(), "content-type": "application/json" },
    });
  });
}

async function captureEvidence(
  page: import("@playwright/test").Page,
  caseId: string,
  outcome: "pass" | "fail",
): Promise<string> {
  await page
    .$$eval(
      "details[data-testid='tool-card'], details[data-testid='reasoning-summary']",
      (els) => els.forEach((el) => ((el as HTMLDetailsElement).open = true)),
    )
    .catch(() => {});
  fs.mkdirSync(OUTPUT_SCREENSHOT_DIR, { recursive: true });
  const name = outcome === "fail" ? `${caseId}_FAILED.png` : `${caseId}.png`;
  const absPath = path.join(OUTPUT_SCREENSHOT_DIR, name);
  const buffer = await page.screenshot({ fullPage: true });
  fs.writeFileSync(absPath, buffer);
  await test.info().attach(name, { body: buffer, contentType: "image/png" });
  return screenshotRelPath(absPath);
}

async function newThreadIfAvailable(
  page: import("@playwright/test").Page,
): Promise<void> {
  const btn = page.locator(
    "[data-testid='new-thread'], button:has-text('New chat'), button:has-text('New')",
  );
  if ((await btn.count()) > 0) {
    await btn.first().click();
  }
}

test.describe("Governance carrier-gate shadow validation (L4: real stack)", () => {
  test.skip(
    process.env.MOCK_MIDDLEWARE === "1",
    "Requires real backend — unset MOCK_MIDDLEWARE.",
  );
  test.skip(CASES.length === 0, "No cases — check CARRIER_CASE_FILTER / CARRIER_LIMIT.");

  for (const caseRow of CASES) {
    test(`carrier ${caseRow.case}`, async ({ authenticatedPage: page }) => {
      test.setTimeout(180_000);

      const runTraceId = freshTraceId();
      installThreadBridge(page, caseRow.gj_id, runTraceId);

      const title = `gj:${caseRow.gj_id}:${runTraceId}`;
      let responseText = "";
      let toolCardCount = 0;
      const startedAt = Date.now();

      try {
        await page.goto("/");
        await newThreadIfAvailable(page);

        await sendMessage(page, caseRow.prompt);
        const response = await waitForResponse(page, { timeoutMs: 150_000 });
        await waitForComposerReady(page, { timeoutMs: 5_000 }).catch(() => {});

        responseText = (await response.textContent()) ?? "";
        const latencyMs = Date.now() - startedAt;

        // The ONLY DOM assertion: a non-empty answer rendered. The shadow gate is
        // invisible in the UI; whether its carriers landed is the analyzer's job.
        // This also proves the no-block invariant: even a run with a gap completes.
        expect(responseText.length).toBeGreaterThan(0);

        const toolCards = page.locator("[data-testid='tool-card'], .tool-card");
        toolCardCount = await toolCards.count();

        const screenshotPath = await captureEvidence(page, caseRow.case, "pass");

        appendCapture({
          case: caseRow.case,
          gj_id: caseRow.gj_id,
          trace_id: runTraceId,
          prompt: caseRow.prompt,
          used_tool: caseRow.used_tool,
          thread_title: title,
          response_text: responseText.slice(0, 4000),
          response_chars: responseText.length,
          tool_card_count: toolCardCount,
          latency_ms: latencyMs,
          screenshot_path: screenshotPath,
          outcome: "pass",
          finished_at: new Date().toISOString(),
          base_url: process.env.BASE_URL ?? "http://localhost:3000",
        });
      } catch (err) {
        let screenshotPath: string | undefined;
        try {
          screenshotPath = await captureEvidence(page, caseRow.case, "fail");
        } catch {
          // Page may be closed; still record the failure row.
        }
        appendCapture({
          case: caseRow.case,
          gj_id: caseRow.gj_id,
          trace_id: runTraceId,
          prompt: caseRow.prompt,
          used_tool: caseRow.used_tool,
          thread_title: title,
          response_text: responseText.slice(0, 4000),
          response_chars: responseText.length,
          tool_card_count: toolCardCount,
          latency_ms: Date.now() - startedAt,
          screenshot_path: screenshotPath,
          outcome: "fail",
          error: err instanceof Error ? err.message : String(err),
          finished_at: new Date().toISOString(),
          base_url: process.env.BASE_URL ?? "http://localhost:3000",
        });
        throw err;
      }
    });
  }
});
