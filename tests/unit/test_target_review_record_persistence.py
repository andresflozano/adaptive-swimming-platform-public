from __future__ import annotations

from pathlib import Path

import pytest

from adaptive_swimming.domain.workout import (
    EquipmentCode,
    ExerciseCode,
    IntensityCode,
)
from adaptive_swimming.evaluation.calibration_eligibility import (
    assess_calibration_eligibility,
)
from adaptive_swimming.evaluation.pace_calibration import (
    PaceObservation,
    PaceObservationKey,
    ProvisionalPaceSummary,
)
from adaptive_swimming.persistence.target_review_records import (
    load_target_review_decision,
    save_target_review_decision,
    target_review_decision_path,
)
from adaptive_swimming.planning.provisional_target_proposals import (
    ProvisionalTargetProposal,
    propose_target_for_review,
)
from adaptive_swimming.planning.target_review_decisions import (
    TargetReviewDecision,
    TargetReviewDecisionType,
    record_target_review_decision,
)

REVIEW_DECISION_ID = "TRD_20260905_001_V1"
REVIEW_DECISION_VERSION = 1


def build_proposal() -> ProvisionalTargetProposal:
    key = PaceObservationKey(
        exercise=ExerciseCode.FREESTYLE,
        distance_meters=50,
        equipment=(EquipmentCode.FINS,),
        intensity=IntensityCode.UNRESOLVED,
    )
    values = (62, 65, 65, 75, 65, 64, 62, 64)
    session_ids = (
        "SR_20260901_001_V2",
        "SR_20260901_001_V2",
        "SR_20260901_001_V2",
        "SR_20260901_001_V2",
        "SR_20260903_001_V2",
        "SR_20260903_001_V2",
        "SR_20260903_001_V2",
        "SR_20260903_001_V2",
    )
    observations = tuple(
        PaceObservation(
            generated_workout_id=(
                "GW_20260901_001_V1" if session_id == "SR_20260901_001_V2" else "GW_20260903_001_V1"
            ),
            session_result_id=session_id,
            block_sequence=4,
            set_group_sequence=1,
            item_sequence=1,
            repetition_number=index,
            key=key,
            actual_seconds=value,
        )
        for index, (value, session_id) in enumerate(
            zip(values, session_ids, strict=True),
            start=1,
        )
    )
    summary = ProvisionalPaceSummary(
        key=key,
        sample_count=8,
        minimum_seconds=62,
        maximum_seconds=75,
        mean_seconds=65.25,
        median_seconds=64.5,
        observations=observations,
        limitations=("Synthetic test summary.",),
    )

    return propose_target_for_review(assess_calibration_eligibility(summary))


def build_decision() -> TargetReviewDecision:
    return record_target_review_decision(
        build_proposal(),
        review_decision_id=REVIEW_DECISION_ID,
        review_decision_version=REVIEW_DECISION_VERSION,
        decision=(TargetReviewDecisionType.ACCEPTED_FOR_FUTURE_WORKOUT),
        rationale=("Review anchor accepted for a controlled future test.",),
    )


def test_target_review_decision_path_uses_validated_id(
    tmp_path: Path,
) -> None:
    path = target_review_decision_path(
        REVIEW_DECISION_ID,
        tmp_path,
    )

    assert path == tmp_path / f"{REVIEW_DECISION_ID}.json"


def test_target_review_decision_path_rejects_invalid_id(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="Invalid target review decision identifier",
    ):
        target_review_decision_path(
            "../outside",
            tmp_path,
        )


def test_target_review_decision_round_trips(
    tmp_path: Path,
) -> None:
    decision = build_decision()

    path = save_target_review_decision(
        decision,
        tmp_path,
    )

    assert load_target_review_decision(path) == decision


def test_target_review_decision_refuses_overwrite(
    tmp_path: Path,
) -> None:
    decision = build_decision()

    save_target_review_decision(
        decision,
        tmp_path,
    )

    with pytest.raises(
        FileExistsError,
        match="Refusing to overwrite",
    ):
        save_target_review_decision(
            decision,
            tmp_path,
        )


def test_target_review_decision_write_leaves_no_temp_file(
    tmp_path: Path,
) -> None:
    save_target_review_decision(
        build_decision(),
        tmp_path,
    )

    assert not tuple(tmp_path.rglob("*.tmp"))


def test_persistence_does_not_modify_source_decision(
    tmp_path: Path,
) -> None:
    decision = build_decision()
    before = decision.model_dump_json()

    save_target_review_decision(
        decision,
        tmp_path,
    )

    assert decision.model_dump_json() == before
