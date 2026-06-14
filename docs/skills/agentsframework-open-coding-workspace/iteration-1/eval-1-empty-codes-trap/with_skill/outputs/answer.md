# Diagnosis: your open codes never made it into `open_codes` — they're stuck in the memo

## What went wrong

This is the single most common open-coding failure, called out as **"the trap"** in
Step 4 of the `agentsframework-open-coding` skill:

> **The single most common failure: memos full of prose, `open_codes` empty.** Codes
> only persist if you press **Enter** to turn each into a chip. Typing a comma-list
> into the memo box does *not* populate `open_codes`.

Your `/tmp/oc_trap/coded.jsonl` has 3 rows. Running the skill's Step-4 verification:

```
3 rows, 2 with NO codes
uncoded: ['2c0f3fceb182424b8d1870f1e55dd370', '9d2c84fb4a7943008c77d460e4eecdcf']
```

Looking at the rows:

| trace_id (short) | prompt | `open_codes` | `memo` |
|---|---|---|---|
| e68552dd… | Design a rate limiter | `["depth-under-plan"]` ✅ | "good synthesis, benign miss" |
| 2c0f3fce… | Refactor the auth module | `[]` ❌ | "depth-under-plan, clarification-instead-of-action, asked for info instead of doing it" |
| 9d2c84fb… | Compare Redis and Memcached | `[]` ❌ | "fabricated-delegation, incomplete-enumeration, tool errors swallowed" |

Only the **first** row was coded correctly. For the other two, you typed your
observations — which *are* codes (`depth-under-plan`, `clarification-instead-of-action`,
`fabricated-delegation`, `incomplete-enumeration`, `tool-error swallowed`) — as a
comma-separated string **into the memo box** instead of pressing **Enter** in the
codes field to commit each one as a chip. So `open_codes` stayed `[]`.

## Why the export looks "missing" rather than erroring

The exporter (`scripts/push_open_codes_to_langfuse.py`) does **not** drop these rows,
which is the trap within the trap. Two relevant lines:

```python
# line 45 — keeps any row that has codes OR a non-empty memo
coded = [r for r in rows if r.get("open_codes") or r.get("memo", "").strip()]

# line 59 — falls back to a placeholder when codes are empty
value = ", ".join(codes) if codes else "(memo only)"
```

So for your two miscoded rows the exporter would push a score whose **value is the
literal string `"(memo only)"`**, with your actual observations sitting only in the
free-text `comment`/memo and in `metadata.open_codes` as an empty list `[]`.

That is exactly the symptom you saw: the rows export, but **the codes are missing** —
because as far as the data is concerned, those rows have no codes. Only row 1
(`e68552dd…`) would carry a real code value (`depth-under-plan`). Nothing errors,
nothing warns, which is why it slipped past you.

(Note: the skill text refers to the exporter as `export_coded_to_dataset.py` /
"dataset" surface; the script actually present in this repo is
`push_open_codes_to_langfuse.py`, which pushes per-trace **TEXT scores**. The trap and
the fix are identical either way — empty `open_codes` is empty regardless of surface.)

## How to check (before every push)

Run the skill's Step-4 guard against your file. Use `.venv/bin/python` — this repo
requires Python 3.13:

```bash
.venv/bin/python -c "import json; \
rows=[json.loads(l) for l in open('/tmp/oc_trap/coded.jsonl') if l.strip()]; \
empty=[r['trace_id'] for r in rows if not r.get('open_codes')]; \
print(f'{len(rows)} rows, {len(empty)} with NO codes'); print('uncoded:', empty)"
```

A clean file prints `0 with NO codes`. Yours prints `2`. **Do not push until this
reads 0** (or until you have a deliberate reason for an uncoded row).

## How to fix

The fix is **manual and yours to make** — the skill is explicit that codes are typed by
a human and must never be auto-generated or back-filled by a tool. So:

1. **Re-serve the coder over http** (never `file://`, or Save silently falls back to a
   browser download):
   ```bash
   python scripts/serve_open_coder.py          # serves http://localhost:3117/coder.html
   ```
2. Reopen the page. The server restores prior codes on `GET /load`, so row 1 keeps its
   chip and you'll see the two uncoded cards.
3. For trace `2c0f3fce…` and `9d2c84fb…`: read each comma-item you'd parked in the memo,
   type it into the **codes** field, and press **Enter** so each becomes a chip. Your own
   notes already name the codes:
   - `2c0f3fce…` → `depth-under-plan`, `clarification-instead-of-action`
   - `9d2c84fb…` → `fabricated-delegation`, `incomplete-enumeration`, `tool-error-unhandled`

   (Confirm these against the trace before committing — open coding is human judgment,
   not transcription. Keep the prose in the memo if it adds nuance; just make sure the
   short behavioral codes also live as chips.)
4. **Save to disk** to rewrite the JSONL.
5. Re-run the Step-4 verification above and confirm it prints `0 with NO codes`.
6. **Only then** push (dry-run first, then `--write`).

## Why not just let the export proceed

Pushing now would land two rows whose code value is `"(memo only)"`. The whole point of
open coding is the short behavioral code that later rolls up into an axial taxonomy and a
judge rubric; a `(memo only)` placeholder carries nothing into that rollup. You'd have
"pushed" the batch while losing 2/3 of the actual signal. Fix the chips first.
