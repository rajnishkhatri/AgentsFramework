"""L3 Probabilistic (mocked-LLM determinism): components/memory_extractor.py.

Phase 2 typed background auto-capture. Structure mirrors
tests/components/test_task_understanding.py: one in-memory LLM stub plus the
REAL PromptService (TAP-2), structural assertions only on the proposed items
(TAP-3, Pattern 8 — assert zero-or-more typed items of the right *shape*, not
an exact list a better model would change), and every rejection path tested
before its acceptance path (TAP-4 / AP-6).

Contract under test (plan §Phase 2): ``extract`` proposes a (possibly empty)
list of ``TypedMemory`` items and RAISES on a transport/parse failure — it
never falls back itself (no peer component import). A malformed *item* inside
an otherwise-valid batch is dropped (the schema is the classifier), not raised
— one junk item must not lose the whole batch. The extractor only *proposes*;
storage is the autocapture service's decision (shadow vs write-back).
"""

from __future__ import annotations

import json

import pytest

from components.memory_extractor import MemoryExtractor, MemoryExtractionError
from components.schemas import TypedMemory
from services.base_config import ModelProfile
from services.prompt_service import PromptService

# ─────────────────────────────────────────────────────────────────────
# Fakes (Pattern 6 — single mock provider)
# ─────────────────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, content: str, *, usage: dict | None = None) -> None:
        self.content = content
        self.usage_metadata = usage or {}


class FakeLLMService:
    """In-memory LLM stub: replays a canned response, records each call."""

    def __init__(
        self,
        response_content: str,
        *,
        raises: Exception | None = None,
        usage: dict | None = None,
    ) -> None:
        self._response = response_content
        self._raises = raises
        self._usage = usage
        self.calls: list[tuple] = []

    async def invoke(self, profile, messages, **kwargs):
        self.calls.append((profile, messages))
        if self._raises is not None:
            raise self._raises
        return _FakeResponse(self._response, usage=self._usage)


def _profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


def _extractor(
    response_content: str,
    *,
    raises: Exception | None = None,
    usage: dict | None = None,
) -> tuple[MemoryExtractor, FakeLLMService]:
    llm = FakeLLMService(response_content, raises=raises, usage=usage)
    extractor = MemoryExtractor(
        llm_service=llm,  # type: ignore[arg-type]
        prompt_service=PromptService(),
        profile=_profile(),
    )
    return extractor, llm


_MESSAGES = [
    {"role": "user", "content": "I always want my answers in metric units."},
    {"role": "assistant", "content": "Understood — I'll use metric units."},
]


def _items_json(*items: dict) -> str:
    return json.dumps({"memories": list(items)})


_VALID_ITEM = dict(
    type="semantic",
    content="prefers metric units",
    key="profile",
    salience=0.8,
)


# ─────────────────────────────────────────────────────────────────────
# Rejection / failure paths (written first — TAP-4)
# ─────────────────────────────────────────────────────────────────────


class TestExtractFailurePaths:
    async def test_transport_error_raises(self):
        extractor, _ = _extractor("{}", raises=RuntimeError("boom"))
        with pytest.raises(MemoryExtractionError):
            await extractor.extract(messages=_MESSAGES)

    async def test_unparseable_json_raises(self):
        extractor, _ = _extractor("this is not json at all")
        with pytest.raises(MemoryExtractionError):
            await extractor.extract(messages=_MESSAGES)

    async def test_response_not_object_raises(self):
        extractor, _ = _extractor("[1, 2, 3]")
        with pytest.raises(MemoryExtractionError):
            await extractor.extract(messages=_MESSAGES)

    async def test_empty_messages_returns_no_proposal_without_calling_llm(self):
        # Nothing to extract from → no LLM cost, empty proposal. (Confound,
        # not a defect — split it out per the eval taxonomy.)
        extractor, llm = _extractor(_items_json(_VALID_ITEM))
        result = await extractor.extract(messages=[])
        assert result.memories == []
        assert llm.calls == []

    async def test_no_memories_key_yields_empty_proposal(self):
        # A well-formed "nothing worth remembering" response is valid, not an
        # error — the extractor should propose [], not raise.
        extractor, _ = _extractor(json.dumps({"memories": []}))
        result = await extractor.extract(messages=_MESSAGES)
        assert result.memories == []

    async def test_malformed_item_is_dropped_not_raised(self):
        # One junk item (unknown type) must not lose the whole batch — the
        # schema-as-classifier guard drops it; the valid one survives.
        extractor, _ = _extractor(
            _items_json({**_VALID_ITEM, "type": "bogus"}, _VALID_ITEM)
        )
        result = await extractor.extract(messages=_MESSAGES)
        assert [m.content for m in result.memories] == ["prefers metric units"]

    async def test_item_with_extra_field_is_dropped(self):
        # extra="forbid" rejects a smuggled raw-content field; item dropped.
        extractor, _ = _extractor(
            _items_json({**_VALID_ITEM, "raw_turns": "..."})
        )
        result = await extractor.extract(messages=_MESSAGES)
        assert result.memories == []


# ─────────────────────────────────────────────────────────────────────
# Acceptance paths
# ─────────────────────────────────────────────────────────────────────


class TestExtractAcceptance:
    async def test_proposes_typed_item(self):
        extractor, _ = _extractor(_items_json(_VALID_ITEM))
        result = await extractor.extract(messages=_MESSAGES)
        assert len(result.memories) == 1
        item = result.memories[0]
        assert isinstance(item, TypedMemory)
        assert item.type == "semantic"

    async def test_proposes_all_three_types(self):
        extractor, _ = _extractor(
            _items_json(
                {**_VALID_ITEM, "type": "semantic", "key": "profile"},
                {**_VALID_ITEM, "type": "episodic", "key": "task-1"},
                {**_VALID_ITEM, "type": "procedural", "key": "strat-1"},
            )
        )
        result = await extractor.extract(messages=_MESSAGES)
        assert {m.type for m in result.memories} == {
            "semantic",
            "episodic",
            "procedural",
        }

    async def test_carries_token_usage_for_eval_capture(self):
        # The proposal seam reports real token/cost so the eval workstream can
        # measure extractor cost (I-11 — the only seam in P1/P2 that has real
        # tokens to report).
        extractor, _ = _extractor(
            _items_json(_VALID_ITEM),
            usage={"input_tokens": 120, "output_tokens": 30},
        )
        result = await extractor.extract(messages=_MESSAGES)
        assert result.tokens_in == 120
        assert result.tokens_out == 30
        assert result.cost_usd > 0
        assert result.model == "gpt-4o-mini"

    async def test_existing_profile_is_passed_to_prompt(self):
        # The extractor must SEE the current profile so it can avoid
        # re-proposing a fact already stored (consolidation precondition).
        extractor, llm = _extractor(json.dumps({"memories": []}))
        await extractor.extract(
            messages=_MESSAGES,
            existing_profile={"prefers metric units"},
        )
        rendered = llm.calls[0][1][0]["content"]
        assert "metric units" in rendered

    async def test_handles_fenced_json(self):
        extractor, _ = _extractor(
            "```json\n" + _items_json(_VALID_ITEM) + "\n```"
        )
        result = await extractor.extract(messages=_MESSAGES)
        assert len(result.memories) == 1
