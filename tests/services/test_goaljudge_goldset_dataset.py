"""L2 tests for Stage 5 golden-dataset CRUD + contamination firewall."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from components.schemas import GOAL_FAILURE_MODES
from services.governance.goaljudge_goldset_dataset import (
    DuplicateItemError,
    FirewallError,
    GoldsetItem,
    GoldsetProvenance,
    GoldsetSplit,
    GoalJudgeGoldsetRepository,
    InMemoryLangfuseDatasetClient,
    LangfuseDatasetClient,
    active_failure_modes,
    assert_firewall_batch,
    compute_test_split_hash,
)


def _sample_item(**overrides: object) -> GoldsetItem:
    base = {
        "item_id": "GS-001",
        "task_input": "do the thing",
        "final_answer": "done",
        "goal_met": False,
        "split": GoldsetSplit.DEV,
        "provenance": GoldsetProvenance.PRODUCTION,
        "failure_mode": "fabricated-progress",
    }
    base.update(overrides)
    return GoldsetItem(**base)


class TestFailureModeVocabulary:
    def test_active_failure_modes_matches_components_schema(self) -> None:
        assert active_failure_modes() == GOAL_FAILURE_MODES

    def test_unknown_failure_mode_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown failure_mode"):
            _sample_item(failure_mode="made-up-code")


class TestContaminationFirewall:
    def test_synthetic_on_test_split_rejected_at_validation(self) -> None:
        with pytest.raises(ValueError, match="contamination firewall"):
            _sample_item(
                split=GoldsetSplit.TEST,
                provenance=GoldsetProvenance.SYNTHETIC,
            )

    def test_assert_firewall_batch_rejects_duplicate_ids(self) -> None:
        with pytest.raises(FirewallError, match="duplicate item_id"):
            assert_firewall_batch([_sample_item(), _sample_item()])


class TestGoalJudgeGoldsetRepository:
    def test_ensure_dataset_is_idempotent(self) -> None:
        client = InMemoryLangfuseDatasetClient()
        repo = GoalJudgeGoldsetRepository(client)
        repo.ensure_dataset()
        repo.ensure_dataset()
        assert client.datasets == {"goaljudge_goldset_v1"}

    def test_upsert_item_creates_dataset_and_tags_metadata(self) -> None:
        client = InMemoryLangfuseDatasetClient()
        repo = GoalJudgeGoldsetRepository(client)
        item = _sample_item(item_id="GS-010", split=GoldsetSplit.TEST)
        repo.upsert_item(item)

        assert repo.item_ids == frozenset({"GS-010"})
        assert len(client.dataset_items) == 1
        stored = client.dataset_items[0]
        assert stored["id"] == "GS-010"
        assert stored["metadata"] == {
            "split": "test",
            "provenance": "production",
        }
        assert stored["input"]["failure_mode"] == "fabricated-progress"

    def test_upsert_item_rejects_duplicate_id(self) -> None:
        client = InMemoryLangfuseDatasetClient()
        repo = GoalJudgeGoldsetRepository(client)
        repo.upsert_item(_sample_item(item_id="GS-DUP"))
        with pytest.raises(DuplicateItemError, match="GS-DUP"):
            repo.upsert_item(_sample_item(item_id="GS-DUP"))

    def test_upsert_many_inserts_batch_after_firewall(self) -> None:
        client = InMemoryLangfuseDatasetClient()
        repo = GoalJudgeGoldsetRepository(client)
        items = [
            _sample_item(item_id="GS-1"),
            _sample_item(
                item_id="GS-2",
                provenance=GoldsetProvenance.SYNTHETIC,
                failure_mode="subtask-dropped",
            ),
        ]
        assert repo.upsert_many(items) == 2
        assert repo.item_ids == frozenset({"GS-1", "GS-2"})

    def test_upsert_many_aborts_on_duplicate_id(self) -> None:
        client = InMemoryLangfuseDatasetClient()
        repo = GoalJudgeGoldsetRepository(client)
        items = [
            _sample_item(item_id="GS-OK"),
            _sample_item(item_id="GS-OK", failure_mode="subtask-dropped"),
        ]
        with pytest.raises(FirewallError, match="duplicate item_id"):
            repo.upsert_many(items)
        assert repo.item_ids == frozenset()
        assert client.dataset_items == []


class TestRealLangfuseDatasetClient:
    """Protocol-shape tests for the production wrapper.

    No live Langfuse calls — the SDK is mocked. The point is to prove the
    wrapper satisfies the same Protocol the repository injects, so the
    repository code is identical against the real SDK and the in-memory
    fake.
    """

    def test_real_client_satisfies_protocol(self) -> None:
        from scripts.langfuse_dataset_client import RealLangfuseDatasetClient

        client = RealLangfuseDatasetClient(MagicMock())
        assert isinstance(client, LangfuseDatasetClient)

    def test_real_client_create_dataset_passes_through(self) -> None:
        from scripts.langfuse_dataset_client import RealLangfuseDatasetClient

        sdk = MagicMock()
        sdk.create_dataset.return_value = {"name": "goaljudge_goldset_v1"}
        client = RealLangfuseDatasetClient(sdk)

        result = client.create_dataset(name="goaljudge_goldset_v1")

        sdk.create_dataset.assert_called_once_with(name="goaljudge_goldset_v1")
        assert result == {"name": "goaljudge_goldset_v1"}

    def test_real_client_create_dataset_item_passes_through(self) -> None:
        from scripts.langfuse_dataset_client import RealLangfuseDatasetClient

        sdk = MagicMock()
        sdk.create_dataset_item.return_value = {"id": "GS-001"}
        client = RealLangfuseDatasetClient(sdk)

        payload = {"item_id": "GS-001", "goal_met": False}
        result = client.create_dataset_item(
            dataset_name="goaljudge_goldset_v1",
            input=payload,
            id="GS-001",
            metadata={"split": "test"},
        )

        sdk.create_dataset_item.assert_called_once_with(
            dataset_name="goaljudge_goldset_v1",
            input=payload,
            id="GS-001",
            metadata={"split": "test"},
        )
        assert result == {"id": "GS-001"}

    def test_real_client_coerces_pydantic_return(self) -> None:
        """SDK returns a typed Dataset object; wrapper must coerce to dict."""
        from scripts.langfuse_dataset_client import RealLangfuseDatasetClient

        sdk_return = MagicMock()
        sdk_return.model_dump.return_value = {"name": "ds", "id": "abc"}
        sdk = MagicMock()
        sdk.create_dataset.return_value = sdk_return

        client = RealLangfuseDatasetClient(sdk)
        result = client.create_dataset(name="ds")
        assert result == {"name": "ds", "id": "abc"}

    def test_builder_raises_when_env_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from scripts.langfuse_dataset_client import build_real_langfuse_dataset_client

        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

        with pytest.raises(RuntimeError, match="LANGFUSE_PUBLIC_KEY"):
            build_real_langfuse_dataset_client()


class TestComputeTestSplitHash:
    """The Stage 5 spec §9 / master plan §8.2 freeze instrument.

    The hash must be:
      1. **Stable** — insertion order does not affect the digest.
      2. **Sensitive** — any field change on any test row changes the digest.
      3. **Test-only** — dev-split items are ignored; dev churn must not
         break Stage 6's diff.
    """

    def _test_item(self, **overrides: object) -> GoldsetItem:
        base: dict[str, object] = {
            "item_id": "GS-T-001",
            "task_input": "ground-truth task",
            "final_answer": "yes",
            "goal_met": False,
            "split": GoldsetSplit.TEST,
            "provenance": GoldsetProvenance.PRODUCTION,
            "failure_mode": "fabricated-progress",
        }
        base.update(overrides)
        return GoldsetItem(**base)

    def test_hash_is_stable_across_insertion_order(self) -> None:
        a = self._test_item(item_id="GS-T-A")
        b = self._test_item(item_id="GS-T-B")
        c = self._test_item(item_id="GS-T-C")

        h_forward = compute_test_split_hash([a, b, c])
        h_reverse = compute_test_split_hash([c, b, a])
        h_shuffled = compute_test_split_hash([b, c, a])

        assert h_forward == h_reverse == h_shuffled
        assert len(h_forward) == 64  # SHA-256 hex

    def test_hash_changes_when_any_field_changes(self) -> None:
        base = self._test_item(item_id="GS-T-A")
        original = compute_test_split_hash([base])

        # Mutate every salient field one at a time; each must shift the hash.
        for mutation in [
            self._test_item(item_id="GS-T-A", task_input="different prompt"),
            self._test_item(item_id="GS-T-A", final_answer="no"),
            self._test_item(item_id="GS-T-A", goal_met=True),
            self._test_item(item_id="GS-T-A", failure_mode="subtask-dropped"),
            self._test_item(item_id="GS-T-A", partial_fraction=0.5),
            self._test_item(item_id="GS-T-A", evidence_digest="new digest"),
            self._test_item(item_id="GS-T-A", source_trace_id="abc123"),
        ]:
            assert compute_test_split_hash([mutation]) != original, (
                f"hash did not change after mutating item: {mutation.model_dump()}"
            )

    def test_hash_ignores_dev_split_items(self) -> None:
        """Adding/removing dev items must not change the test-split hash."""
        test_item = self._test_item(item_id="GS-T-A")
        dev_item = GoldsetItem(
            item_id="GS-D-A",
            task_input="dev item",
            final_answer="anything",
            goal_met=False,
            split=GoldsetSplit.DEV,
            provenance=GoldsetProvenance.SYNTHETIC,
            failure_mode="subtask-dropped",
        )
        dev_item_other = GoldsetItem(
            item_id="GS-D-B",
            task_input="another dev item, very different content",
            final_answer="totally other",
            goal_met=True,
            split=GoldsetSplit.DEV,
            provenance=GoldsetProvenance.PRODUCTION,
        )

        h_test_only = compute_test_split_hash([test_item])
        h_with_one_dev = compute_test_split_hash([test_item, dev_item])
        h_with_two_dev = compute_test_split_hash([test_item, dev_item, dev_item_other])
        h_with_swapped_dev = compute_test_split_hash([test_item, dev_item_other])

        assert h_test_only == h_with_one_dev == h_with_two_dev == h_with_swapped_dev

    def test_hash_empty_test_split(self) -> None:
        """A dev-only set still produces a deterministic (empty-payload) hash."""
        dev_only = GoldsetItem(
            item_id="GS-D-A",
            task_input="dev",
            final_answer="x",
            goal_met=False,
            split=GoldsetSplit.DEV,
            provenance=GoldsetProvenance.PRODUCTION,
        )
        h = compute_test_split_hash([dev_only])
        # SHA-256 of "[]" (json of empty list)
        import hashlib
        expected = hashlib.sha256(b"[]").hexdigest()
        assert h == expected
