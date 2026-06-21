"""C1 Phase 7 — context-compaction dual carrier unit tests (design §7.2).

The Recording-pillar carrier for a message-history fold. Lives in
``services/governance/context_compaction_carrier.py`` (clone-shape of
``memory_consolidation_carrier.py``). Counts + hash + flags ONLY —
**never** dropped text or constraint strings. The ``_CompactionOutcome``
Protocol is what makes "content-free" structural, not a convention.

These tests cover the carrier in isolation:

- ``EventType.CONTEXT_COMPACTED`` member + observation-map entry (the
  enrichment path; the drift-guard `default_spec()` is NOT touched).
- ``emit_compaction_carrier`` signature + emitted ``TraceEvent`` shape:
  ``event_type``, ``workflow_id``, ``step``, ``details`` (decision_id +
  counts + hash + flags).
- Content-free guard: the carrier rejects any field that isn't a scalar /
  hash / bool — the Protocol structurally forbids strings of dropped text
  or constraints, but a positive guard test pins it.
- ``constraint_floor_hash`` is SHA-256 of the rendered floor block (so an
  in-process auditor with the floor strings can re-derive it; the trace
  reader cannot, per §7.3).
- ``black_box`` ``integrity_hash`` chain still validates after a fold
  carrier lands (the chained recorder absorbs the new event without break).

L1, no langfuse / langchain imports, <2s.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from services.governance.black_box import (
    BlackBoxRecorder,
    EventType,
    TraceEvent,
)


# ════════════════════════════════════════════════════════════════════════════
# Part A — EventType enum + observation-map entry.
# ════════════════════════════════════════════════════════════════════════════


class TestEventTypeMember:
    def test_context_compacted_member_exists(self) -> None:
        # The enum value MUST be the stable string the observation map joins on.
        assert EventType.CONTEXT_COMPACTED.value == "context_compacted"

    def test_observation_map_carries_context_compacted(self) -> None:
        """The relay sidecar exports unknown event types as unnamed spans;
        this map entry is what gives the curated trace observation a name
        readable in Langfuse (design §7.1)."""
        from services.governance.black_box_publisher import (
            _EVENT_TYPE_TO_OBSERVATION,
        )

        assert EventType.CONTEXT_COMPACTED in _EVENT_TYPE_TO_OBSERVATION
        obs_type, obs_name = _EVENT_TYPE_TO_OBSERVATION[
            EventType.CONTEXT_COMPACTED
        ]
        assert obs_type == "span"
        assert obs_name == "context.compacted"


# ════════════════════════════════════════════════════════════════════════════
# Part B — emit_compaction_carrier signature + TraceEvent shape.
# ════════════════════════════════════════════════════════════════════════════


class _FakeOutcome:
    """The minimal duck satisfying the ``_CompactionOutcome`` Protocol —
    counts + hash + flags ONLY (no strings)."""

    def __init__(
        self,
        *,
        tokens_before: int = 1200,
        tokens_after: int = 400,
        turns_folded: int = 8,
        observations_cleared: int = 5,
        keep_last_k: int = 2,
        pinned_kept: int = 2,
        must_not_count: int = 2,
        constraint_floor_hash: str = "0" * 64,
        floor_reinjected: bool = False,
        floor_exceeded: bool = False,
        context_exhausted: bool = False,
        fold_committed: bool = True,
    ) -> None:
        self.tokens_before = tokens_before
        self.tokens_after = tokens_after
        self.turns_folded = turns_folded
        self.observations_cleared = observations_cleared
        self.keep_last_k = keep_last_k
        self.pinned_kept = pinned_kept
        self.must_not_count = must_not_count
        self.constraint_floor_hash = constraint_floor_hash
        self.floor_reinjected = floor_reinjected
        self.floor_exceeded = floor_exceeded
        self.context_exhausted = context_exhausted
        self.fold_committed = fold_committed


def _fresh_recorder(tmp_path: Path) -> BlackBoxRecorder:
    return BlackBoxRecorder(storage_dir=tmp_path / "bb")


class TestEmitCompactionCarrier:
    def test_emit_records_context_compacted_event(
        self, tmp_path: Path
    ) -> None:
        """Calling the emitter lands exactly one ``CONTEXT_COMPACTED`` event
        on the recorder, with workflow_id + step + details propagated."""
        from services.governance.context_compaction_carrier import (
            emit_compaction_carrier,
        )

        recorder = _fresh_recorder(tmp_path)
        emit_compaction_carrier(
            recorder,
            workflow_id="wf-c1-7",
            step=10,
            decision_id="dec-abc-123",
            outcome=_FakeOutcome(),
        )
        # The recorder's JSONL is the source of truth.
        path = tmp_path / "bb" / "wf-c1-7" / "trace.jsonl"
        assert path.exists(), f"recorder JSONL missing: {path}"
        events = [json.loads(line) for line in path.read_text().splitlines()]
        compacted = [
            e for e in events if e["event_type"] == "context_compacted"
        ]
        assert len(compacted) == 1, (
            f"expected exactly one context_compacted event; got "
            f"{len(compacted)}: {events!r}"
        )
        ev = compacted[0]
        assert ev["workflow_id"] == "wf-c1-7"
        assert ev["step"] == 10

    def test_details_carry_decision_id_join_key(self, tmp_path: Path) -> None:
        """The Recording↔Reasoning join key (§7.0) MUST land in details."""
        from services.governance.context_compaction_carrier import (
            emit_compaction_carrier,
        )

        recorder = _fresh_recorder(tmp_path)
        emit_compaction_carrier(
            recorder,
            workflow_id="wf-j",
            step=3,
            decision_id="dec-join-99",
            outcome=_FakeOutcome(),
        )
        events = [
            json.loads(line)
            for line in (tmp_path / "bb" / "wf-j" / "trace.jsonl")
            .read_text()
            .splitlines()
        ]
        ev = next(e for e in events if e["event_type"] == "context_compacted")
        assert ev["details"]["decision_id"] == "dec-join-99"

    def test_details_carry_counts_hash_flags(self, tmp_path: Path) -> None:
        """The exact shape from design §7.2 — counts, the floor hash, and
        the §5.3/§5.4 flags."""
        from services.governance.context_compaction_carrier import (
            emit_compaction_carrier,
        )

        recorder = _fresh_recorder(tmp_path)
        outcome = _FakeOutcome(
            tokens_before=1500,
            tokens_after=350,
            turns_folded=12,
            observations_cleared=7,
            keep_last_k=2,
            pinned_kept=3,
            must_not_count=2,
            constraint_floor_hash="abc" + "0" * 61,
            floor_reinjected=True,
            floor_exceeded=False,
            context_exhausted=False,
        )
        emit_compaction_carrier(
            recorder,
            workflow_id="wf-d",
            step=11,
            decision_id="dec-d",
            outcome=outcome,
        )
        events = [
            json.loads(line)
            for line in (tmp_path / "bb" / "wf-d" / "trace.jsonl")
            .read_text()
            .splitlines()
        ]
        details = next(
            e for e in events if e["event_type"] == "context_compacted"
        )["details"]

        # Counts
        assert details["tokens_before"] == 1500
        assert details["tokens_after"] == 350
        assert details["turns_folded"] == 12
        assert details["observations_cleared"] == 7
        assert details["keep_last_k"] == 2
        assert details["pinned_kept"] == 3
        assert details["must_not_count"] == 2
        # Hash (tamper-evidence, §7.3)
        assert details["constraint_floor_hash"] == "abc" + "0" * 61
        # Flags
        assert details["floor_reinjected"] is True
        assert details["floor_exceeded"] is False
        assert details["context_exhausted"] is False

    def test_details_carry_fold_committed_flag(self, tmp_path: Path) -> None:
        """Fix 3 — the carrier reports whether the fold actually COMMITTED.

        On a declined fold (``floor_exceeded=True``) the producer reports
        ``tokens_after == tokens_before``, which reads as "no compression".
        ``fold_committed`` disambiguates "no compression because declined"
        from "no compression because no-op". Bool, so it stays content-free.
        """
        from services.governance.context_compaction_carrier import (
            emit_compaction_carrier,
        )

        recorder = _fresh_recorder(tmp_path)
        # A declined fold: floor exceeded, NOT committed.
        emit_compaction_carrier(
            recorder,
            workflow_id="wf-fc",
            step=2,
            decision_id="dec-fc",
            outcome=_FakeOutcome(
                floor_exceeded=True,
                fold_committed=False,
                tokens_before=900,
                tokens_after=900,  # no compression — but BECAUSE declined
            ),
        )
        events = [
            json.loads(line)
            for line in (tmp_path / "bb" / "wf-fc" / "trace.jsonl")
            .read_text()
            .splitlines()
        ]
        details = next(
            e for e in events if e["event_type"] == "context_compacted"
        )["details"]
        assert "fold_committed" in details, (
            "carrier details missing the fold_committed flag (Fix 3)"
        )
        assert details["fold_committed"] is False
        # The disambiguation is meaningful: tokens_after==tokens_before AND
        # fold_committed is False ⇒ "no compression because declined".
        assert details["tokens_after"] == details["tokens_before"]


# ════════════════════════════════════════════════════════════════════════════
# Part C — content-free invariant (the governance privacy boundary).
# ════════════════════════════════════════════════════════════════════════════


class TestContentFreeInvariant:
    def test_details_carry_no_string_dropped_text(self, tmp_path: Path) -> None:
        """The Protocol exposes only scalars/hash/bools — emitting an
        outcome whose hash is the SHA of a sensitive string must NEVER
        surface that string in the details payload."""
        from services.governance.context_compaction_carrier import (
            emit_compaction_carrier,
        )

        secret = "DELETE production_secrets_table"
        outcome = _FakeOutcome(
            constraint_floor_hash=hashlib.sha256(secret.encode()).hexdigest()
        )
        recorder = _fresh_recorder(tmp_path)
        emit_compaction_carrier(
            recorder,
            workflow_id="wf-cf",
            step=1,
            decision_id="dec-cf",
            outcome=outcome,
        )
        raw_jsonl = (tmp_path / "bb" / "wf-cf" / "trace.jsonl").read_text()
        # The secret must NOT appear anywhere in the carrier wire
        # (substring guard, mirrors memory-carrier content-free tests).
        assert secret not in raw_jsonl, (
            "content-free invariant breached — a sensitive constraint "
            "string leaked into the carrier wire"
        )
        # And the hash IS there (positive proof the test fired on the right path).
        assert hashlib.sha256(secret.encode()).hexdigest() in raw_jsonl

    def test_protocol_structurally_forbids_string_fields(self) -> None:
        """The Protocol class (the structural type) lists only scalar/hash/
        bool annotations — an outcome with a stray ``dropped_text`` attribute
        is fine to *pass* (Protocols are structural), but the carrier must
        not pull that attribute through ``details``. Verify by introspecting
        the Protocol's annotations."""
        from services.governance.context_compaction_carrier import (
            _CompactionOutcome,
        )

        # Every annotation MUST be one of {int, str (hash), bool}.
        # str is allowed ONLY for the hash field (a hex digest, not free
        # text). Strings for anything else would be a content-bearing leak.
        annotations = _CompactionOutcome.__annotations__
        for name, annotation in annotations.items():
            ann_str = (
                annotation.__name__
                if hasattr(annotation, "__name__")
                else str(annotation)
            )
            if name == "constraint_floor_hash":
                assert ann_str == "str", (
                    f"hash field has unexpected annotation: {ann_str}"
                )
                continue
            assert ann_str in {"int", "bool"}, (
                f"Protocol field {name!r} is annotated {ann_str!r} — only "
                "int/bool/(hash:str) are allowed; everything else risks "
                "leaking content onto the carrier wire"
            )


# ════════════════════════════════════════════════════════════════════════════
# Part D — black_box integrity_hash chain validates after the carrier lands.
# ════════════════════════════════════════════════════════════════════════════


class TestIntegrityChain:
    def test_chain_advances_after_carrier(self, tmp_path: Path) -> None:
        """The chained recorder MUST treat the new event like any other:
        record before, record carrier, record after — the integrity_hash
        of each subsequent event references the prior. This pins the §7.3
        tamper-evidence model: the carrier is in the chain, so tampering
        with it breaks the next event's hash."""
        from services.governance.context_compaction_carrier import (
            emit_compaction_carrier,
        )

        from datetime import UTC, datetime as _dt

        recorder = _fresh_recorder(tmp_path)
        # Record one prior event so we have a non-trivial chain head.
        recorder.record(
            TraceEvent(
                event_id="pre-1",
                workflow_id="wf-chain",
                event_type=EventType.STEP_EXECUTED,
                timestamp=_dt.now(UTC),
                step=0,
                details={},
            )
        )
        emit_compaction_carrier(
            recorder,
            workflow_id="wf-chain",
            step=1,
            decision_id="dec-chain",
            outcome=_FakeOutcome(),
        )
        recorder.record(
            TraceEvent(
                event_id="post-1",
                workflow_id="wf-chain",
                event_type=EventType.STEP_EXECUTED,
                timestamp=_dt.now(UTC),
                step=2,
                details={},
            )
        )
        events = [
            json.loads(line)
            for line in (tmp_path / "bb" / "wf-chain" / "trace.jsonl")
            .read_text()
            .splitlines()
        ]
        # All three events were stamped, and each subsequent integrity_hash
        # is non-empty (the chained recorder filled it in at record time).
        assert len(events) == 3
        assert all(e.get("integrity_hash") for e in events)
        # The carrier's hash MUST differ from the preceding event's hash —
        # chained means each event's hash depends on the prior.
        assert events[0]["integrity_hash"] != events[1]["integrity_hash"]
        assert events[1]["integrity_hash"] != events[2]["integrity_hash"]
