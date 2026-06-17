"""MemoryAutoCaptureService: post-run typed memory background seam (Phase 2).

Horizontal service (AGENTS.md): framework-clean (no ``langgraph`` /
``langchain``), constructor-injected with its collaborators (the typed
``MemoryExtractor``, the ``LongTermMemoryService``, the enable flag). It is the
*background* half of Phase 2 — it runs OUTSIDE the graph hot path, after a run
finishes, so the extractor's LLM call never sits in the user-visible latency
path.

Two behaviors, gated by ``write_back_enabled``:
- **Shadow (default, ``MEMORY_AUTOCAPTURE_ENABLED`` OFF):** run the extractor,
  emit ONE ``MEMORY_STORED`` carrier per PROPOSED item (``{user_id, key, type,
  salience}`` — never content), and store NOTHING. The trace carries the
  proposal so the grounded-theory eval workstream has shadow traces to code;
  production state is untouched.
- **Write-back (``MEMORY_AUTOCAPTURE_ENABLED`` ON — only after the enable-policy
  clears):** additionally ``store`` each item with ``metadata={"type": ...}``
  so typed recall's filter can find it.

Privacy invariant: ``content`` NEVER reaches a carrier or a log line — only
``{user_id, key, type, salience}``. Cross-user-leak guard: the only ``user_id``
used is the run's subject; ``""``/``"anonymous"`` is normalized to no-subject
and short-circuits (no extraction, no store).

Debounce: per-thread. ``schedule(...)`` coalesces a burst of completions for
the same thread into a single extraction on a pause (bounds LLM cost — mirrors
LangMem ``create_memory_store_manager``). ``capture(...)`` is the immediate,
testable one-shot the scheduler ultimately calls; the runtime adapter can call
either.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Protocol, Sequence

from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent

if TYPE_CHECKING:
    from services.long_term_memory import LongTermMemoryService


class _ExtractorPort(Protocol):
    """The slice of ``components.MemoryExtractor`` this service depends on.

    Declared here (not imported from ``components``) so the service stays
    layer-clean: ``services/`` must not import ``components/`` (I-5), even
    under ``TYPE_CHECKING``. The concrete extractor is injected at the
    composition root and satisfies this structurally.
    """

    async def extract(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        existing_profile: Iterable[str] | None = None,
    ) -> Any: ...

logger = logging.getLogger("services.memory_autocapture")

__all__ = ["MemoryAutoCaptureService", "CaptureOutcome"]

# Subjects that must NOT pool memory across users (cross-user-leak guard).
# Mirrors components.memory_context._ANONYMOUS_SUBJECT — kept local so this
# service does not reach up into components for a constant.
_NON_SUBJECTS = frozenset({"", "anonymous"})


def _subject(user_id: str) -> str:
    normalized = (user_id or "").strip()
    return "" if normalized in _NON_SUBJECTS else normalized


@dataclass(frozen=True)
class CaptureOutcome:
    """What one capture pass did (counts only — never content)."""

    proposed: int = 0
    stored: int = 0
    degraded: bool = False


class MemoryAutoCaptureService:
    def __init__(
        self,
        extractor: _ExtractorPort,
        memory_service: LongTermMemoryService,
        *,
        write_back_enabled: bool = False,
        debounce_seconds: float = 2.0,
        black_box: BlackBoxRecorder | None = None,
    ) -> None:
        self._extractor = extractor
        self._memory = memory_service
        self._write_back = write_back_enabled
        self._debounce_seconds = debounce_seconds
        # Default recorder used when a per-call ``black_box`` is not supplied
        # (the runtime path injects it at the composition root so carriers land
        # in the same workflow trace the graph wrote to). Tests pass it per call.
        self._black_box = black_box
        # Per-thread pending debounce tasks (thread_id -> asyncio.Task).
        self._pending: dict[str, asyncio.Task[None]] = {}

    # ── debounce scheduling ────────────────────────────────────────────

    def schedule(
        self,
        *,
        thread_id: str,
        user_id: str,
        messages: Sequence[Mapping[str, Any]],
        workflow_id: str,
        task_id: str,
        black_box: BlackBoxRecorder | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Debounced enqueue: a new completion for ``thread_id`` cancels the
        prior pending one and reschedules, so a burst coalesces into one
        extraction on a pause. Fire-and-forget — the runtime never awaits it.
        """
        existing = self._pending.get(thread_id)
        if existing is not None and not existing.done():
            existing.cancel()

        async def _runner() -> None:
            try:
                await asyncio.sleep(self._debounce_seconds)
                await self.capture(
                    thread_id=thread_id,
                    user_id=user_id,
                    messages=messages,
                    workflow_id=workflow_id,
                    task_id=task_id,
                    black_box=black_box,
                    config=config,
                )
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - background never raises up
                logger.warning("memory.autocapture background pass failed")
            finally:
                if self._pending.get(thread_id) is asyncio.current_task():
                    self._pending.pop(thread_id, None)

        self._pending[thread_id] = asyncio.ensure_future(_runner())

    async def drain(self) -> None:
        """Await all pending debounce tasks (test/shutdown helper)."""
        pending = [t for t in self._pending.values() if not t.done()]
        for task in pending:
            try:
                await task
            except asyncio.CancelledError:
                pass

    # ── the one-shot capture pass ──────────────────────────────────────

    async def capture(
        self,
        *,
        thread_id: str,
        user_id: str,
        messages: Sequence[Mapping[str, Any]],
        workflow_id: str,
        task_id: str,
        black_box: BlackBoxRecorder | None = None,
        config: dict[str, Any] | None = None,
    ) -> CaptureOutcome:
        """Run the extractor once and emit/store its proposals. Never raises."""
        subject = _subject(user_id)
        if not subject:
            return CaptureOutcome()
        recorder = black_box if black_box is not None else self._black_box
        if recorder is None:
            logger.warning("memory.autocapture skipped: no BlackBoxRecorder")
            return CaptureOutcome()

        existing_profile = self._load_existing_profile(subject)
        try:
            result = await self._extractor.extract(
                messages=messages,
                existing_profile=existing_profile,
            )
        except Exception as exc:  # MemoryExtractionError or transport
            logger.warning(
                "memory.autocapture degraded user_id=%s thread=%s error=%s",
                subject,
                thread_id,
                type(exc).__name__,
            )
            return CaptureOutcome(degraded=True)

        stored = 0
        for item in result.memories:
            store_error = ""
            if self._write_back:
                try:
                    self._memory.store(
                        subject,
                        item.key,
                        {"text": item.content},
                        metadata={"type": item.type, "salience": item.salience},
                    )
                    stored += 1
                except Exception as exc:
                    store_error = type(exc).__name__
                    logger.warning(
                        "memory.autocapture store degraded user_id=%s key=%s "
                        "error=%s",
                        subject,
                        item.key,
                        store_error,
                    )
            self._emit_carrier(
                recorder,
                workflow_id=workflow_id,
                user_id=subject,
                item_key=item.key,
                item_type=item.type,
                salience=item.salience,
                proposed_only=not self._write_back,
                store_error=store_error,
            )

        await self._record_eval(
            config=config,
            user_id=subject,
            task_id=task_id,
            result=result,
            proposed=len(result.memories),
            stored=stored,
        )
        logger.info(
            "memory.autocapture user_id=%s thread=%s proposed=%d stored=%d "
            "write_back=%s",
            subject,
            thread_id,
            len(result.memories),
            stored,
            self._write_back,
        )
        return CaptureOutcome(proposed=len(result.memories), stored=stored)

    # ── helpers ────────────────────────────────────────────────────────

    def _load_existing_profile(self, subject: str) -> set[str]:
        """Best-effort read of already-known semantic facts (ADD-only guard).

        A failed read just means the extractor sees an empty profile — never
        fail the capture over it.
        """
        try:
            records = self._memory.search(
                subject, "", limit=50, mem_type="semantic"
            )
        except Exception:
            return set()
        facts: set[str] = set()
        for record in records:
            text = record.payload.get("text")
            if isinstance(text, str) and text:
                facts.add(text)
        return facts

    def _emit_carrier(
        self,
        black_box: BlackBoxRecorder,
        *,
        workflow_id: str,
        user_id: str,
        item_key: str,
        item_type: str,
        salience: float,
        proposed_only: bool,
        store_error: str,
    ) -> None:
        details: dict[str, Any] = {
            "user_id": user_id,
            "key": item_key,
            "type": item_type,
            "salience": salience,
            # Distinguishes a shadow proposal from a real write in the trace
            # so the audit can tell "would have stored" from "did store".
            "proposed_only": proposed_only,
        }
        if store_error:
            details["error_kind"] = store_error
        black_box.record(
            TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.MEMORY_STORED,
                timestamp=datetime.now(UTC),
                details=details,
            )
        )

    async def _record_eval(
        self,
        *,
        config: dict[str, Any] | None,
        user_id: str,
        task_id: str,
        result: Any,
        proposed: int,
        stored: int,
    ) -> None:
        from services import eval_capture

        cfg = config or {"configurable": {"user_id": user_id, "task_id": task_id}}
        await eval_capture.record(
            target="memory_extract",
            ai_input={"window": "post_run"},
            ai_response={"proposed": proposed, "stored": stored},
            config=cfg,
            model=getattr(result, "model", None),
            tokens_in=getattr(result, "tokens_in", None),
            tokens_out=getattr(result, "tokens_out", None),
            cost_usd=getattr(result, "cost_usd", None),
            latency_ms=getattr(result, "latency_ms", None),
        )
