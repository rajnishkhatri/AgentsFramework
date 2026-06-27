from typing import Any
from langgraph.checkpoint.base import BaseCheckpointSaver
from services.observability import FrameworkTelemetry


class InstrumentedCheckpointer(BaseCheckpointSaver):
    """Wrap a LangGraph checkpointer so it updates :class:`FrameworkTelemetry`.

    Each ``put`` / ``aput`` increments ``checkpoint_invocations``; each
    ``get`` / ``aget`` that returns a non-None state increments
    ``rollback_invocations`` (LangGraph's interrupt/resume path triggers a
    ``get`` to rebuild state, which is the closest signal to a "rollback"
    that the public API exposes).

    All other attribute access falls through to the wrapped instance, so
    methods like ``list``, ``get_tuple``, and ``setup`` keep working
    transparently.

    Notes:
        * ``put_writes`` / ``aput_writes`` (intermediate channel writes)
          are intentionally NOT counted -- STORY-412 maps a "checkpoint"
          to a full ``put`` call.
    """

    def __init__(self, inner: Any, telemetry: FrameworkTelemetry) -> None:
        # We don't call super().__init__() because we are just a wrapper and
        # don't want to initialize the base class state which we don't use.
        self._inner = inner
        self._telemetry = telemetry

    def put(self, *args: Any, **kwargs: Any) -> Any:
        result = self._inner.put(*args, **kwargs)
        self._telemetry.increment_checkpoint()
        return result

    async def aput(self, *args: Any, **kwargs: Any) -> Any:
        result = await self._inner.aput(*args, **kwargs)
        self._telemetry.increment_checkpoint()
        return result

    def get(self, *args: Any, **kwargs: Any) -> Any:
        result = self._inner.get(*args, **kwargs)
        if result is not None:
            self._telemetry.increment_rollback()
        return result

    async def aget(self, *args: Any, **kwargs: Any) -> Any:
        result = await self._inner.aget(*args, **kwargs)
        if result is not None:
            self._telemetry.increment_rollback()
        return result

    def get_next_version(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate for LangGraph pregel (accessed as ``checkpointer.get_next_version``)."""
        return self._inner.get_next_version(*args, **kwargs)

    def put_writes(self, *args: Any, **kwargs: Any) -> Any:
        return self._inner.put_writes(*args, **kwargs)

    async def aput_writes(self, *args: Any, **kwargs: Any) -> Any:
        return await self._inner.aput_writes(*args, **kwargs)

    def get_tuple(self, *args: Any, **kwargs: Any) -> Any:
        return self._inner.get_tuple(*args, **kwargs)

    async def aget_tuple(self, *args: Any, **kwargs: Any) -> Any:
        return await self._inner.aget_tuple(*args, **kwargs)

    def list(self, *args: Any, **kwargs: Any) -> Any:
        return self._inner.list(*args, **kwargs)

    async def alist(self, *args: Any, **kwargs: Any) -> Any:
        return await self._inner.alist(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
