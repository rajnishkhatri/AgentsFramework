# Dev Workspace Restart Guide

Full stop-and-restart procedure for local development.

```
Workspace root:  ~/Documents/AgentsFramework/agent
Processes:       2  (middleware + frontend)
Ports:           8000 (middleware)  ·  3000 (frontend)
```

---

## 1 — Stop all listeners

```bash
cd ~/Documents/AgentsFramework/agent

for p in 3000 8000; do
  lsof -tiTCP:$p -sTCP:LISTEN | xargs kill 2>/dev/null
done
```

Verify both ports are free:

```bash
lsof -nP -iTCP:3000 -sTCP:LISTEN   # should return nothing
lsof -nP -iTCP:8000 -sTCP:LISTEN   # should return nothing
```

## 2 — Pull latest changes (optional)

Skip this step if you only want to pick up local edits.

```bash
cd ~/Documents/AgentsFramework/agent
git pull
```

If `pyproject.toml` changed:

```bash
pip install -e ".[dev]"
```

If `frontend/pnpm-lock.yaml` changed:

```bash
cd ~/Documents/AgentsFramework/agent/frontend
pnpm install
```

## 3 — Start the middleware (Terminal 1)

```bash
cd ~/Documents/AgentsFramework/agent
python -m middleware
```

- Loads `.env` from the repo root via `dotenv`.
- Builds the LangGraph ReAct graph and starts uvicorn on `0.0.0.0:8000`.
- If port 8000 is busy it auto-increments up to +63 (disable with `PORT_STRICT=1`).
- Override the port: `PORT=9000 python -m middleware`.

Wait for the log line:

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

## 4 — Start the frontend (Terminal 2)

```bash
cd ~/Documents/AgentsFramework/agent/frontend
pnpm dev
```

Wait for:

```
✓ Ready in ...ms
```

Then open http://localhost:3000.

## 5 — Verify

```bash
curl http://localhost:8000/healthz        # middleware health — expect 200
open http://localhost:3000                 # frontend UI
```

---

## Quick full-restart one-liner

Paste from the repo root to kill, wait, and restart both processes:

```bash
cd ~/Documents/AgentsFramework/agent && \
for p in 3000 8000; do lsof -tiTCP:$p -sTCP:LISTEN | xargs kill 2>/dev/null; done && \
sleep 1 && \
python -m middleware &
cd ~/Documents/AgentsFramework/agent/frontend && pnpm dev
```

---

## When you need to restart vs. when you don't

| Change | Restart needed? |
|---|---|
| `.tsx` / `.ts` source files | No — Next.js hot-reloads |
| `.env.local`, `next.config.*`, `tailwind.config.*` | Yes — restart **frontend** |
| Any Python file | Yes — restart **middleware** (no hot-reload) |
| `pyproject.toml` dependencies | `pip install -e ".[dev]"` then restart middleware |
| `pnpm-lock.yaml` dependencies | `pnpm install` then restart frontend |

## Port reference

| Process | Default port | Override |
|---|---|---|
| Middleware (FastAPI + LangGraph) | 8000 | `PORT=<N> python -m middleware` |
| Frontend (Next.js) | 3000 | `pnpm dev --port <N>` |
| Mock middleware (E2E tests only) | 8765 | `MOCK_MIDDLEWARE_PORT=<N>` |

## Environment

The middleware loads `~/Documents/AgentsFramework/agent/.env` on startup.
See `.env.example` for all expected variables (API keys, feature flags, architecture profile).
The frontend reads `frontend/.env.local` (not committed).
