from __future__ import annotations

import pytest

from adaptive_swimming.domain.session_results import (
    CompletionStatus,
    GeneratedWorkout,
    WorkoutSessionResult,
)
from adaptive_swimming.planning.pool_test_five_proposal import (
    build_pool_test_five_proposal,
    build_pool_test_five_workout,
)
from adaptive_swimming.planning.recalibrated_target_review import (
    RecalibratedTargetReviewSet,
)
from adaptive_swimming.planning.workout_progression import (
    WorkoutProgressionAssessment,
    WorkoutProgressionObjective,
)
from adaptive_swimming.planning.workout_proposal import (
    NextWorkoutProposal,
    ProposalStatus,
)
from tests.unit.scripts.test_review_recalibrated_targets import (
    review_set_for_persistence,
)
from tests.unit.test_configurable_workout_proposal import build_parent

PROPOSAL_ID = "NWP_20260913_001_V1"
GENERATED_ID = "GW_20260913_001_V1"
DECISION_ID = "RTRD_20260906_001_V1"


def build_completed_result(parent: GeneratedWorkout) -> WorkoutSessionResult:
    return WorkoutSessionResult(
        session_result_id="SR_20260905_001_V2",
        generated_workout_id=parent.generated_workout_id,
        result_version=2,
        completion_status=CompletionStatus.COMPLETED_AS_WRITTEN,
        completed_distance_meters=parent.planned_distance_meters,
        actual_total_seconds=3600,
        perceived_exertion=7,
        safety_issue_reported=False,
    )


def inputs() -> tuple[
    GeneratedWorkout,
    WorkoutSessionResult,
    RecalibratedTargetReviewSet,
]:
    parent = build_parent()
    return parent, build_completed_result(parent), review_set_for_persistence()


def proposal_and_assessment() -> tuple[
    NextWorkoutProposal,
    WorkoutProgressionAssessment,
]:
    parent, result, review_set = inputs()
    return build_pool_test_five_proposal(
        parent,
        result,
        review_set,
        review_decision_id=DECISION_ID,
        proposal_id=PROPOSAL_ID,
        generated_workout_id=GENERATED_ID,
    )


def test_builds_proposed_adaptive_workout() -> None:
    proposal, assessment = proposal_and_assessment()

    assert proposal.status == ProposalStatus.PROPOSED
    assert proposal.proposed_generated_workout.planned_distance_meters == 1500
    assert proposal.proposed_generated_workout.available_training_seconds == 3600
    assert assessment.objective == WorkoutProgressionObjective.ADAPTIVE_PROGRESSION
    assert assessment.satisfies_objective
    assert assessment.structural_changes


def test_has_only_retained_fins_target() -> None:
    proposal, _ = proposal_and_assessment()
    targeted = tuple(
        item
        for block in proposal.proposed_generated_workout.workout.blocks
        for group in block.set_groups
        for item in group.items
        if item.target is not None
    )

    assert len(targeted) == 1
    assert targeted[0].target is not None
    assert targeted[0].target.target_seconds == 65
    assert targeted[0].repetitions == 4
    assert targeted[0].distance_meters == 50


def test_structure_is_not_pool_test_four_copy() -> None:
    proposal, assessment = proposal_and_assessment()
    workout = proposal.proposed_generated_workout.workout

    assert tuple(block.total_distance_meters() for block in workout.blocks) == (
        300,
        200,
        400,
        200,
        100,
        300,
    )
    assert any(change.field == "repetitions" for change in assessment.structural_changes)
    assert any(change.field == "rest" for change in assessment.structural_changes)


def test_preserves_lineage_and_round_trips() -> None:
    parent, result, _ = inputs()
    proposal, _ = proposal_and_assessment()

    assert proposal.parent_generated_workout_id == parent.generated_workout_id
    assert proposal.previous_session_result_id == result.session_result_id
    assert NextWorkoutProposal.model_validate_json(proposal.model_dump_json()) == proposal


def test_inputs_remain_unchanged() -> None:
    parent, result, review_set = inputs()
    before = tuple(value.model_dump_json() for value in (parent, result, review_set))

    build_pool_test_five_proposal(
        parent,
        result,
        review_set,
        review_decision_id=DECISION_ID,
        proposal_id=PROPOSAL_ID,
        generated_workout_id=GENERATED_ID,
    )

    after = tuple(value.model_dump_json() for value in (parent, result, review_set))
    assert after == before


def test_rejects_not_started_result() -> None:
    parent, result, review_set = inputs()
    payload = result.model_dump()
    payload.update(
        {
            "completion_status": CompletionStatus.NOT_STARTED,
            "completed_distance_meters": 0,
            "actual_total_seconds": None,
            "perceived_exertion": None,
            "equipment_used": (),
            "block_results": (),
        }
    )
    not_started = WorkoutSessionResult.model_validate(payload)

    with pytest.raises(ValueError, match="completed previous result"):
        build_pool_test_five_proposal(
            parent,
            not_started,
            review_set,
            review_decision_id=DECISION_ID,
            proposal_id=PROPOSAL_ID,
            generated_workout_id=GENERATED_ID,
        )


def test_rejects_safety_flag() -> None:
    parent, result, review_set = inputs()
    flagged = result.model_copy(update={"safety_issue_reported": True})

    with pytest.raises(ValueError, match="safety-flagged"):
        build_pool_test_five_proposal(
            parent,
            flagged,
            review_set,
            review_decision_id=DECISION_ID,
            proposal_id=PROPOSAL_ID,
            generated_workout_id=GENERATED_ID,
        )


def test_rejects_missing_decision() -> None:
    parent, result, review_set = inputs()

    with pytest.raises(ValueError, match="exactly one"):
        build_pool_test_five_proposal(
            parent,
            result,
            review_set,
            review_decision_id="RTRD_20260913_999_V1",
            proposal_id=PROPOSAL_ID,
            generated_workout_id=GENERATED_ID,
        )


def test_workout_rejects_non_retained_target() -> None:
    with pytest.raises(ValueError, match="retained 65-second"):
        build_pool_test_five_workout(64)
