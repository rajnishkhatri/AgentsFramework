/**
 * One-off diagnostic: POST /api/run/stream on the deployed stack using the
 * saved storage state, and dump the raw SSE lines. Not a test — run with tsx.
 */
import { chromium } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "https://agent-frontend-w65nrxwkiq-uc.a.run.app";

async function main(): Promise<void> {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ storageState: "e2e/.auth/state.json" });
  const page = await ctx.newPage();
  await page.goto(BASE_URL);
  if (process.env.DEBUG_PROMPT) {
    await page.evaluate((p) => { (window as unknown as { __PROMPT__?: string }).__PROMPT__ = p; }, process.env.DEBUG_PROMPT);
  }
  if (process.env.DEBUG_THREAD) {
    await page.evaluate((t) => { (window as unknown as { __THREAD__?: string }).__THREAD__ = t; }, process.env.DEBUG_THREAD);
  }

  const dump = await page.evaluate(async () => {
    const res = await fetch("/api/run/stream", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        thread_id: (window as unknown as { __THREAD__?: string }).__THREAD__ ?? `debug-sse-${Date.now()}`,
        input: {
          messages: [{ role: "user", content: (window as unknown as { __PROMPT__?: string }).__PROMPT__ ?? "Create a file /workspace/sse_debug.txt containing the word hello, then tell me what you did." }],
        },
      }),
    });
    const lines: string[] = [];
    lines.push(`HTTP ${res.status} content-type=${res.headers.get("content-type")}`);
    if (!res.body) return lines.concat("<no body>");
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    const t0 = Date.now();
    while (Date.now() - t0 < 120_000) {
      const { done, value } = await reader.read();
      if (done) { lines.push("<stream closed>"); break; }
      buf += dec.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, idx).trimEnd();
        buf = buf.slice(idx + 1);
        if (line) lines.push(line.length > 400 ? line.slice(0, 400) + "…" : line);
      }
      if (lines.length > 300) { lines.push("<truncated at 300 lines>"); break; }
    }
    return lines;
  });

  for (const l of dump) console.log(l);
  await browser.close();
}

main().catch((e) => { console.error(e); process.exit(1); });
