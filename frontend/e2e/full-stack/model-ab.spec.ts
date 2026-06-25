/**
 * Tier 3 — extensive model A/B sweep against the deployed Cloud Run stack.
 *
 * Generalizes planning-stress.spec.ts into a MODEL × CASE matrix: every model
 * arm is pinned through the REAL Composer dropdown (input.pinned_model rides the
 * run), driven over the benchmark-shaped corpus (general / multi-turn / memory),
 * capturing per-cell: a screenshot, TTFT + total latency, and a JSONL row whose
 * trace_id joins to Langfuse (scripts/analyze_model_ab.py does the per-cell trace
 * pull + integrity + token/cost/latency aggregation).
 *
 * Plan: docs/plans/model_ab_extensive_e2e.plan.md.
 * Methodology: docs/skills/playwright-agentic-e2e.
 *
 * COST CONTROL (plan §2.0): the two reasoning arms (claude-opus-4-8,
 * deepseek-v4-pro) are RESTRICTED to reasoning-eligible cases (isReasoningEligible
 * — L2/L3 or multi-turn) and SAMPLED (seeded fraction, REPEAT=1). The cheap arms +
 * Auto take every case at MODEL_AB_REPEAT (default 3). Opus/Pro NEVER run on
 * routine L1 general cases.
 *
 * On-demand only; never in per-commit CI (real model calls, real cost,
 * non-deterministic — skill golden rule). Requires the A/B revision with
 * MODEL_PROFILE_SET=all (so /models offers every arm) + all three provider keys:
 *   BASE_URL=<ab---agent-frontend URL>   E2E_AUTHENTICATED=1
 *
 * ALWAYS pin --project=chromium for a real run — the matrix is per-test, so the
 * default multi-browser project list would multiply the (paid) run count by the
 * number of browsers. Use MODEL_AB_DRY_RUN=1 first to review the projected runs.
 *
 * Env knobs:
 *   MODEL_AB_MODELS=gpt-4o-mini,claude-haiku-4-5   — arm subset (default: all 8)
 *   MODEL_AB_FAMILY=general|multi-turn|memory       — one family
 *   MODEL_AB_CASE_FILTER=GEN-L1-01                  — one case
 *   MODEL_AB_LIMIT=4                                 — cap cases (after family)
 *   MODEL_AB_SMOKE=1                                 — one case per family per arm
 *   MODEL_AB_REPEAT=3 / MODEL_AB_REASONING_REPEAT=1  — repeats (cheap / Opus,Pro)
 *   MODEL_AB_REASONING_SAMPLE=0.4                    — Opus/Pro eligible-case sample
 *   MODEL_AB_DRY_RUN=1                               — print the matrix, run nothing
 *   MODEL_AB_JSONL / MODEL_AB_SCREENSHOT_DIR         — output overrides
 *
 * JSONL row (one per model×case×repeat): model, family, difficulty, case, gj_id,
 *   trace_id (per-run), corpus_trace_id, repeat, prompt, response_text,
 *   response_chars, tool_card_count, ttft_ms, latency_ms, screenshot_path,
 *   outcome, finished_at, base_url.
 */

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { test, expect } from "../fixtures/auth.fixture";
import {
  sendMessage,
  waitForResponse,
  waitForComposerReady,
} from "../fixtures/helpers";
import {
  loadCases,
  smokeCases,
  isReasoningEligible,
  type ModelAbCase,
} from "../fixtures/model_ab_corpus";

// ── matrix config ───────────────────────────────────────────────────────────

const ALL_MODELS = [
  "Auto",
  "gpt-4o-mini",
  "gpt-4o",
  "claude-haiku-4-5",
  "claude-sonnet-4-6",
  "claude-opus-4-8",
  "deepseek-v4-flash",
  "deepseek-v4-pro",
] as const;

// The expensive reasoning arms: eligibility-filtered + sampled (plan §2.0).
const REASONING_MODELS = new Set(["claude-opus-4-8", "deepseek-v4-pro"]);

const REPEAT = Number(process.env.MODEL_AB_REPEAT ?? 3);
const REASONING_REPEAT = Number(process.env.MODEL_AB_REASONING_REPEAT ?? 1);
const REASONING_SAMPLE = Number(process.env.MODEL_AB_REASONING_SAMPLE ?? 0.4);
const DRY_RUN = process.env.MODEL_AB_DRY_RUN === "1";

const MODELS: string[] = (process.env.MODEL_AB_MODELS
  ? process.env.MODEL_AB_MODELS.split(",").map((m) => m.trim()).filter(Boolean)
  : [...ALL_MODELS]
).filter((m) => (ALL_MODELS as readonly string[]).includes(m));

const BASE_CASES: ModelAbCase[] =
  process.env.MODEL_AB_SMOKE === "1"
    ? smokeCases()
    : loadCases({
        family: process.env.MODEL_AB_FAMILY,
        caseFilter: process.env.MODEL_AB_CASE_FILTER,
        limit: process.env.MODEL_AB_LIMIT
          ? Number(process.env.MODEL_AB_LIMIT)
          : undefined,
      });

const OUTPUT_JSONL =
  process.env.MODEL_AB_JSONL ??
  path.join(process.cwd(), "..", "cache", "model_ab_live", "ui_batch.jsonl");

const OUTPUT_SCREENSHOT_DIR =
  process.env.MODEL_AB_SCREENSHOT_DIR ??
  path.join(path.dirname(OUTPUT_JSONL), "screenshots");

const REPO_ROOT = path.resolve(process.cwd(), "..");

// ── seeded sampling (deterministic, reproducible — plan §2.0) ─────────────────

/** Stable 0..1 hash of a string (FNV-1a → normalized). The seed includes the
 *  model so each reasoning arm samples its own reproducible subset. */
function seededUnitHash(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return ((h >>> 0) % 100000) / 100000;
}

/** The cases ONE model runs: reasoning arms get eligibility-filter + seeded
 *  sample; cheap arms + Auto get every case. */
function casesForModel(model: string): ModelAbCase[] {
  if (!REASONING_MODELS.has(model)) return BASE_CASES;
  const eligible = BASE_CASES.filter(isReasoningEligible);
  if (REASONING_SAMPLE >= 1) return eligible;
  return eligible.filter(
    (c) => seededUnitHash(`${model}:${c.gj_id}`) < REASONING_SAMPLE,
  );
}

function repeatsForModel(model: string): number {
  return REASONING_MODELS.has(model) ? REASONING_REPEAT : REPEAT;
}

// ── capture I/O (one file == one batch — the Stage-B report-integrity rule) ──

function rotateArtifactOnce(): void {
  if (process.env.MODEL_AB_JSONL_APPEND === "1") return;
  try {
    if (fs.existsSync(OUTPUT_JSONL) && fs.statSync(OUTPUT_JSONL).size > 0) {
      const stamp = new Date().toISOString().replace(/[:.]/g, "-");
      fs.renameSync(OUTPUT_JSONL, `${OUTPUT_JSONL}.${stamp}.bak`);
    }
  } catch {
    /* best-effort */
  }
}
if (!DRY_RUN) rotateArtifactOnce();

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

// ── per-run trace_id + thread bridge (no Langfuse superposition) ──────────────

function freshTraceId(): string {
  const buf = crypto.randomBytes(16);
  return Array.from(buf, (b) => b.toString(16).padStart(2, "0")).join("");
}

/** Inject thread_id=gj:{gj_id}:{runTraceId} so the middleware adopts a
 *  deterministic server-side trace_id (the model-A/B family ids GJ-AB*-NN parse
 *  via the broadened bridge regex). The route PRESERVES the rest of the POST body
 *  — crucially input.pinned_model, which the dropdown selection already set. */
function installThreadBridge(
  page: import("@playwright/test").Page,
  caseRow: ModelAbCase,
  runTraceId: string,
): void {
  const threadId = `gj:${caseRow.gj_id}:${runTraceId}`;
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
      throw new Error("model-ab batch must not send client-generated trace_id");
    }
    body.thread_id = threadId;
    await route.continue({
      postData: JSON.stringify(body),
      headers: { ...request.headers(), "content-type": "application/json" },
    });
  });
}

// ── model pin via the real dropdown ──────────────────────────────────────────

/** Open the Composer model picker and select `model` (the testids added to
 *  Composer.tsx). Auto is the default; selecting it is still explicit so a prior
 *  cell's pin never bleeds across. */
async function pinModel(
  page: import("@playwright/test").Page,
  model: string,
): Promise<void> {
  await page.locator("[data-testid='model-picker-trigger']").first().click();
  const opt = page.locator(`[data-testid='model-option-${model}']`).first();
  await opt.waitFor({ state: "visible", timeout: 5_000 });
  await opt.click();
}

async function newThreadIfAvailable(
  page: import("@playwright/test").Page,
): Promise<void> {
  const btn = page.locator(
    "[data-testid='new-thread'], button:has-text('New chat'), button:has-text('New')",
  );
  if ((await btn.count()) > 0) await btn.first().click();
}

async function captureEvidence(
  page: import("@playwright/test").Page,
  model: string,
  caseId: string,
  repeat: number,
  outcome: "pass" | "fail",
): Promise<string> {
  await page
    .$$eval(
      "details[data-testid='tool-card'], details[data-testid='reasoning-summary']",
      (els) => els.forEach((el) => ((el as HTMLDetailsElement).open = true)),
    )
    .catch(() => {});
  const dir = path.join(OUTPUT_SCREENSHOT_DIR, model);
  fs.mkdirSync(dir, { recursive: true });
  const suffix = outcome === "fail" ? "_FAILED" : "";
  const absPath = path.join(dir, `${caseId}_r${repeat}${suffix}.png`);
  const buffer = await page.screenshot({ fullPage: true });
  fs.writeFileSync(absPath, buffer);
  await test
    .info()
    .attach(`${model}/${caseId}_r${repeat}`, {
      body: buffer,
      contentType: "image/png",
    });
  return screenshotRelPath(absPath);
}

// ── dry-run: print the matrix + projected runs, execute nothing ──────────────

function logMatrix(): void {
  let total = 0;
  const lines: string[] = ["[model-ab] DRY RUN — projected matrix:"];
  for (const model of MODELS) {
    const cases = casesForModel(model);
    const reps = repeatsForModel(model);
    const runs = cases.length * reps;
    total += runs;
    lines.push(
      `  ${model.padEnd(24)} cases=${String(cases.length).padStart(2)} ` +
        `× repeat=${reps} = ${runs} runs` +
        (REASONING_MODELS.has(model) ? "  (reasoning-eligible + sampled)" : ""),
    );
  }
  lines.push(`  TOTAL runs: ${total}`);
  // eslint-disable-next-line no-console
  console.log(lines.join("\n"));
}

// ── the matrix ───────────────────────────────────────────────────────────────

test.describe("Model A/B sweep (L4: real stack, UI-pinned)", () => {
  test.skip(
    process.env.MOCK_MIDDLEWARE === "1",
    "Requires real backend — unset MOCK_MIDDLEWARE.",
  );
  test.skip(
    MODELS.length === 0 || BASE_CASES.length === 0,
    "No models or cases — check MODEL_AB_MODELS / MODEL_AB_FAMILY / corpus.",
  );

  if (DRY_RUN) {
    test("dry-run: print the matrix (no LLM calls)", () => {
      logMatrix();
      expect(MODELS.length).toBeGreaterThan(0);
    });
    return;
  }

  for (const model of MODELS) {
    const cases = casesForModel(model);
    const reps = repeatsForModel(model);
    for (const caseRow of cases) {
      for (let repeat = 1; repeat <= reps; repeat++) {
        test(`${model} · ${caseRow.case} [${caseRow.family}/${caseRow.difficulty}] r${repeat}`, async ({
          authenticatedPage: page,
        }) => {
          test.setTimeout(200_000);

          const runTraceId = freshTraceId();
          installThreadBridge(page, caseRow, runTraceId);

          // Each row is a single-shot prompt OR a multi-turn `turns` array.
          const turns: string[] = caseRow.turns ?? [caseRow.prompt ?? ""];
          let responseText = "";
          let toolCardCount = 0;
          let ttftMs = 0;
          const startedAt = Date.now();

          try {
            await page.goto("/");
            await newThreadIfAvailable(page);
            // Pin the model BEFORE the first send so input.pinned_model is set.
            await pinModel(page, model);

            for (let i = 0; i < turns.length; i++) {
              const turnStart = Date.now();
              await sendMessage(page, turns[i]!);
              const response = await waitForResponse(page, {
                timeoutMs: 150_000,
              });
              if (i === 0) ttftMs = Date.now() - turnStart;
              responseText = (await response.textContent()) ?? "";
              await waitForComposerReady(page, { timeoutMs: 5_000 }).catch(
                () => {},
              );
            }

            const latencyMs = Date.now() - startedAt;
            // The ONLY DOM assertion: a non-empty answer rendered. Per-(model,
            // family) scoring is the analyzer's job, not this spec's.
            expect(responseText.length).toBeGreaterThan(0);

            toolCardCount = await page
              .locator("[data-testid='tool-card'], .tool-card")
              .count();
            const screenshotPath = await captureEvidence(
              page,
              model,
              caseRow.case,
              repeat,
              "pass",
            );

            appendCapture({
              model,
              family: caseRow.family,
              difficulty: caseRow.difficulty,
              case: caseRow.case,
              gj_id: caseRow.gj_id,
              trace_id: runTraceId,
              corpus_trace_id: caseRow.trace_id,
              repeat,
              prompt: turns.join("\n---\n").slice(0, 2000),
              response_text: responseText.slice(0, 4000),
              response_chars: responseText.length,
              tool_card_count: toolCardCount,
              ttft_ms: ttftMs,
              latency_ms: latencyMs,
              screenshot_path: screenshotPath,
              outcome: "pass",
              finished_at: new Date().toISOString(),
              base_url: process.env.BASE_URL ?? "http://localhost:3000",
            });
          } catch (err) {
            let screenshotPath: string | undefined;
            try {
              screenshotPath = await captureEvidence(
                page,
                model,
                caseRow.case,
                repeat,
                "fail",
              );
            } catch {
              /* page may be closed */
            }
            appendCapture({
              model,
              family: caseRow.family,
              difficulty: caseRow.difficulty,
              case: caseRow.case,
              gj_id: caseRow.gj_id,
              trace_id: runTraceId,
              corpus_trace_id: caseRow.trace_id,
              repeat,
              response_text: responseText.slice(0, 4000),
              response_chars: responseText.length,
              tool_card_count: toolCardCount,
              ttft_ms: ttftMs,
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
    }
  }
});
