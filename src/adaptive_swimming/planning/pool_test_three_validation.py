from __future__ import annotations

from adaptive_swimming.domain.workout import (
    EquipmentCode,
    ExerciseCode,
    TargetType,
)
from adaptive_swimming.planning.workout_proposal import (
    NextWorkoutProposal,
    ProposalStatus,
)


def targeted_items(
    proposal: NextWorkoutProposal,
) -> tuple[tuple[int, int, int], ...]:
    return tuple(
        (block.sequence, group.sequence, item.sequence)
        for block in proposal.proposed_generated_workout.workout.blocks
        for group in block.set_groups
        for item in group.items
        if item.target is not None
    )


def validate_pool_test_three_proposal(
    proposal: NextWorkoutProposal,
    *,
    expected_parent_id: str,
    expected_previous_result_id: str,
    expected_generated_workout_id: str,
) -> None:
    if proposal.status != ProposalStatus.PROPOSED:
        raise ValueError("Pool Test 3 proposal must remain PROPOSED.")
    if proposal.parent_generated_workout_id != expected_parent_id:
        raise ValueError("Pool Test 3 parent workout lineage is invalid.")
    if proposal.previous_session_result_id != expected_previous_result_id:
        raise ValueError("Pool Test 3 previous-result lineage is invalid.")

    generated = proposal.proposed_generated_workout
    workout = generated.workout
    if generated.generated_workout_id != expected_generated_workout_id:
        raise ValueError("Pool Test 3 generated-workout ID is invalid.")
    if len(workout.blocks) != 6:
        raise ValueError("Pool Test 3 must preserve six blocks.")
    if workout.total_distance_meters() != 1500:
        raise ValueError("Pool Test 3 must preserve 1,500 m.")
    if proposal.time_feasibility.status.value != "UNRESOLVED":
        raise ValueError("Pool Test 3 time feasibility must remain UNRESOLVED.")

    if targeted_items(proposal) != ((4, 1, 1),):
        raise ValueError("Pool Test 3 must target only Block 4, group 1, item 1.")

    block_two_item = workout.blocks[1].set_groups[0].items[0]
    block_three_item = workout.blocks[2].set_groups[0].items[0]
    fins_item = workout.blocks[3].set_groups[0].items[0]

    if block_two_item.target is not None:
        raise ValueError("The deferred paddles anchor must remain unapplied.")
    if block_three_item.target is not None:
        raise ValueError("The aerobic freestyle item must remain untargeted.")
    if (
        fins_item.exercise != ExerciseCode.FREESTYLE
        or fins_item.distance_meters != 50
        or fins_item.repetitions != 4
        or fins_item.equipment != (EquipmentCode.FINS,)
        or fins_item.target is None
        or fins_item.target.target_type != TargetType.REPETITION_COMPLETION_TIME
        or fins_item.target.raw_value != "1:05"
        or fins_item.target.target_seconds != 65
    ):
        raise ValueError("The accepted 65-second fins target is invalid.")
