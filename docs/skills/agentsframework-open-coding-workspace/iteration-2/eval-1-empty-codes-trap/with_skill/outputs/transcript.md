# Transcript — eval-1 empty-codes trap (with skill)

## Skill files read

- `docs/skills/agentsframework-open-coding/SKILL.md` — full skill; Step 4
  ("Verify the JSONL — the trap") is the directly relevant section.
- `docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py`
  — read (grep) to confirm the dry-run `(N with NO codes)` banner, NOT executed.

## Commands run

### 1. Read + sanity-check the coded file
```bash
ls -la /tmp/oc_trap/ && wc -l /tmp/oc_trap/coded.jsonl
```
Result: one file, `coded.jsonl`, 3 lines, 588 bytes.

Read of `/tmp/oc_trap/coded.jsonl` showed:
- row 1 `e68552dd…`: `open_codes` = `["depth-under-plan"]` (correct)
- row 2 `2c0f3fce…`: `open_codes` = `[]`, codes sitting in memo prose
- row 3 `9d2c84fb…`: `open_codes` = `[]`, codes sitting in memo prose

### 2. Step-4 verification one-liner (the skill's own command)
```bash
WORK=/tmp/oc_trap
.venv/bin/python -c "import json,sys; \
rows=[json.loads(l) for l in open('$WORK/coded.jsonl') if l.strip()]; \
empty=[r['trace_id'] for r in rows if not r.get('open_codes')]; \
print(f'{len(rows)} rows, {len(empty)} with NO codes'); print('uncoded:', empty)"
```
Output:
```
3 rows, 2 with NO codes
uncoded: ['2c0f3fceb182424b8d1870f1e55dd370', '9d2c84fb4a7943008c77d460e4eecdcf']
```

### 3. Exporter dry run — attempted, intentionally NOT completed
```bash
EXPORT=docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py
.venv/bin/python "$EXPORT" --dataset oc-trap-eval1 --coded /tmp/oc_trap/coded.jsonl
```
Blocked by the sandbox classifier (script imports the Langfuse client; user
forbade pushing to Langfuse). Did NOT retry / work around it.

### 4. Confirm the banner by reading source instead of running it
```bash
grep -n "NO codes\|open_codes\|dry\|--write\|WARN\|warning" \
  docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py
```
Confirmed:
- line 84–85: counts `n_uncoded` and prints `({n_uncoded} with NO codes)`
- line 87–88: warning banner about codes only persisting if Enter-committed
- line 126: `DRY RUN — nothing written. Re-run with --write.` (write is opt-in)

This matches SKILL.md Step 4's claim that the dry run surfaces the same count.

## Scripts used
- Skill Step-4 verification one-liner (ran, gave the diagnosis).
- `export_coded_to_dataset.py` — inspected only; never executed (no push).

## What I did NOT do
- Did NOT push to Langfuse (no `--write`, dry run not completed).
- Did NOT invent or back-fill any codes into `open_codes` — left the user to
  re-commit them in the coder (Cardinal Rule 2: human codes first).

## Conclusion
The Step-4 trap: 2/3 rows have empty `open_codes` because the codes were typed
into the memo field instead of Enter-committed as chips. Fix = reopen the coder
(`serve_open_coder.py --dir /tmp/oc_trap`), Enter-commit the codes on the two
uncoded cards, Save, re-run the verification one-liner until `0 with NO codes`,
then export.
