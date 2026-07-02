# Streaming & Agentic Behavior

This is the core of testing an agent chat UI. Two properties make it different
from ordinary web testing — **incremental delivery** (a token stream) and
**non-determinism** (an LLM, not a fixture). Get these two right and your suite
stops being flaky.

## Table of contents
- [Mocking the stream (T1)](#mocking-the-stream-t1)
- [The EventSource gotcha](#the-eventsource-gotcha)
- [Sending a message reliably](#sending-a-message-reliably)
- [Waiting for a streamed reply: settle, don't "finish"](#waiting-for-a-streamed-reply)
- [Targeting the live region](#targeting-the-live-region)
- [Asserting on non-deterministic output](#asserting-on-non-deterministic-output)
- [Tool calls and generative UI](#tool-calls-and-generative-ui)
- [Injecting a join key without breaking provenance](#injecting-a-join-key)
- [Latency / TTFT benchmarks](#latency-benchmarks)

## Mocking the stream (T1)

At the highest cut, intercept the streaming request in the browser and return a
canned event stream. For SSE (`text/event-stream`), build the body from your
event objects and fulfill in one shot:

```ts
function buildSSEBody(events) {
  return events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
}
function buildSSEHeaders() {
  return {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",       // disable proxy buffering so bytes flush
    Connection: "keep-alive",
  };
}

await page.route("**/api/run/stream", async (route) => {
  await route.fulfill({ status: 200, headers: buildSSEHeaders(), body: buildSSEBody(events) });
});
```

**Limitation to state in the test:** `route.fulfill({ body })` does not chunk —
the browser receives the whole stream at once, so inter-token *timing* is
artificial. T1 is for **structural** assertions (an event rendered, a card
appeared), not for timing fidelity. For true incremental flush, mock one layer
down with a real HTTP server (T2) that writes bytes with delays, or test live (T3).

Keep a small library of canned event sequences (a happy path, a tool-call
success, a tool error, a long stream for stop/regenerate, an error path, a
generative-UI event). Parameterize each with ids (`traceId`, `runId`, `threadId`,
`messageId`) so multi-message tests can vary them.

## The EventSource gotcha

If the app streams using the **native `EventSource` API**, `page.route()` will
**not** intercept it — this is a long-standing Playwright limitation
([#15353](https://github.com/microsoft/playwright/issues/15353)). Symptoms: your
route handler never fires, the real endpoint gets hit, the test "mocks nothing".

Check how the app streams (grep for `new EventSource(` vs a `fetch()` with a
`ReadableStream` reader). If it's `EventSource`:
- mock at T2 (a real local HTTP server the app connects to), or
- test at T3 against the real backend, or
- if you control the app, consider a fetch-based stream reader (many modern
  stacks already use `fetch` precisely so it's interceptable and supports POST +
  headers, which `EventSource` can't).

This one silently invalidates otherwise-correct T1 specs, so confirm it before
writing a pile of browser-level mocks.

## Sending a message reliably

Different chat composers submit differently — plain Enter, Cmd/Ctrl+Enter, or a
button. Worse, focus/IME/remote-DOM quirks can swallow a keypress. Make
`sendMessage` resilient by attempting the primary path and falling back if the
network request didn't fire:

```ts
export async function sendMessage(page, text, opts) {
  const c = composer(page);
  await c.waitFor({ timeout: opts?.timeoutMs ?? 10_000 });
  await c.fill(text);

  // Arm the watcher BEFORE the keypress so a fast submit isn't missed.
  const submitFired = page
    .waitForRequest((r) => r.method() === "POST" && /\/api\/run\/stream\b/.test(r.url()),
      { timeout: opts?.submitFallbackMs ?? 2_000 })
    .then(() => true).catch(() => false);

  await c.press("Enter");                 // primary path
  if (!(await submitFired)) {             // fallback: click Send
    const btn = sendButton(page);
    if (await btn.count()) await btn.first().click();
  }
}
```

Use the app's *actual* submit shortcut as the primary press. Don't blind-press
Cmd/Ctrl+Enter if the composer treats that as a newline — check the composer's
keyboard contract first.

## Waiting for a streamed reply

This is where most flakiness lives. A streamed answer **grows** — it may render
`19 → 200 → 900+` chars over several seconds. There is no single "done" DOM event
you can trust. Three traps to avoid:

1. **Don't wait on the response object's `finished()`.** Behind a long-lived
   stream — and especially behind a `page.route` intercept — it may never resolve
   and will hang the whole test until timeout.
2. **Don't assume "composer re-enabled" means done.** Some backends never
   re-enable the composer after a run, or do so unreliably. Gating on it produces
   both false-done and never-done.
3. **Don't assert exact length or text** mid-stream — it's a moving target.

The reliable signal is **text settle**: poll the rendered content and consider it
ready once the trimmed text is non-empty and *unchanged across N consecutive
reads*.

```ts
export async function waitForResponse(page, opts) {
  const m = messages(page).first();
  const timeout = opts?.timeoutMs ?? 30_000;
  const gap = opts?.sampleGapMs ?? 700;
  const needStable = opts?.stableSamples ?? 3;
  const deadline = Date.now() + timeout;

  await expect.poll(async () => ((await m.textContent()) ?? "").trim().length, { timeout })
    .toBeGreaterThan(0);                       // some text arrived

  let last = "", stable = 0;
  while (Date.now() < deadline) {
    const cur = ((await m.textContent()) ?? "").trim();
    if (cur.length > 0 && cur === last) { if (++stable >= needStable) return m; }
    else { stable = 0; last = cur; }
    await page.waitForTimeout(gap);
  }
  return m;                                    // return anyway; let the caller assert
}
```

Tune `stableSamples`/`sampleGapMs` to the stream's cadence. Return the locator
even on timeout so the caller can capture *what did* render (a partial answer or a
status line) rather than throwing away the evidence — important when diagnosing a
UI that renders nothing while the backend actually succeeded.

## Targeting the live region

Streaming UIs render tokens into an `aria-live` region so assistive tech announces
them. But frameworks inject *their own* live regions. Notably, **Next.js's route
announcer is `div[aria-live="assertive"][role="alert"]`** — if your selector is a
bare `[aria-live]` you'll match the router's (empty) announcer, not the message.

Scope to the message container. If the assistant turn is an `<article>` whose
streamed text lives in a nested polite live region, target exactly that:

```ts
const MESSAGE_SELECTORS = [
  "article div[aria-live='polite']",   // the streamed content, not the router announcer
  "[data-testid='message-content']",   // best: add a testid if you own the app
  "[role='log']",
  ".message-content",
].join(", ");
```

A `data-testid` on the message container is the most robust handle — prefer
adding one over relying on ARIA structure that can drift.

## Asserting on non-deterministic output

You cannot assert the LLM said an exact sentence; it varies every run. Assert
properties that are **stable across runs**:

- **Presence/structure:** an assistant turn appeared and is non-empty; a tool card
  rendered; a code block exists; the stop button showed during streaming.
- **Provenance:** the trace id propagated end-to-end; the run id is present;
  the response carries the expected envelope/signature.
- **Bounded content:** a normalized substring or regex (case/whitespace-folded),
  not the full string. E.g. for "list the files" expect `/\b(file|directory)\b/i`,
  not a verbatim listing.
- **Budgets:** latency p50 under a threshold; token/cost ceilings if exposed.
- **Semantic, via an LLM judge:** for "is this answer relevant/safe/correct"
  questions, capture the response and score it with a separate model call (an
  "agent-as-judge"), asserting on the judge's structured verdict rather than the
  prose. This is the current best practice for behavioral correctness of
  non-deterministic output — keep it out of per-commit CI (it's slow and itself
  probabilistic) and run it as a release-gate or offline eval.

The general principle: **mock the model when you're testing the UI; judge the
model when you're testing behavior.** Don't try to do both in one assertion.

## Tool calls and generative UI

Agentic UIs render tool invocations (cards showing "called X with args Y →
result") and sometimes inline generative panels/iframes. Test them at T1 with a
canned tool-call event sequence:

- assert the tool card renders and shows the tool name / a success or error state;
- for a sandboxed generative iframe, assert the sandbox attributes are present
  (e.g. `sandbox="allow-scripts"` only — not `allow-same-origin`, which would
  defeat the sandbox);
- count tool cards as a structural signal (`page.locator("[data-testid='tool-card']").count()`).

At T3 the tools actually run; assert the *kind* of result (a card appeared, no
error state) rather than exact tool output.

## Injecting a join key

Sometimes a test must tag a run so it can be correlated later (e.g. join a UI run
to a backend record or a registry case). Do it by rewriting the **outbound
request body**, not by faking server-side identifiers:

```ts
page.route("**/api/run/stream", async (route) => {
  const body = JSON.parse(route.request().postData() ?? "{}");
  // Respect server-authority rules: never inject a client-generated trace_id if
  // the system forbids it — encode your key somewhere the server expects instead.
  if ("trace_id" in body) throw new Error("must not send client-generated trace_id");
  body.thread_id = `myprefix:${caseId}:${deterministicId}`;
  await route.continue({ postData: JSON.stringify(body),
    headers: { ...route.request().headers(), "content-type": "application/json" } });
});
```

If the system mandates server-generated provenance (a common security rule:
the *client* must not supply `trace_id`), honor it — derive your correlation id
deterministically (e.g. a UUIDv5 of the case id) and let the server own the real
trace id. Encode your join key in a field the server tolerates (like a structured
`thread_id`) and parse it server-side.

## Latency benchmarks

For TTFT (time-to-first-token) or end-to-end latency budgets, time from submit to
the first content mutation, run several iterations, and assert on a percentile
(p50/p95) rather than a single sample — one slow cold-start shouldn't fail the
gate. Capture each sample so a regression is diagnosable. These belong in the
full-stack tier (real model timing) and run on-demand.
