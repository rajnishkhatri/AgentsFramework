# Diagnosis: empty `open_codes` (the Step-4 memo-vs-chip trap)

## What went wrong

Your codes are missing from the export because they were typed into the **memo**
box, not committed as **code chips**. In the HTML coder, a code only lands in the
`open_codes` array if you press **Enter** to turn it into a chip. Typing a
comma-separated list into the memo field leaves `open_codes` empty — the exporter
then has nothing to copy into the Langfuse dataset, which is why "the codes seem to
be missing."

This is the single most common open-coding session failure, called out explicitly
in the skill's Step 4 ("The trap"). It is a UI-mechanics mistake, not a data-loss
or save bug — your JSONL saved fine; it just has prose where codes should be.

## Evidence (from your file `/tmp/oc_trap/coded.jsonl`)

3 rows total, **2 with NO codes**:

| trace_id (short) | prompt | `open_codes` | memo |
|---|---|---|---|
| `e68552dd…` | Design a rate limiter… | `["depth-under-plan"]` ✅ | "good synthesis, benign miss" |
| `2c0f3fce…` | Refactor the auth module. | `[]` ❌ | "depth-under-plan, clarification-instead-of-action, asked for info instead of doing it" |
| `9d2c84fb…` | Compare Redis and Memcached… | `[]` ❌ | "fabricated-delegation, incomplete-enumeration, tool errors swallowed" |

The tell is obvious in rows 2 and 3: the memo contains what are clearly intended to
be **codes** (`depth-under-plan`, `clarification-instead-of-action`,
`fabricated-delegation`, `incomplete-enumeration`, `tool-errors-swallowed`) sitting
as a comma-list in prose, while `open_codes` is `[]`. Row 1 was done correctly — one
chip committed, memo used only for nuance — which is the pattern the other two should
match.

## How to check (the skill's Step-4 verification command)

Run before every export:

```bash
WORK=/tmp/oc_trap
.venv/bin/python -c "import json,sys; \
rows=[json.loads(l) for l in open('$WORK/coded.jsonl') if l.strip()]; \
empty=[r['trace_id'] for r in rows if not r.get('open_codes')]; \
print(f'{len(rows)} rows, {len(empty)} with NO codes'); print('uncoded:', empty)"
```

Output on your file:

```
3 rows, 2 with NO codes
uncoded: ['2c0f3fceb182424b8d1870f1e55dd370', '9d2c84fb4a7943008c77d460e4eecdcf']
```

The exporter's default **dry run** prints the same `(N with NO codes)` count plus a
warning banner (`export_coded_to_dataset.py` lines 84–88), so you'd catch this even
if you skipped the one-liner. Either way: fix it before `--write`.

## How to fix (you must re-enter the codes — I did NOT do it for you)

Open coding is a human-judgment step; the skill forbids auto-generating or
back-filling first-pass codes (Cardinal Rule 2, "Human codes first"), so I did not
move your memo text into `open_codes`. The memo strings look like the right codes,
but turning prose into committed codes is your call, not the tool's. To fix:

1. Re-serve the coder against this work dir:
   ```bash
   python docs/skills/agentsframework-open-coding/scripts/serve_open_coder.py --dir /tmp/oc_trap
   ```
   Open `http://localhost:3117/coder.html`. The server serves your saved JSONL at
   `/load`, so your existing memos reappear.
2. For the two uncoded cards (`2c0f3fce…`, `9d2c84fb…`), type each intended code
   into the **code** input and press **Enter** so it becomes a chip. Move the
   code-like tokens out of the memo; keep the memo for genuine nuance only.
3. **Save to disk** (writes the JSONL via `POST /save`; do not open the HTML as
   `file://` or the save silently falls back to a `~/Downloads` copy).
4. Re-run the Step-4 verification one-liner — it should report `0 with NO codes`.
5. Only then export: dry run first, then `--write`.

## Note on the export attempt

I did not run the exporter (even the default dry run): in this environment the
script import path triggers the Langfuse client, and you asked me not to push to
Langfuse, so the run was blocked. I confirmed the banner behavior by reading the
source instead (lines 84–88, dry-run default at line 126). Once you've re-committed
the codes and verified `0 with NO codes`, the dry run is safe to run yourself, and
`--write` pushes to the dataset.
