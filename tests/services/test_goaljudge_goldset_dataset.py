"""L2 tests for Stage 5 golden-dataset CRUD + contamination firewall."""

from __future__ import annotations

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
    active_failure_modes,
    assert_firewall_batch,
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
