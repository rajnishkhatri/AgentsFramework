/**
 * Tier 3 — planning-pipeline stress run against the deployed Cloud Run stack.
 *
 * Drives the synthetic stress corpus (frontend/e2e/fixtures/planning_stress_corpus.json,
 * regen: `python scripts/build_planning_stress_corpus.py`) through the real chat
 * composer, one case per test, capturing one JSONL row + one evidence screenshot
 * per case. The spec is a DRIVER + CAPTURE; the real per-phase scoring is the
 * trace-analysis half (scripts/analyze_planning_traces.py), which pulls each
 * captured trace_id from Langfuse and scores entry-router accuracy and escalation
 * precision SEPARATELY (e2e-stress plan §5).
 *
 * Non-determinism is the point of T3: prompts make a CLASS of outcome likely,
 * not certain. The spec asserts only that a non-empty answer rendered (the DOM
 * "outcome"); it never asserts an exact depth/verdict per case.
 *
 * Plan: docs/plans/planning_pipeline_e2e_stress_and_trace_analysis.plan.md §4.
 * Methodology: docs/skills/playwright-agentic-e2e + docs/skills/gcp-live-smoke.
 *
 * On-demand only; never in per-commit CI (real model calls, non-deterministic —
 * skill golden rule). Requires a LOOPS-ON revision (Step 0 flags):
 *   BASE_URL=<--tag stress Cloud Run revision URL>
 *   E2E_AUTHENTICATED=1  (+ WorkOS creds in repo-root .env for global-setup)
 *
 * Optional:
 *   STRESS_CASE_FILTER=STRESS-DEPTH-010   — single case
 *   STRESS_PHASE=reflexion                — one phase (depth|replan|reflexion|escalation)
 *   STRESS_LIMIT=4                         — cap batch size (after phase filter)
 *   STRESS_SMOKE=1                         — one case per phase (carrier smoke)
 *   STRESS_JSONL / STRESS_SCREENSHOT_DIR   — override output paths
 *
 * JSONL schema (one row per case): case, phase, trace_id, session_id, prompt,
 *   thread_title, response_text, response_chars, tool_card_count, latency_ms,
 *   screenshot_path, outcome ("pass"|"fail"), error (fail only), finished_at,
 *   base_url, plus the row's want_* expectations (echoed for the analysis join).
 *
 * Screenshots (one per case, reflecting its outcome — both success AND error
 * paths are always captured): pass → {case}.png, fail → {case}_FAILED.png.
 */

import fs from "node:fs";
import path from "node:path";
import { test, expect } from "../fixtures/auth.fixture";
import {
  sendMessage,
  waitForResponse,
  waitForComposerReady,
} from "../fixtures/helpers";
import {
  filterCases,
  smokeCases,
  type PlanningStressCase,
} from "../fixtures/planning_stress_corpus";

const CASES: PlanningStressCase[] =
  process.env.STRESS_SMOKE === "1"
    ? smokeCases()
    : filterCases({
        caseFilter: process.env.STRESS_CASE_FILTER,
        phase: process.env.STRESS_PHASE,
        limit: process.env.STRESS_LIMIT
          ? Number(process.env.STRESS_LIMIT)
          : undefined,
      });

const OUTPUT_JSONL =
  process.env.STRESS_JSONL ??
  path.join(process.cwd(), "..", "cache", "planning_stress", "ui_batch.jsonl");

const OUTPUT_SCREENSHOT_DIR =
  process.env.STRESS_SCREENSHOT_DIR ??
  path.join(path.dirname(OUTPUT_JSONL), "screenshots");

const REPO_ROOT = path.resolve(process.cwd(), "..");

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
 * Evidence screenshot for one case. Tool cards + the reasoning expander are
 * force-opened first so the capture shows every tool's input/output — on a
 * failure this is the difference between "file_io errored" and the actual
 * error payload. Long <pre> JSON is wrapped (capture-only) via the CSSOM, not
 * addStyleTag: the deployed target's strict CSP blocks injected <style> tags
 * (recap-live skill note). Pass → {case}.png, fail → {case}_FAILED.png.
 */
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
  await page
    .$$eval(
      "[data-testid='tool-card'] pre, [data-testid='reasoning-summary'] p",
      (els) =>
        els.forEach((el) => {
          const s = (el as HTMLElement).style;
          s.whiteSpace = "pre-wrap";
          s.wordBreak = "break-word";
        }),
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

/**
 * Encode the corpus join key into thread_id as ``gj:{case}:{trace_id}`` so the
 * middleware derives a deterministic server-side trace_id (the same bridge the
 * GoalJudge batch uses). This is what lets analyze_planning_traces.py pull each
 * case's trace from Langfuse by the pre-computed trace_id. FE-AP-7: never send a
 * client-generated trace_id field.
 */
function installStressThreadBridge(
  page: import("@playwright/test").Page,
  caseRow: PlanningStressCase,
): void {
  const threadId = `gj:${caseRow.case}:${caseRow.trace_id}`;
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
      throw new Error("stress batch must not send client-generated trace_id");
    }
    body.thread_id = threadId;
    await route.continue({
      postData: JSON.stringify(body),
      headers: { ...request.headers(), "content-type": "application/json" },
    });
  });
}

function wantExpectations(c: PlanningStressCase): Record<string, unknown> {
  const w: Record<string, unknown> = {};
  if (c.want_depth !== undefined) w.want_depth = c.want_depth;
  if (c.want_replan !== undefined) w.want_replan = c.want_replan;
  if (c.want_reflexion !== undefined) w.want_reflexion = c.want_reflexion;
  if (c.want_terminates_at_budget !== undefined)
    w.want_terminates_at_budget = c.want_terminates_at_budget;
  if (c.want_escalation !== undefined) w.want_escalation = c.want_escalation;
  return w;
}

test.describe("Planning-pipeline tiered-loops stress (L4: real stack)", () => {
  test.skip(
    process.env.MOCK_MIDDLEWARE === "1",
    "Requires real backend — unset MOCK_MIDDLEWARE.",
  );
  test.skip(
    CASES.length === 0,
    "No cases — check STRESS_PHASE / STRESS_CASE_FILTER, or regen the corpus.",
  );

  for (const caseRow of CASES) {
    test(`stress ${caseRow.case} [${caseRow.phase}]`, async ({
      authenticatedPage: page,
    }) => {
      test.setTimeout(180_000);

      installStressThreadBridge(page, caseRow);

      const title = `gj:${caseRow.case}:${caseRow.trace_id}`;
      const wants = wantExpectations(caseRow);
      let responseText = "";
      let toolCardCount = 0;
      const startedAt = Date.now();

      try {
        await page.goto("/");
        await newThreadIfAvailable(page);

        await sendMessage(page, caseRow.prompt);
        // Source of truth is the settled response text (see waitForResponse):
        // some Cloud Run runs never disable the composer, so we cannot gate on
        // composer state. waitForComposerReady is a soft confirmation only.
        const response = await waitForResponse(page, { timeoutMs: 150_000 });
        await waitForComposerReady(page, { timeoutMs: 5_000 }).catch(() => {});

        responseText = (await response.textContent()) ?? "";
        const latencyMs = Date.now() - startedAt;
        // The ONLY DOM-level assertion: a non-empty answer rendered. Per-phase
        // correctness is the trace-analysis half's job (§5), not this spec's.
        expect(responseText.length).toBeGreaterThan(0);

        const toolCards = page.locator("[data-testid='tool-card'], .tool-card");
        toolCardCount = await toolCards.count();

        const screenshotPath = await captureEvidence(page, caseRow.case, "pass");

        appendCapture({
          case: caseRow.case,
          phase: caseRow.phase,
          trace_id: caseRow.trace_id,
          session_id: caseRow.session_id,
          prompt: caseRow.prompt,
          thread_title: title,
          response_text: responseText.slice(0, 4000),
          response_chars: responseText.length,
          tool_card_count: toolCardCount,
          latency_ms: latencyMs,
          screenshot_path: screenshotPath,
          outcome: "pass",
          finished_at: new Date().toISOString(),
          base_url: process.env.BASE_URL ?? "http://localhost:3000",
          ...wants,
        });
      } catch (err) {
        let screenshotPath: string | undefined;
        try {
          screenshotPath = await captureEvidence(page, caseRow.case, "fail");
        } catch {
          // Page may be closed; still record the failure row.
        }
        const errorMessage = err instanceof Error ? err.message : String(err);
        appendCapture({
          case: caseRow.case,
          phase: caseRow.phase,
          trace_id: caseRow.trace_id,
          session_id: caseRow.session_id,
          prompt: caseRow.prompt,
          thread_title: title,
          response_text: responseText.slice(0, 4000),
          response_chars: responseText.length,
          tool_card_count: toolCardCount,
          latency_ms: Date.now() - startedAt,
          screenshot_path: screenshotPath,
          outcome: "fail",
          error: errorMessage,
          finished_at: new Date().toISOString(),
          base_url: process.env.BASE_URL ?? "http://localhost:3000",
          ...wants,
        });
        throw err;
      }
    });
  }
});
