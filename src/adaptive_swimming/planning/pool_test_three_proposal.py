from __future__ import annotations

from adaptive_swimming.domain.session_results import (
    GeneratedWorkout,
    WorkoutSessionResult,
    validate_session_result,
)
from adaptive_swimming.domain.workout import (
    EquipmentCode,
    ExerciseCode,
    IntensityCode,
    Target,
    TargetType,
    WorkoutSession,
)
from adaptive_swimming.evaluation.pace_calibration import PaceObservationKey
from adaptive_swimming.planning.target_review_decisions import (
    TargetReviewDecision,
    TargetReviewDecisionType,
)
from adaptive_swimming.planning.workout_proposal import (
    AdaptationTraceEntry,
    NextWorkoutProposal,
    ProposalStatus,
    generated_text,
)

FINS_TARGET_KEY = PaceObservationKey(
    exercise=ExerciseCode.FREESTYLE,
    distance_meters=50,
    equipment=(EquipmentCode.FINS,),
    intensity=IntensityCode.UNRESOLVED,
)
PADDLES_TARGET_KEY = PaceObservationKey(
    exercise=ExerciseCode.FREESTYLE,
    distance_meters=100,
    equipment=(EquipmentCode.PADDLES_INVERTED,),
    intensity=IntensityCode.UNRESOLVED,
)


def validate_review_decisions(
    accepted_fins_decision: TargetReviewDecision,
    deferred_paddles_decision: TargetReviewDecision,
) -> None:
    if accepted_fins_decision.decision != TargetReviewDecisionType.ACCEPTED_FOR_FUTURE_WORKOUT:
        raise ValueError("The fins target decision must be accepted for a future workout.")
    if not accepted_fins_decision.may_be_applied_to_future_workout:
        raise ValueError("The fins target decision is not applicable.")
    if accepted_fins_decision.proposal.key != FINS_TARGET_KEY:
        raise ValueError("The accepted decision must reference the 50 m fins key.")
    if accepted_fins_decision.reviewed_target_seconds != 65:
        raise ValueError("The accepted fins target must be 65 seconds.")

    if deferred_paddles_decision.decision != TargetReviewDecisionType.DEFERRED:
        raise ValueError("The inverted-paddles target decision must be deferred.")
    if deferred_paddles_decision.may_be_applied_to_future_workout:
        raise ValueError("The deferred paddles decision must remain unapplied.")
    if deferred_paddles_decision.proposal.key != PADDLES_TARGET_KEY:
        raise ValueError("The deferred decision must reference the 100 m inverted-paddles key.")
    if deferred_paddles_decision.reviewed_target_seconds != 156:
        raise ValueError("The deferred paddles anchor must be 156 seconds.")


def build_pool_test_three_workout(
    parent_generated_workout: GeneratedWorkout,
    accepted_fins_decision: TargetReviewDecision,
    deferred_paddles_decision: TargetReviewDecision,
) -> WorkoutSession:
    validate_review_decisions(
        accepted_fins_decision,
        deferred_paddles_decision,
    )

    matching_coordinates = tuple(
        (block.sequence, group.sequence, item.sequence)
        for block in parent_generated_workout.workout.blocks
        for group in block.set_groups
        for item in group.items
        if (
            item.exercise == FINS_TARGET_KEY.exercise
            and item.distance_meters == FINS_TARGET_KEY.distance_meters
            and item.equipment == FINS_TARGET_KEY.equipment
            and item.intensity == FINS_TARGET_KEY.intensity
        )
    )
    if len(matching_coordinates) != 1:
        raise ValueError(
            "Pool Test 3 requires exactly one planned item matching the "
            f"accepted fins key; found {len(matching_coordinates)}."
        )

    target_coordinate = matching_coordinates[0]
    updated_blocks = tuple(
        block.model_copy(
            update={
                "set_groups": tuple(
                    group.model_copy(
                        update={
                            "items": tuple(
                                item.model_copy(
                                    update={
                                        "target": Target(
                                            target_type=(TargetType.REPETITION_COMPLETION_TIME),
                                            raw_value="1:05",
                                            target_seconds=65,
                                        ),
                                        "swimmer_instruction": (
                                            "Complete each repetition in 1:05 or "
                                            "faster and record the actual time."
                                        ),
                                        "source_text": generated_text(
                                            "4 x 50 m with fins, 1:05 target, record actual pace"
                                        ),
                                    }
                                )
                                if (
                                    block.sequence,
                                    group.sequence,
                                    item.sequence,
                                )
                                == target_coordinate
                                else item
                                for item in group.items
                            )
                        }
                    )
                    for group in block.set_groups
                ),
                "source_text": generated_text("4 x 50 m freestyle with fins at 1:05 target")
                if block.sequence == target_coordinate[0]
                else block.source_text,
            }
        )
        for block in parent_generated_workout.workout.blocks
    )

    return parent_generated_workout.workout.model_copy(
        update={
            "session_id": "WT_ENGINE_POOL_TEST_003_V1",
            "source_section": generated_text("Pool Test 3, one accepted pace-target change"),
            "blocks": updated_blocks,
        }
    )


def build_pool_test_three_proposal(
    parent_generated_workout: GeneratedWorkout,
    previous_result: WorkoutSessionResult,
    accepted_fins_decision: TargetReviewDecision,
    deferred_paddles_decision: TargetReviewDecision,
    *,
    proposal_id: str,
    generated_workout_id: str,
) -> NextWorkoutProposal:
    validate_session_result(parent_generated_workout, previous_result)
    proposed_workout = build_pool_test_three_workout(
        parent_generated_workout,
        accepted_fins_decision,
        deferred_paddles_decision,
    )
    generated = GeneratedWorkout(
        generated_workout_id=generated_workout_id,
        workout_version=1,
        workout=proposed_workout,
        pool_length_meters=parent_generated_workout.pool_length_meters,
        available_training_seconds=(parent_generated_workout.available_training_seconds),
        equipment_available=parent_generated_workout.equipment_available,
        generation_reason="POOL_TEST_3_ACCEPTED_FINS_TARGET_PROPOSAL",
    )

    return NextWorkoutProposal(
        proposal_id=proposal_id,
        proposal_version=1,
        parent_generated_workout_id=(parent_generated_workout.generated_workout_id),
        previous_session_result_id=previous_result.session_result_id,
        status=ProposalStatus.PROPOSED,
        proposed_generated_workout=generated,
        adaptation_trace=(
            AdaptationTraceEntry(
                rule_id="PRESERVE_POOL_TEST_2_STRUCTURE",
                description=(
                    "Preserved the six-block, 1,500 m Pool Test 2 structure "
                    "and 60-minute availability."
                ),
            ),
            AdaptationTraceEntry(
                rule_id="APPLY_ACCEPTED_FINS_TARGET",
                description=(
                    "Applied accepted decision TRD_20260905_001_V1 as a "
                    "65-second target for each 50 m fins repetition."
                ),
            ),
            AdaptationTraceEntry(
                rule_id="EXCLUDE_DEFERRED_PADDLES_TARGET",
                description=("Did not apply deferred decision TRD_20260905_002_V1."),
            ),
        ),
        limitations=(
            "The 65-second fins target remains provisional until evaluated "
            "in a completed future session.",
            "The 100 m aerobic freestyle set remains without a fixed target.",
            "Approximately 30 seconds of operational time between blocks is "
            "observed but not modeled as prescribed rest.",
            "This proposal is not persisted or accepted by the builder.",
        ),
    )
