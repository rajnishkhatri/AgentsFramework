/**
 * Tier 3 — F1–F7 tool-calling fix-probe injection against a live LLM (localhost).
 *
 * Drives each probe prompt through the real chat composer, one probe per fix,
 * each engineered to trigger exactly one fix's seam (see `fix_probes.ts`). The
 * DOM capture is reconciled server-side against BlackBox carriers + Langfuse
 * spans by `scripts/analyze_fix_probes.py` — this spec only DRIVES the run and
 * records the join keys; it deliberately asserts almost nothing about prose
 * (TAP-3: live LLM output is non-deterministic; the carriers are the contract).
 *
 * On-demand only; requires a real backend (unset MOCK_MIDDLEWARE) and the
 * pinned providers reachable for F3 (DeepSeek) / F7 (GLM/Z.ai). Probes whose
 * provider is unavailable SKIP with a recorded reason — never a silent pass.
 *
 * Plan: docs/plans/toolcalling_f1f7_live_validation.plan.md
 *
 * Prerequisites:
 *   BASE_URL=http://localhost:3000   (or a deployed frontend)
 *   E2E_AUTHENTICATED=1 / E2E_FAKE_SESSION=1
 *   MODEL_PROFILE_SET=all            (so default + deepseek + glm all resolve)
 *
 * Optional:
 *   FIX_PROBE_FILTER=P-F1-path       — single probe
 *   FIX_PROBE_LIMIT=3                — cap batch size
 *   FIX_PROBE_AVAILABLE_PINS=deepseek,glm
 *                                    — comma list of pins reachable locally;
 *                                      a probe whose pin is absent SKIPs. Default
 *                                      empty => only default-provider probes run.
 *   FIX_PROBE_JSONL                  — override JSONL output path
 *   FIX_PROBE_SCREENSHOT_DIR        — override screenshot dir
 *
 * JSONL schema (one row per probe):
 *   probe_id, fix, pinned_model, trace_id, session_id, prompts[], thread_title,
 *   response_text, tool_card_count, tool_output, expected_error_class,
 *   expected_marker, expected_goal_met, negative_control, screenshot_path,
 *   outcome ("pass" | "fail"), error (fail only), turns, finished_at, base_url
 */

import fs from "node:fs";
import path from "node:path";
import { test, expect } from "../fixtures/auth.fixture";
import {
  sendMessage,
  waitForResponse,
  waitForComposerReady,
} from "../fixtures/helpers";
import { filterProbes, type FixProbeCase } from "../fixtures/fix_probes";

const PROBES = filterProbes({
  filter: process.env.FIX_PROBE_FILTER,
  limit: process.env.FIX_PROBE_LIMIT
    ? Number(process.env.FIX_PROBE_LIMIT)
    : undefined,
});

const OUTPUT_JSONL =
  process.env.FIX_PROBE_JSONL ??
  path.join(process.cwd(), "..", "cache", "fix_probe_eval", "ui_batch.jsonl");

const OUTPUT_SCREENSHOT_DIR =
  process.env.FIX_PROBE_SCREENSHOT_DIR ??
  path.join(path.dirname(OUTPUT_JSONL), "ui_batch_screenshots");

const REPO_ROOT = path.resolve(process.cwd(), "..");

/** Pins the local backend can actually serve (DeepSeek/GLM need direct keys). */
const AVAILABLE_PINS = new Set(
  (process.env.FIX_PROBE_AVAILABLE_PINS ?? "")
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean),
);

function appendCapture(row: Record<string, unknown>): void {
  const dir = path.dirname(OUTPUT_JSONL);
  fs.mkdirSync(dir, { recursive: true });
  fs.appendFileSync(OUTPUT_JSONL, `${JSON.stringify(row)}\n`, "utf8");
}

function screenshotAbsPath(probeId: string, outcome: "pass" | "fail"): string {
  const suffix = outcome === "fail" ? "_FAILED" : "";
  return path.join(OUTPUT_SCREENSHOT_DIR, `${probeId}${suffix}.png`);
}

function screenshotRelPath(absPath: string): string {
  const resolved = path.resolve(absPath);
  if (resolved.startsWith(`${REPO_ROOT}${path.sep}`)) {
    return path.relative(REPO_ROOT, resolved);
  }
  return resolved;
}

async function captureProbeScreenshot(
  page: import("@playwright/test").Page,
  probeId: string,
  outcome: "pass" | "fail",
): Promise<string> {
  fs.mkdirSync(OUTPUT_SCREENSHOT_DIR, { recursive: true });
  const absPath = screenshotAbsPath(probeId, outcome);
  const attachName = path.basename(absPath);
  const buffer = await page.screenshot({ fullPage: true });
  fs.writeFileSync(absPath, buffer);
  await test.info().attach(attachName, {
    body: buffer,
    contentType: "image/png",
  });
  return screenshotRelPath(absPath);
}

/**
 * Rewrite outbound /api/run/stream bodies so thread_id encodes the probe join
 * key as ``gj:{probe_id}:{trace_id}`` (the bridge regex the analyzer already
 * parses), and inject the per-probe model pin. The pin rides
 * ``body.input.pinned_model`` (see ui_input_to_agent_request.ts) — the
 * ``?model=`` URL seed sets it too, but we set it here defensively so the pin is
 * guaranteed regardless of how the composer hydrated. FE-AP-7: a client-
 * generated ``trace_id`` on the body is a hard error (the backend derives it).
 */
function installProbeThreadBridge(
  page: import("@playwright/test").Page,
  probe: FixProbeCase,
): void {
  // Use case_id (GJ-FIX-NN) so the backend's `gj:` regex parses the thread and
  // adopts probe.trace_id as the BlackBox workflow_id (the join key the analyzer
  // resolves). probe.id is the human label and is NOT wire-valid for that regex.
  const threadId = `gj:${probe.case_id}:${probe.trace_id}`;
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
      throw new Error("fix-probe batch must not send client-generated trace_id");
    }
    body.thread_id = threadId;
    if (probe.pinned_model) {
      const input =
        (body.input as Record<string, unknown> | undefined) ?? {};
      input.pinned_model = probe.pinned_model;
      body.input = input;
    }
    await route.continue({
      postData: JSON.stringify(body),
      headers: { ...request.headers(), "content-type": "application/json" },
    });
  });
}

/** Navigate with the pin pre-seeded via ?model= (mirrors model-ab.spec.ts). */
async function gotoWithPin(
  page: import("@playwright/test").Page,
  probe: FixProbeCase,
): Promise<void> {
  const url = probe.pinned_model
    ? `/?model=${encodeURIComponent(probe.pinned_model)}`
    : "/";
  await page.goto(url);
}

/**
 * Capture the streamed tool-card output text so the analyzer can grep the F2/F3
 * markers from the DOM as a cross-check against the persisted ToolMessage.
 */
async function readToolOutput(
  page: import("@playwright/test").Page,
): Promise<{ count: number; text: string }> {
  const cards = page.locator("[data-testid='tool-card'], .tool-card");
  const count = await cards.count();
  let text = "";
  for (let i = 0; i < count; i++) {
    text += `${(await cards.nth(i).textContent()) ?? ""}\n`;
  }
  return { count, text };
}

test.describe("F1–F7 fix-probe batch (T3: live-LLM carrier validation)", () => {
  test.skip(
    process.env.MOCK_MIDDLEWARE === "1",
    "Requires real backend — unset MOCK_MIDDLEWARE.",
  );

  test.skip(
    PROBES.length === 0,
    "No probes — check FIX_PROBE_FILTER / FIX_PROBE_LIMIT.",
  );

  for (const probe of PROBES) {
    test(`probe ${probe.id} (${probe.fix})`, async ({
      authenticatedPage: page,
    }) => {
      // A probe with a non-default pin SKIPs (not fails) when its provider is
      // not reachable locally — recorded, never a silent pass.
      if (
        probe.pinned_model &&
        !AVAILABLE_PINS.has(probe.pinned_model.toLowerCase())
      ) {
        const reason = `pin '${probe.pinned_model}' unavailable (set FIX_PROBE_AVAILABLE_PINS)`;
        appendCapture({
          probe_id: probe.id,
          case_id: probe.case_id,
          fix: probe.fix,
          pinned_model: probe.pinned_model,
          trace_id: probe.trace_id,
          session_id: probe.session_id,
          prompts: probe.turns.map((t) => t.prompt),
          outcome: "skip",
          skip_reason: reason,
          finished_at: new Date().toISOString(),
          base_url: process.env.BASE_URL ?? "http://localhost:3000",
        });
        test.skip(true, reason);
        return;
      }

      test.setTimeout(240_000);
      installProbeThreadBridge(page, probe);

      const title = `gj:${probe.case_id}:${probe.trace_id}`;
      let responseText = "";
      let toolCardCount = 0;
      let toolOutput = "";

      try {
        await gotoWithPin(page, probe);

        // Multi-turn probes (F7) send every turn in the SAME thread — never
        // click "New chat" between turns, so state["messages"] is non-empty on
        // turn ≥2 (the exact condition F7 targets).
        for (let i = 0; i < probe.turns.length; i++) {
          const isLastTurn = i === probe.turns.length - 1;
          await sendMessage(page, probe.turns[i].prompt);
          const response = await waitForResponse(page, { timeoutMs: 180_000 });
          await waitForComposerReady(page, { timeoutMs: 5_000 }).catch(() => {});
          responseText = (await response.textContent()) ?? "";
          // This spec DRIVES + CAPTURES; analyze_fix_probes.py is the real gate
          // (carriers, not prose). We only assert non-empty on the FINAL turn of
          // a normal probe, to confirm the run produced something rather than
          // hanging. Intermediate turns may legitimately render empty (e.g. GLM
          // empty-output), and live_unforcible probes (F6) intentionally aim for
          // an empty answer — so don't gate those on non-empty text here.
          if (isLastTurn && !probe.live_unforcible) {
            expect(responseText.length).toBeGreaterThan(0);
          }
        }

        const tool = await readToolOutput(page);
        toolCardCount = tool.count;
        toolOutput = tool.text;

        const screenshotPath = await captureProbeScreenshot(page, probe.id, "pass");

        appendCapture({
          probe_id: probe.id,
          case_id: probe.case_id,
          fix: probe.fix,
          pinned_model: probe.pinned_model ?? null,
          trace_id: probe.trace_id,
          session_id: probe.session_id,
          prompts: probe.turns.map((t) => t.prompt),
          turns: probe.turns.length,
          thread_title: title,
          response_text: responseText.slice(0, 4000),
          tool_card_count: toolCardCount,
          tool_output: toolOutput.slice(0, 8000),
          expected_error_class: probe.expected_error_class ?? null,
          expected_marker: probe.expected_marker ?? null,
          expected_goal_met:
            probe.expected_goal_met === undefined
              ? null
              : probe.expected_goal_met,
          negative_control: probe.negative_control ?? null,
          live_unforcible: probe.live_unforcible ?? false,
          screenshot_path: screenshotPath,
          outcome: "pass",
          finished_at: new Date().toISOString(),
          base_url: process.env.BASE_URL ?? "http://localhost:3000",
        });
      } catch (err) {
        let screenshotPath: string | undefined;
        try {
          screenshotPath = await captureProbeScreenshot(page, probe.id, "fail");
        } catch {
          // Page may be closed; still record the failure row.
        }

        const errorMessage = err instanceof Error ? err.message : String(err);
        appendCapture({
          probe_id: probe.id,
          case_id: probe.case_id,
          fix: probe.fix,
          pinned_model: probe.pinned_model ?? null,
          trace_id: probe.trace_id,
          session_id: probe.session_id,
          prompts: probe.turns.map((t) => t.prompt),
          turns: probe.turns.length,
          thread_title: title,
          response_text: responseText.slice(0, 4000),
          tool_card_count: toolCardCount,
          tool_output: toolOutput.slice(0, 8000),
          expected_error_class: probe.expected_error_class ?? null,
          expected_marker: probe.expected_marker ?? null,
          expected_goal_met:
            probe.expected_goal_met === undefined
              ? null
              : probe.expected_goal_met,
          negative_control: probe.negative_control ?? null,
          live_unforcible: probe.live_unforcible ?? false,
          screenshot_path: screenshotPath,
          outcome: "fail",
          error: errorMessage,
          finished_at: new Date().toISOString(),
          base_url: process.env.BASE_URL ?? "http://localhost:3000",
        });
        throw err;
      }
    });
  }
});
