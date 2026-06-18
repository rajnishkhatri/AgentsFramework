/**
 * Tier 3 — memory cross-session stress run against the deployed Cloud Run stack.
 *
 * Drives the multi-session memory corpus
 * (frontend/e2e/fixtures/memory_multisession_corpus.json, regen:
 * `python scripts/build_memory_multisession_corpus.py`) through the real chat as
 * MULTIPLE SESSIONS for one persistent per-case user: each CASE is a conversation
 * = an ordered list of sessions, each session a fresh thread / one /run/stream.
 * A fact stored in session N must be recalled in session N+1.
 *
 * The spec is a DRIVER + CAPTURE; the real scoring is the trace-analysis half
 * (scripts/analyze_memory_traces.py), which pulls each probe trace and scores
 * cross-session recall / knowledge-update / abstention + the three HARD-0 gates
 * (cross-user leak / stale-after-update / fabricated memory). Per
 * docs/plans/memory_multisession_e2e_stress.plan.md §4.
 *
 * Non-determinism is the point of T3: the ONLY DOM assertion is that a non-empty
 * answer rendered; recall correctness is the analyzer's job.
 *
 * On-demand only; never in per-commit CI (real model calls). Requires the
 * MEMORY-ON revision (MEMORY_ENABLED=true):
 *   BASE_URL=<--tag mem Cloud Run revision URL>
 *   E2E_AUTHENTICATED=1  (+ WorkOS creds in repo-root .env for global-setup)
 *
 * Optional:
 *   MEM_CASE_FILTER=MEM-RECALL-units-01   — single case
 *   MEM_ABILITY=knowledge-update          — one ability
 *   MEM_LIMIT=4                            — cap (after ability filter)
 *   MEM_SMOKE=1                            — one case per ability (carrier smoke)
 *   MEM_JSONL / MEM_SCREENSHOT_DIR         — override output paths
 *
 * Probe JSONL schema (one row per PROBE session): case, mem_id, ability,
 *   provenance, user_id, session_idx, probe_trace_id, evidence_session_idx,
 *   prompt, response_text, response_chars, recalled_count_dom?, want_recall,
 *   expect_substring, screenshot_path, outcome, error?, finished_at, base_url.
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
  type MemoryCase,
  type MemorySession,
} from "../fixtures/memory_multisession_corpus";

const CASES: MemoryCase[] =
  process.env.MEM_SMOKE === "1"
    ? smokeCases()
    : filterCases({
        caseFilter: process.env.MEM_CASE_FILTER,
        ability: process.env.MEM_ABILITY,
        limit: process.env.MEM_LIMIT ? Number(process.env.MEM_LIMIT) : undefined,
      });

const OUTPUT_JSONL =
  process.env.MEM_JSONL ??
  path.join(process.cwd(), "..", "cache", "memory_multisession", "probe_batch.jsonl");

const OUTPUT_SCREENSHOT_DIR =
  process.env.MEM_SCREENSHOT_DIR ??
  path.join(path.dirname(OUTPUT_JSONL), "screenshots");

const REPO_ROOT = path.resolve(process.cwd(), "..");

// Rotate the artifact ONCE per batch (one file == one batch), like the
// planning-stress spec — an append-across-batches file makes the report's
// "latest row per case" silently span runs (reproducibility hazard). Back up
// the prior file timestamped. MEM_JSONL_APPEND=1 opts back into accumulation.
function rotateArtifactOnce(): void {
  if (process.env.MEM_JSONL_APPEND === "1") return;
  try {
    if (fs.existsSync(OUTPUT_JSONL) && fs.statSync(OUTPUT_JSONL).size > 0) {
      const stamp = new Date().toISOString().replace(/[:.]/g, "-");
      fs.renameSync(OUTPUT_JSONL, `${OUTPUT_JSONL}.${stamp}.bak`);
    }
  } catch {
    // best-effort
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

async function captureEvidence(
  page: import("@playwright/test").Page,
  shotId: string,
  outcome: "pass" | "fail",
): Promise<string> {
  await page
    .$$eval(
      "details[data-testid='tool-card'], details[data-testid='reasoning-summary']",
      (els) => els.forEach((el) => ((el as HTMLDetailsElement).open = true)),
    )
    .catch(() => {});
  fs.mkdirSync(OUTPUT_SCREENSHOT_DIR, { recursive: true });
  const name = outcome === "fail" ? `${shotId}_FAILED.png` : `${shotId}.png`;
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

/** Mint a fresh 32-hex trace_id for ONE run (no Langfuse superposition across
 * reruns — see the planning-stress spec note + [[stress-harness-traceid-superposition]]). */
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
 * Install the mem: thread bridge for ONE session of a case. The thread id
 * `mem:{mem_id}:s{session_idx}:{user_id}:{trace_id}` carries the PER-CASE user_id
 * so the backend resolves eval_user_id to it (middleware/goaljudge_saturation_bridge
 * _MEM_THREAD_RE) — that is what makes recall key on the case's user and the
 * cross-user-leak guard observable. FE-AP-7: never send a client trace_id field.
 */
function installMemThreadBridge(
  page: import("@playwright/test").Page,
  caseRow: MemoryCase,
  sessionIdx: number,
  runTraceId: string,
): void {
  const threadId = `mem:${caseRow.mem_id}:s${sessionIdx}:${caseRow.user_id}:${runTraceId}`;
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
      throw new Error("memory batch must not send client-generated trace_id");
    }
    body.thread_id = threadId;
    await route.continue({
      postData: JSON.stringify(body),
      headers: { ...request.headers(), "content-type": "application/json" },
    });
  });
}

/** Read the RecallIndicator count from the DOM (a cheap cross-check of the
 * trace's MEMORY_RECALLED count). Returns null when no indicator rendered. */
async function readRecalledCount(
  page: import("@playwright/test").Page,
): Promise<number | null> {
  const el = page.locator("[data-testid='recall-indicator']");
  if ((await el.count()) === 0) return 0; // indicator hidden == 0 recalled
  const text = (await el.first().textContent()) ?? "";
  const m = text.match(/(\d+)\s+memor/i);
  return m ? Number(m[1]) : null;
}

/** Drive ONE session (fresh thread, all its turns); return the settled answer
 * text of the LAST turn + the DOM recall count. */
async function runSession(
  page: import("@playwright/test").Page,
  caseRow: MemoryCase,
  session: MemorySession,
): Promise<{ runTraceId: string; responseText: string; recalledCountDom: number | null }> {
  const runTraceId = freshTraceId();
  await page.unroute("**/api/run/stream").catch(() => {});
  installMemThreadBridge(page, caseRow, session.session_idx, runTraceId);

  await page.goto("/");
  await newThreadIfAvailable(page);

  let responseText = "";
  for (const turn of session.turns) {
    await sendMessage(page, turn);
    const response = await waitForResponse(page, { timeoutMs: 150_000 });
    await waitForComposerReady(page, { timeoutMs: 5_000 }).catch(() => {});
    responseText = (await response.textContent()) ?? "";
  }
  const recalledCountDom = await readRecalledCount(page);
  return { runTraceId, responseText, recalledCountDom };
}

test.describe("Memory cross-session stress (L4: real stack, MEMORY_ENABLED)", () => {
  test.skip(
    process.env.MOCK_MIDDLEWARE === "1",
    "Requires real backend — unset MOCK_MIDDLEWARE.",
  );
  test.skip(
    CASES.length === 0,
    "No cases — check MEM_ABILITY / MEM_CASE_FILTER, or regen the corpus.",
  );

  for (const caseRow of CASES) {
    // Sessions within a case MUST run in order (seed before probe) — the
    // experiment is the ordering. describe.serial keeps them sequential.
    test.describe.serial(`${caseRow.case} [${caseRow.ability}]`, () => {
      for (const session of caseRow.sessions) {
        test(`s${session.session_idx} ${session.kind}`, async ({
          authenticatedPage: page,
        }) => {
          test.setTimeout(200_000);
          const shotId = `${caseRow.case}-s${session.session_idx}`;
          try {
            const { runTraceId, responseText, recalledCountDom } = await runSession(
              page,
              caseRow,
              session,
            );

            // The ONLY DOM-level assertion: a non-empty answer rendered.
            expect(responseText.length).toBeGreaterThan(0);

            // Only PROBE sessions produce a scoring row — seed/filler sessions
            // just plant state for later probes.
            if (session.kind === "probe") {
              const screenshotPath = await captureEvidence(page, shotId, "pass");
              appendCapture({
                case: caseRow.case,
                mem_id: caseRow.mem_id,
                ability: caseRow.ability,
                provenance: caseRow.provenance,
                user_id: caseRow.user_id,
                session_idx: session.session_idx,
                probe_trace_id: runTraceId,
                corpus_trace_id: session.trace_id,
                evidence_session_idx: session.evidence_session_idx ?? null,
                prompt: session.turns.join(" ⏎ "),
                response_text: responseText.slice(0, 4000),
                response_chars: responseText.length,
                recalled_count_dom: recalledCountDom,
                want_recall: session.want_recall ?? null,
                expect_substring: session.expect_substring ?? [],
                screenshot_path: screenshotPath,
                outcome: "pass",
                finished_at: new Date().toISOString(),
                base_url: process.env.BASE_URL ?? "http://localhost:3000",
              });
            }
          } catch (err) {
            let screenshotPath: string | undefined;
            try {
              screenshotPath = await captureEvidence(page, shotId, "fail");
            } catch {
              // page may be closed
            }
            const errorMessage = err instanceof Error ? err.message : String(err);
            if (session.kind === "probe") {
              appendCapture({
                case: caseRow.case,
                mem_id: caseRow.mem_id,
                ability: caseRow.ability,
                provenance: caseRow.provenance,
                user_id: caseRow.user_id,
                session_idx: session.session_idx,
                probe_trace_id: null,
                evidence_session_idx: session.evidence_session_idx ?? null,
                prompt: session.turns.join(" ⏎ "),
                response_text: "",
                response_chars: 0,
                want_recall: session.want_recall ?? null,
                expect_substring: session.expect_substring ?? [],
                screenshot_path: screenshotPath,
                outcome: "fail",
                error: errorMessage,
                finished_at: new Date().toISOString(),
                base_url: process.env.BASE_URL ?? "http://localhost:3000",
              });
            }
            throw err;
          }
        });
      }
    });
  }
});
