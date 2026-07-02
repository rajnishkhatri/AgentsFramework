# Deeper compaction levers (lossy — confirm with the user first)

Re-hooking (the main lever in SKILL.md) is lossless and usually enough. Reach for these
only when re-hooking alone can't get MEMORY.md under budget. **Both remove or merge
information, so confirm with the user before applying either** — present them with
`AskUserQuestion` and let the user choose.

## Lever A — Prune resolved/superseded memories

The analyzer reports `resolved_candidates`: index entries that self-describe as `RESOLVED`,
`SUPERSEDED`, `DEPRECATED`, or point at a successor. A memory that records a fixed bug or a
decision that's been overtaken is rarely worth carrying in the always-loaded index forever
— the git history of the codebase already retains the actual fix.

To prune one safely:
1. Confirm it's genuinely closed (read the topic file, not just the hook — a hook saying
   "RESOLVED" can still carry a live "remaining piece").
2. Check whether other memories `[[wikilink]]` to it. If they do, either keep it or update
   those links so you don't create dangling cross-references.
3. Delete **both** the topic `*.md` file and its `MEMORY.md` index line.
4. Note the deletion in your final report — this is information leaving the system.

Conservative default: prune only entries that are fully closed AND not referenced by any
other memory. When in doubt, keep it and rely on re-hooking.

## Lever B — Consolidate topic clusters

Several index entries are often really one topic fragmented across many sessions (e.g. a
multi-phase feature with eight entries). Merging a cluster shrinks the index AND sharpens
recall — one good pointer beats eight competing ones.

To consolidate a cluster:
1. Identify the cluster (entries sharing a prefix/theme — the analyzer's entry list plus
   the titles make these obvious).
2. Create one merged topic file that preserves the load-bearing facts from each member
   (don't just concatenate — synthesize; keep dates, decisions, and gotchas, drop
   redundancy). Carry forward `[[wikilink]]` targets that point into the cluster.
3. Replace the cluster's many index lines with one hooked line pointing at the merged file.
4. Delete the now-merged source topic files (their content lives in the merged file).
5. Update any external `[[wikilinks]]` that referenced the old files.

There is an `anthropic-skills:consolidate-memory` skill that specializes in this merge step
— prefer it for the synthesis if it's available, then return here to fix up the index.

Consolidation is the highest-effort, highest-judgment lever. It's worth it when a project
has accreted many small entries on one workstream, but it's never required just to hit a
size target — re-hook + a little pruning almost always suffices.

## After any deeper lever

Always re-run the verifier:

```bash
python <skill-dir>/scripts/verify_memory.py [MEMORY_DIR] --target-kb 12
```

and confirm `no_dangling_links` and `no_orphan_topic_files` still pass — these two catch
the mistakes pruning and merging are most likely to introduce.
