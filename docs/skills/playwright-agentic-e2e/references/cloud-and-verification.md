# Cloud-Hosted Targets & Server-Side Verification

Driving a real deployment is half the job. For an agentic system the other half is
proving the *backend* did the right thing — the request reached the agent, the
expected work happened, a trace was recorded. The DOM can't show that, and a blank
DOM doesn't always mean the backend failed.

## Table of contents
- [Pointing tests at a cloud deployment](#pointing-tests-at-a-cloud-deployment)
- [Why verify server-side](#why-verify-server-side)
- [Querying structured logs (the jsonPayload trap)](#querying-structured-logs)
- [Reconciling DOM captures with backend traces](#reconciling-dom-with-traces)
- [Using verify_run.py](#using-verify_runpy)
- [Observability backends](#observability-backends)

## Pointing tests at a cloud deployment

Covered mechanically in `running-and-ci.md`; the cloud-specific notes:

- **Cloud Run / Vercel / Fly** all serve over HTTPS at a stable hostname. Set
  `BASE_URL` to that URL; the conditional `webServer` then starts nothing local.
- **Cookies must be `secure`** against an HTTPS origin. If you mint a fake
  session (local only), set `secure: true` when the base URL is `https:`. For real
  sign-in this is automatic.
- **Cold starts** inflate first-request latency (a scaled-to-zero Cloud Run
  service can take seconds to wake). Give the first navigation and the sign-in a
  generous timeout, and base latency assertions on percentiles over several runs,
  not a single cold sample.
- **Know your topology.** Note the frontend URL *and* the backend/service URL, the
  cloud project, and the region — you'll need them to find this run's logs. Record
  them in the capture artifact (store `base_url` per row).

## Why verify server-side

A green DOM assertion proves the **frontend rendered something**. It does not
prove the agent ran, the right tools fired, or a trace exists. And the failure
modes are asymmetric:

- The UI can render a final answer while the backend quietly used a fallback.
- **The backend can fully succeed while the UI renders nothing** — the run
  completed, the trace exists, but the final token never reached the live region
  (a frontend streaming/render gap). If you only assert on the DOM you'd call this
  a backend failure, which is wrong and sends you debugging the wrong layer.

So for full-stack runs, capture the DOM result **and** cross-check the backend.
Treat them as two independent signals.

## Querying structured logs

Modern platforms emit **structured** (JSON) logs, and the field your line lands in
matters. On Google Cloud Logging, a `console.log("...")` of a plain string lands
in `textPayload`, but a structured/JSON log entry lands in `jsonPayload` — and a
message emitted by many logging libraries ends up at **`jsonPayload.message`**,
*not* `textPayload`. Querying `textPayload` will then return nothing and you'll
wrongly conclude the event never logged.

A working Cloud Logging query for a run's bridge/marker line:

```bash
gcloud logging read \
  'resource.type="cloud_run_revision"
   AND resource.labels.service_name="<your-service>"
   AND jsonPayload.message=~"<your-marker-substring>"' \
  --project=<your-project> \
  --freshness=1h \
  --format='value(timestamp, jsonPayload.message)' \
  --limit=200
```

Notes:
- Try **both** `jsonPayload.message` and `textPayload` if unsure where your code's
  logs land — grep the source for how it logs (structured logger vs `print`/`console`).
- `--freshness` scopes to the run window so you don't sift days of logs.
- Lines can duplicate (retries, multi-replica) — **dedupe** before counting
  (e.g. by a per-run id) so "22 distinct cases" doesn't read as 40.
- Equivalent ideas elsewhere: CloudWatch Logs Insights (`fields @message | filter
  @message like /marker/`), Vercel `vercel logs`, Datadog log search.

## Reconciling DOM with traces

The reconciliation that actually tells you what happened:

| Check | Source | What it proves |
| --- | --- | --- |
| Capture has N rows | your JSONL artifact | the harness drove N cases |
| Correlation id matches expectation | artifact vs. derivation | the join key is correct (e.g. UUIDv5 of case id) |
| N marker lines in logs | Cloud Logging (deduped) | the request reached the backend N times |
| N traces for this run/user | tracing backend | the agent actually executed N times |
| M of N rendered a final answer | artifact (strip status-feed prefix) | the UI render rate — the *frontend* gap, if any |

The last row is the subtle one. A streamed answer's captured text may include a
leading **status feed** ("Using tools: …") that progressively gets replaced by the
real answer. A naive `len(text) > 0` or "starts with 'Using tools'" check
miscounts — fully-answered runs *also* begin with that prefix. To split "rendered
a real answer" from "status-feed only", **strip the leading status segments**
(e.g. regex out `(Using tools:[^…]*…)+`) before measuring. Getting this wrong
flips your headline number (e.g. 11/22 vs 21/22). `verify_run.py` does this strip.

The healthy outcome looks like: N rows == N marker lines == N traces (backend did
all the work), while M ≤ N rendered an answer (the UI render rate). If backend
counts match but M < N, the bug is in the **frontend stream→DOM** path, not the
agent.

## Using verify_run.py

`scripts/verify_run.py` is a starting point that ties the capture artifact to the
backend signals. It:

- loads a JSONL capture (one row per case),
- reports the rendered-answer vs. status-feed-only split (with the status-prefix
  strip done correctly),
- checks correlation ids against a deterministic derivation, and
- optionally diffs the captured case set against a Cloud Logging marker count you
  pass in (it prints the `gcloud` query to run; it does not assume creds).

```bash
python scripts/verify_run.py --jsonl cache/eval/ui_batch.jsonl \
  --status-prefix "Using tools:" \
  [--expect-cases 22] [--id-namespace dns]
```

Adapt the field names and the status prefix to your app. It's intentionally
dependency-light (stdlib only) so it runs anywhere.

## Observability backends

Whatever you use, the verification idea is the same: **count the runs the backend
recorded and match them to what the harness drove.**

- **Langfuse:** list traces by user/session/tag for the run window
  (`lf.api.trace.list(user_id=..., limit=...)`) and count; compare to your row
  count. Trace ids in your capture should resolve to real traces.
- **OpenTelemetry / Jaeger / Tempo / Cloud Trace:** query spans by the run's
  attribute or trace id; assert the expected root spans exist.
- **W&B Weave / LangSmith:** filter the project by run id/tag; the captured ids
  should map to recorded traces.

If verdict-level signals (did the agent meet the goal, was the failure graceful)
aren't emitted as *structured* fields you can query, you can usually still verify
the **integrity** layer — that the right set of runs/traces exists — even when the
semantic axes aren't machine-readable on that platform. Verify what's queryable;
note what isn't.
