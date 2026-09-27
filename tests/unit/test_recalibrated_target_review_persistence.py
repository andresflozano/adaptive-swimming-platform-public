from __future__ import annotations

from pathlib import Path

import pytest

from adaptive_swimming.persistence.recalibrated_target_review_records import (
    load_recalibrated_review_set,
    recalibrated_review_set_path,
    save_recalibrated_review_set,
)
from adaptive_swimming.planning.recalibrated_target_review import (
    RecalibratedTargetReviewAction,
    RecalibratedTargetReviewSet,
    build_recalibrated_target_review_decision,
    build_recalibrated_target_review_set,
)
from tests.unit.test_recalibrated_target_review import (
    build_prior_decision,
    build_proposal,
)

REVIEW_SET_ID = "RTRS_20260906_001_V1"


def build_review_set() -> RecalibratedTargetReviewSet:
    decision = build_recalibrated_target_review_decision(
        build_proposal(),
        review_decision_id="RTRD_20260906_001_V1",
        review_decision_version=1,
        action=RecalibratedTargetReviewAction.RETAIN_CURRENT_TARGET,
        effective_target_seconds=65,
        prior_decision=build_prior_decision(),
        rationale=("Retain the validated 65-second target for one additional session.",),
    )
    return build_recalibrated_target_review_set(
        review_set_id=REVIEW_SET_ID,
        review_set_version=1,
        decisions=(decision,),
    )


def test_recalibrated_review_set_path_uses_validated_id(
    tmp_path: Path,
) -> None:
    path = recalibrated_review_set_path(REVIEW_SET_ID, tmp_path)

    assert path == tmp_path / f"{REVIEW_SET_ID}.json"


def test_recalibrated_review_set_path_rejects_invalid_id(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="Invalid recalibrated review-set identifier",
    ):
        recalibrated_review_set_path("INVALID", tmp_path)


def test_recalibrated_review_set_path_rejects_path_traversal(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="Invalid recalibrated review-set identifier",
    ):
        recalibrated_review_set_path("../outside", tmp_path)


def test_recalibrated_review_set_round_trips(
    tmp_path: Path,
) -> None:
    review_set = build_review_set()

    path = save_recalibrated_review_set(review_set, tmp_path)

    assert load_recalibrated_review_set(path) == review_set


def test_recalibrated_review_set_refuses_overwrite(
    tmp_path: Path,
) -> None:
    review_set = build_review_set()
    save_recalibrated_review_set(review_set, tmp_path)

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        save_recalibrated_review_set(review_set, tmp_path)


def test_persistence_does_not_modify_source_review_set(
    tmp_path: Path,
) -> None:
    review_set = build_review_set()
    before = review_set.model_dump_json()

    save_recalibrated_review_set(review_set, tmp_path)

    assert review_set.model_dump_json() == before


def test_success_leaves_no_temporary_files(
    tmp_path: Path,
) -> None:
    save_recalibrated_review_set(build_review_set(), tmp_path)

    assert not tuple(tmp_path.rglob("*.tmp"))
