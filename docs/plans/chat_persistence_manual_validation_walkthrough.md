# Chat persistence — manual UI validation walkthrough

**You drive the UI; I cross-check Langfuse traces + the Cloud SQL rows for each step.**

After the 2026-06-19 fix (threads table migrated, traffic on durable rev
`00061-laz`), this proves durable persistence works in the real browser. For
each case below: do the steps, paste me **(a)** what you observed and **(b)** the
trace id from the chip. I'll pull the matching Langfuse trace + DB row and
confirm.

---

## Setup (do once)

**URL — use the `?eval=` form so the trace chip shows:**

```
https://memui---agent-frontend-w65nrxwkiq-uc.a.run.app/?eval=manual-validate
```

> Why this host: WorkOS sign-in redirects back to the `memui---…` host. It
> serves the **same** revision (`00061-laz`) + the **same** Cloud SQL DB as the
> bare prod URL, so persistence behaves identically — it's just the auth-stable
> entry point. `?eval=manual-validate` turns on eval mode → each turn shows a
> copyable **`trace <id>`** chip (and opens the recalled-memories disclosure).

Sign in with your normal account. You should land on the chat with a composer at
the bottom and a left panel with **+ New chat** and **Recents**.

**What to paste me after each case:**
1. A one-line observation ("chat appeared in Recents" / "Recents was empty").
2. The **trace id** from the chip under the assistant's answer (click it → "copied").

---

## Case 1 — A new chat is saved and appears in Recents

**This is the exact thing you reported broken.**

1. Click **+ New chat** (clean slate).
2. In the composer, send:
   > `Validation case 1: what is the capital of France?`
3. Wait for the assistant's full answer to finish streaming.
4. **Look at the left "Recents" list.** A row should appear with a title derived
   from your message (e.g. *"Validation case 1: what is the…"*).
5. Click the **`trace …`** chip under the answer → it copies the trace id.

**Paste me:** ✅/❌ did the Recents row appear? + the trace id.

**I will confirm:** the Langfuse trace for that id (run completed, no errors) **and**
a matching row now exists in the Cloud SQL `threads` table.

---

## Case 2 — The chat survives a full page reload (durability)

Right after Case 1 (don't start a new chat):

1. **Hard-reload the page** (Cmd-R).
2. After it loads, **look at Recents** — the Case 1 row should **still be there**.
3. Click that Recents row.
4. The transcript should **replay**: your "capital of France" question and the
   assistant's answer both reappear.

**Paste me:** ✅/❌ still in Recents after reload? ✅/❌ did the transcript replay?

**I will confirm:** the row persisted in Cloud SQL across the reload (this is what
distinguishes the durable DB from the old per-instance in-memory store that lost
it), and whether the **messages** were persisted (the append path) — see note
below.

---

## Case 3 — A second chat doesn't clobber the first (the "+ then back" path)

This reproduces your precise sequence: add a chat, hit **+**, expect the previous
one to still be listed.

1. With Case 1's chat on screen, click **+ New chat**.
2. Send a *different* message:
   > `Validation case 3: list three primary colors.`
3. Wait for the answer.
4. **Look at Recents** — you should now see **TWO** rows: Case 3 (newest, top) and
   Case 1 (below it).
5. Click the **Case 1** row → its "capital of France" transcript should load back.

**Paste me:** ✅/❌ both rows present? ✅/❌ clicking the old one restored it? + the
Case 3 trace id.

**I will confirm:** two distinct thread rows in Cloud SQL (different `thread_id`s,
correct titles) and both traces in Langfuse.

---

## Case 4 — Multi-turn in one chat (append path, the one gap from the probe)

The automated probe proved chat *creation* but not per-turn message *append*.
This case exercises it directly.

1. Click **+ New chat**.
2. Send:
   > `Validation case 4 turn 1: remember the number 4242.`
3. Wait for the answer, then **in the same chat** send a second message:
   > `Validation case 4 turn 2: what number did I just give you?`
4. Wait for the answer.
5. **Reload the page**, click this chat in Recents.
6. The replayed transcript should show **all four messages** (two of yours, two
   assistant replies) in order — not just the first turn.

**Paste me:** ✅/❌ did all four messages replay after reload? + both trace ids.

**I will confirm:** the `threads` row's `messages` JSONB has 4 entries (proves the
`POST /api/threads/{id}/messages` append landed each turn, closing the `msgs=0`
question from the probe).

---

## Case 5 — (Optional, Phase B) Recalled-memories disclosure + reject

Only if Cases 1–4 pass and you want to validate the memory half. Because the URL
is in eval mode, a turn that recalls memory shows a **"N memories recalled here"**
disclosure with a **Reject** button per item.

1. Click **+ New chat**.
2. Send something that should trigger recall of a stored memory, e.g.:
   > `Validation case 5: what do you remember about my preferences?`
3. If a disclosure appears, note **how many** memories it lists, then click
   **Reject** on one of them.
4. Click **+ New chat** and ask the same question again.
5. The previously-rejected memory should **no longer** appear in the new
   disclosure (soft-suppress is global).

**Paste me:** the recalled count before/after reject + both trace ids.

**I will confirm:** from the Langfuse `MEMORY_RECALLED` carrier — the rejected
key's absence from the second run's recall set (the C4 "reject-not-excluded"
gate).

---

## Reference — what I check per trace

| You give me | I pull | Pass looks like |
|---|---|---|
| trace id from chip | Langfuse trace by id | run.started → steps → task.completed, no error step |
| (case 1–4) | Cloud SQL `threads` row | row exists, correct title, survives across your reload |
| (case 4) | `threads.messages` JSONB | length grows by 2 per turn (append landed) |
| (case 5) | `MEMORY_RECALLED` carrier `details.keys` | rejected key gone from run-2's key set |

**Known caveat:** the WorkOS callback is registered on the `memui---…` host, so
sign in there (not the bare prod URL). Both hosts are the same revision + DB.
