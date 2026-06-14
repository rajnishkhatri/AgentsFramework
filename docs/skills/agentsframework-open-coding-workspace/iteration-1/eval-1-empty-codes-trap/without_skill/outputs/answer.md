# Diagnosis: open codes missing on export to Langfuse

## TL;DR

Your codes were never committed as **chips**. In the HTML coder, an open code only
becomes part of `open_codes` when you type it into the small **"add open code, press
Enter"** input *and press Enter*. The large **memo** box is a separate field. On 2 of
your 3 rows you typed the codes into the memo (or left them sitting unsubmitted in the
input) instead of committing them as chips, so `open_codes` saved as an empty list `[]`.
Nothing is lost — the text is sitting in your `memo` field — but if you push now, those
two cases reach Langfuse with **zero codes**.

Do **not** push yet. Re-chip the two rows (in the coder or directly in the JSONL), then
re-run the exporter dry-run and confirm the "with NO codes" count is 0.

## Evidence — what's actually in `/tmp/oc_trap/coded.jsonl`

3 rows. Inspecting `open_codes` vs `memo`:

| # | trace_id (prefix) | `open_codes`         | `memo`                                                                              |
|---|-------------------|----------------------|-------------------------------------------------------------------------------------|
| 1 | `e68552dd…`       | `["depth-under-plan"]` | "good synthesis, benign miss"                                                       |
| 2 | `2c0f3fce…`       | `[]`                 | "depth-under-plan, clarification-instead-of-action, asked for info instead of doing it" |
| 3 | `9d2c84fb…`       | `[]`                 | "fabricated-delegation, incomplete-enumeration, tool errors swallowed"              |

Row 1 is correct: one code was Enter-committed into a chip. Rows 2 and 3 have **empty
`open_codes`** while their `memo` clearly contains comma-separated codes that were meant
to be chips ("depth-under-plan, clarification-instead-of-action…" / "fabricated-delegation,
incomplete-enumeration…"). The observations were captured, but in the wrong field.

## Root cause — the coder's two-field model

In `docs/skills/agentsframework-open-coding/assets/coder.html`:

- The per-case **code input** is `#code-<i>`. A code is added to state ONLY via
  `addCode(i)`, which fires on Enter:
  `onkeydown="if(event.key==='Enter')addCode(${i})"` and
  `function addCode(i){…state[i].codes.push(v);…}` (lines 59, 63). If you don't press
  Enter, the text stays in the input box and is never pushed into `codes`.
- The **memo** is a separate `<textarea id="memo-<i>">` bound directly to
  `state[i].memo` (line 60).
- Export serializes them independently:
  `codedJSONL()` → `JSON.stringify({...c, open_codes: state[i].codes, memo: state[i].memo})`
  (line 66). So `open_codes` comes *only* from committed chips; memo text never becomes a
  code.

Net: anything you typed but didn't Enter — or typed into the memo by habit — serializes as
`open_codes: []`. That is exactly rows 2 and 3.

## What the exporters do with empty codes (why this matters before pushing)

Both downstream paths happily push empty-coded rows; the dataset path even warns you:

- `docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py`
  counts `n_uncoded = sum(1 for r in rows if not r.get("open_codes"))` and prints
  `⚠ N rows have empty open_codes — codes only persist if Enter-committed as chips in the
  coder, not typed into the memo. Verify before --write.` (lines 84-88). It still writes one
  dataset item per row, with `metadata.open_codes = r.get("open_codes", [])` (lines 100-121)
  — so rows 2 and 3 would land as items with empty `open_codes` metadata.
- `scripts/push_open_codes_to_langfuse.py` is gentler: it skips rows with neither codes nor
  memo (`coded = [r for r in rows if r.get("open_codes") or r.get("memo","").strip()]`,
  line 45), but for rows 2/3 it would write a TEXT score with `value="(memo only)"` (line 59)
  — i.e. the codes still don't show up as codes, just as a memo comment.

Either way, your codes do not arrive as codes. That's the trap.

## How to check (before any push)

1. Count empty-code rows in the file directly:
   ```
   .venv/bin/python -c "import json,sys; rows=[json.loads(l) for l in open('/tmp/oc_trap/coded.jsonl') if l.strip()]; print(sum(1 for r in rows if not r.get('open_codes')),'of',len(rows),'rows have empty open_codes'); [print(r['trace_id'][:12],'memo=',r.get('memo')) for r in rows if not r.get('open_codes')]"
   ```
   Expect: `2 of 3 rows have empty open_codes`, listing the two memos that contain the
   intended codes.

2. Dry-run the dataset exporter (no `--write` = writes nothing) and read the warning line:
   ```
   .venv/bin/python docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py \
       --dataset <your-session-name> --coded /tmp/oc_trap/coded.jsonl
   ```
   It will print `(2 with NO codes)` and the ⚠ banner. If that count is not 0, do not add
   `--write`.

## How to fix

Pick one.

### Option A — fix in the coder (recommended, keeps the coder as source of truth)
1. Re-serve the coder so it can reach disk:
   `.venv/bin/python scripts/serve_open_coder.py` (or the copy under
   `docs/skills/agentsframework-open-coding/scripts/serve_open_coder.py`).
   Served over http, it hydrates from disk and persists to disk on Save.
2. For rows 2 and 3, take each comma-separated phrase out of the memo, type it into the
   **"add open code, press Enter"** box, and press **Enter** so it becomes a chip. Keep
   only genuinely narrative text (e.g. "asked for info instead of doing it") in the memo if
   you want it there, or promote it to a code too.
3. Click **Save to disk** (or **Download coded JSONL**) and confirm each previously-empty
   case now shows chips.

### Option B — patch the JSONL directly (fast, if you're confident in the split)
Move the memo phrases into `open_codes`. For example, rewrite the two rows to:
```
{"trace_id":"2c0f3fceb182424b8d1870f1e55dd370","prompt":"Refactor the auth module.","open_codes":["depth-under-plan","clarification-instead-of-action"],"memo":"asked for info instead of doing it"}
{"trace_id":"9d2c84fb4a7943008c77d460e4eecdcf","prompt":"Compare Redis and Memcached (1)(2)(3) and recommend.","open_codes":["fabricated-delegation","incomplete-enumeration","tool-errors-swallowed"],"memo":""}
```
(Use hyphenated/slugged codes consistent with row 1's `depth-under-plan`.) Note: if you
later re-open the coder against the same cases, its localStorage may re-hydrate the old
empty state — `hydrateFromDisk()` only loads from disk when localStorage has no codes/memo
for that session (lines 79-89), so prefer Option A if you'll keep using the UI.

### Then re-verify
Re-run the check in step 1/2 above. Only when "with NO codes" is **0** should you proceed
to push (`--write` for the dataset, or `--write` for the trace-score script) — and per the
task constraint here, the push itself is left to you.

## One more thing to watch (unrelated to the empty codes, but real)
Row 3's prompt is `"Compare Redis and Memcached (1)(2)(3) and recommend."` — the
trace_ids are full 32-char hex, so they will match Langfuse (the push script's
`len(tid) >= 32` guard on lines 48-53/65 passes). No trace-id problem here; the only defect
is the missing chips.

## Files referenced
- `/tmp/oc_trap/coded.jsonl` — the coded file (the evidence)
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/docs/skills/agentsframework-open-coding/assets/coder.html` — chip vs memo logic (lines 59-66)
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py` — dataset exporter + empty-codes warning (lines 84-121)
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/scripts/push_open_codes_to_langfuse.py` — trace-score pusher (lines 45-74)
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/docs/skills/agentsframework-open-coding/scripts/serve_open_coder.py` — server for disk save/hydrate
