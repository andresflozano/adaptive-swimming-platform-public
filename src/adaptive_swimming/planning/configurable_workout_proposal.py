from __future__ import annotations

from pydantic import Field

from adaptive_swimming.domain.session_results import (
    CompletionStatus,
    GeneratedWorkout,
    WorkoutSessionResult,
    extract_id_version,
    validate_session_result,
)
from adaptive_swimming.domain.workout import (
    StrictDomainModel,
    Target,
    TargetType,
)
from adaptive_swimming.planning.recalibrated_target_review import (
    PriorTargetReviewDecision,
    applicable_target_seconds,
)
from adaptive_swimming.planning.workout_proposal import (
    AdaptationTraceEntry,
    NextWorkoutProposal,
    ProposalStatus,
    generated_text,
)


class TargetApplicationSelection(StrictDomainModel):
    block_sequence: int = Field(ge=1)
    set_group_sequence: int = Field(ge=1)
    item_sequence: int = Field(ge=1)


def format_target_seconds(seconds: int) -> str:
    if seconds <= 0:
        raise ValueError("Target seconds must be positive.")

    minutes, remaining_seconds = divmod(seconds, 60)
    if minutes:
        return f"{minutes}:{remaining_seconds:02d}"
    return str(remaining_seconds)


def build_configurable_workout_proposal(
    *,
    parent_generated_workout: GeneratedWorkout,
    previous_result: WorkoutSessionResult,
    reviewed_decision: PriorTargetReviewDecision,
    selection: TargetApplicationSelection,
    proposal_id: str,
    proposal_version: int,
    generated_workout_id: str,
    generated_workout_version: int,
    workout_session_id: str,
    generation_reason: str,
    adaptation_trace: tuple[AdaptationTraceEntry, ...],
    limitations: tuple[str, ...],
) -> NextWorkoutProposal:
    validate_session_result(parent_generated_workout, previous_result)

    if previous_result.completion_status == CompletionStatus.NOT_STARTED:
        raise ValueError("A future-workout proposal requires a completed previous session result.")

    if previous_result.safety_issue_reported:
        raise ValueError(
            "A future-workout proposal cannot use a previous result with a reported safety issue."
        )

    if extract_id_version(proposal_id) != proposal_version:
        raise ValueError("Proposal ID version must match proposal_version.")

    target_seconds = applicable_target_seconds(reviewed_decision)
    decision_key = reviewed_decision.proposal.key
    coordinate = (
        selection.block_sequence,
        selection.set_group_sequence,
        selection.item_sequence,
    )

    matching_items = tuple(
        item
        for block in parent_generated_workout.workout.blocks
        for group in block.set_groups
        for item in group.items
        if (block.sequence, group.sequence, item.sequence) == coordinate
    )

    if len(matching_items) != 1:
        raise ValueError(
            "Target application selection must resolve to exactly one planned item; "
            f"found {len(matching_items)}."
        )

    selected_item = matching_items[0]
    selected_key = (
        selected_item.exercise,
        selected_item.distance_meters,
        selected_item.equipment,
        selected_item.intensity,
    )
    expected_key = (
        decision_key.exercise,
        decision_key.distance_meters,
        decision_key.equipment,
        decision_key.intensity,
    )

    if selected_key != expected_key:
        raise ValueError("Selected planned item does not match the reviewed decision strict key.")

    if selected_item.target is not None and (
        selected_item.target.target_type != TargetType.REPETITION_COMPLETION_TIME
        or selected_item.target.target_seconds != target_seconds
    ):
        raise ValueError("The selected item contains a conflicting existing target.")

    raw_target = format_target_seconds(target_seconds)
    updated_target = Target(
        target_type=TargetType.REPETITION_COMPLETION_TIME,
        raw_value=raw_target,
        target_seconds=target_seconds,
    )

    updated_blocks = tuple(
        block.model_copy(
            update={
                "set_groups": tuple(
                    group.model_copy(
                        update={
                            "items": tuple(
                                item.model_copy(
                                    update={
                                        "target": updated_target,
                                        "swimmer_instruction": (
                                            f"Complete each repetition in {raw_target} or faster "
                                            "and record the actual time."
                                        ),
                                        "source_text": generated_text(
                                            f"Apply reviewed {raw_target} repetition target"
                                        ),
                                    }
                                )
                                if (block.sequence, group.sequence, item.sequence) == coordinate
                                else item
                                for item in group.items
                            )
                        }
                    )
                    for group in block.set_groups
                )
            }
        )
        if block.sequence == selection.block_sequence
        else block
        for block in parent_generated_workout.workout.blocks
    )

    updated_workout = parent_generated_workout.workout.model_copy(
        update={
            "session_id": workout_session_id,
            "source_section": generated_text(
                f"Configurable proposal using {reviewed_decision.review_decision_id}"
            ),
            "blocks": updated_blocks,
        }
    )

    generated_workout = GeneratedWorkout(
        generated_workout_id=generated_workout_id,
        workout_version=generated_workout_version,
        workout=updated_workout,
        pool_length_meters=parent_generated_workout.pool_length_meters,
        available_training_seconds=parent_generated_workout.available_training_seconds,
        equipment_available=parent_generated_workout.equipment_available,
        generation_reason=generation_reason,
    )

    return NextWorkoutProposal(
        proposal_id=proposal_id,
        proposal_version=proposal_version,
        parent_generated_workout_id=parent_generated_workout.generated_workout_id,
        previous_session_result_id=previous_result.session_result_id,
        status=ProposalStatus.PROPOSED,
        proposed_generated_workout=generated_workout,
        adaptation_trace=adaptation_trace,
        limitations=limitations,
    )
