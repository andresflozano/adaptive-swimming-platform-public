from __future__ import annotations

from pydantic import Field

from adaptive_swimming.domain.session_results import (
    CompletionStatus,
    GeneratedWorkout,
    WorkoutSessionResult,
    validate_session_result,
)
from adaptive_swimming.domain.workout import (
    RestApplication,
    StrictDomainModel,
    TargetType,
)


class SessionPerformanceEvaluation(StrictDomainModel):
    generated_workout_id: str
    session_result_id: str
    completion_status: CompletionStatus

    planned_distance_meters: int = Field(ge=0)
    completed_distance_meters: int = Field(ge=0)
    distance_completion_ratio: float = Field(ge=0, le=1)

    planned_block_count: int = Field(ge=0)
    reported_block_count: int = Field(ge=0)
    block_reporting_ratio: float = Field(ge=0, le=1)

    planned_timed_repetition_count: int = Field(ge=0)
    observed_timed_repetition_count: int = Field(ge=0)
    timed_repetition_completion_ratio: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )

    observed_target_count: int = Field(ge=0)
    observed_targets_met_count: int = Field(ge=0)
    observed_target_adherence_ratio: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )

    comparable_recorded_rest_count: int = Field(ge=0)
    matching_recorded_rest_count: int = Field(ge=0)
    recorded_rest_adherence_ratio: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )

    actual_total_seconds: int | None = Field(
        default=None,
        gt=0,
    )
    perceived_exertion: int | None = Field(
        default=None,
        ge=1,
        le=10,
    )
    safety_issue_reported: bool


def safe_ratio(
    numerator: int,
    denominator: int,
) -> float | None:
    if denominator < 0 or numerator < 0:
        raise ValueError("Ratio inputs cannot be negative.")

    if numerator > denominator:
        raise ValueError("Ratio numerator cannot exceed denominator.")

    if denominator == 0:
        return None

    return numerator / denominator


def planned_timed_repetition_count(
    generated_workout: GeneratedWorkout,
) -> int:
    return sum(
        item.repetitions * set_group.repeat_cycles
        for block in generated_workout.workout.blocks
        for set_group in block.set_groups
        for item in set_group.items
        if (
            item.target is not None
            and item.target.target_type == TargetType.REPETITION_COMPLETION_TIME
            and item.target.target_seconds is not None
        )
    )


def prescribed_rest_after_seconds(
    generated_workout: GeneratedWorkout,
    *,
    block_sequence: int,
    set_group_sequence: int,
    item_sequence: int,
    repetition_number: int,
) -> int | None:
    block = next(
        block for block in generated_workout.workout.blocks if block.sequence == block_sequence
    )
    set_group = next(group for group in block.set_groups if group.sequence == set_group_sequence)
    item = next(item for item in set_group.items if item.sequence == item_sequence)

    if set_group.rest is None:
        return None

    rest = set_group.rest

    if rest.application == RestApplication.BETWEEN_REPETITIONS:
        is_final_unit = repetition_number == item.repetitions
    elif rest.application == RestApplication.BETWEEN_ITEMS:
        final_item_sequence = set_group.items[-1].sequence
        is_final_unit = item_sequence == final_item_sequence
    else:
        return None

    if is_final_unit and not rest.include_after_final:
        return None

    return rest.seconds


def evaluate_session_performance(
    generated_workout: GeneratedWorkout,
    session_result: WorkoutSessionResult,
) -> SessionPerformanceEvaluation:
    validate_session_result(
        generated_workout,
        session_result,
    )

    planned_distance = generated_workout.planned_distance_meters
    planned_blocks = len(generated_workout.workout.blocks)
    reported_blocks = len(session_result.block_results)
    planned_timed_repetitions = planned_timed_repetition_count(generated_workout)

    planned_items = {
        (
            block.sequence,
            set_group.sequence,
            item.sequence,
        ): item
        for block in generated_workout.workout.blocks
        for set_group in block.set_groups
        for item in set_group.items
    }

    observed_timed_repetitions = 0
    observed_targets = 0
    observed_targets_met = 0
    comparable_rests = 0
    matching_rests = 0

    for block_result in session_result.block_results:
        for repetition in block_result.repetition_results:
            item = planned_items[
                (
                    repetition.block_sequence,
                    repetition.set_group_sequence,
                    repetition.item_sequence,
                )
            ]

            if (
                item.target is not None
                and item.target.target_type == TargetType.REPETITION_COMPLETION_TIME
                and item.target.target_seconds is not None
                and repetition.completed
            ):
                observed_timed_repetitions += 1

                if repetition.actual_seconds is not None:
                    observed_targets += 1

                    if repetition.actual_seconds <= item.target.target_seconds:
                        observed_targets_met += 1

            prescribed_rest = prescribed_rest_after_seconds(
                generated_workout,
                block_sequence=(repetition.block_sequence),
                set_group_sequence=(repetition.set_group_sequence),
                item_sequence=(repetition.item_sequence),
                repetition_number=(repetition.repetition_number),
            )

            if prescribed_rest is not None:
                if repetition.rest_after_seconds is not None:
                    comparable_rests += 1

                    if repetition.rest_after_seconds == prescribed_rest:
                        matching_rests += 1

    distance_ratio = safe_ratio(
        session_result.completed_distance_meters,
        planned_distance,
    )
    block_ratio = safe_ratio(
        reported_blocks,
        planned_blocks,
    )
    timed_repetition_ratio = safe_ratio(
        observed_timed_repetitions,
        planned_timed_repetitions,
    )

    assert distance_ratio is not None
    assert block_ratio is not None

    return SessionPerformanceEvaluation(
        generated_workout_id=(generated_workout.generated_workout_id),
        session_result_id=(session_result.session_result_id),
        completion_status=(session_result.completion_status),
        planned_distance_meters=planned_distance,
        completed_distance_meters=(session_result.completed_distance_meters),
        distance_completion_ratio=distance_ratio,
        planned_block_count=planned_blocks,
        reported_block_count=reported_blocks,
        block_reporting_ratio=block_ratio,
        planned_timed_repetition_count=(planned_timed_repetitions),
        observed_timed_repetition_count=(observed_timed_repetitions),
        timed_repetition_completion_ratio=(timed_repetition_ratio),
        observed_target_count=observed_targets,
        observed_targets_met_count=(observed_targets_met),
        observed_target_adherence_ratio=safe_ratio(
            observed_targets_met,
            observed_targets,
        ),
        comparable_recorded_rest_count=comparable_rests,
        matching_recorded_rest_count=matching_rests,
        recorded_rest_adherence_ratio=safe_ratio(
            matching_rests,
            comparable_rests,
        ),
        actual_total_seconds=(session_result.actual_total_seconds),
        perceived_exertion=(session_result.perceived_exertion),
        safety_issue_reported=(session_result.safety_issue_reported),
    )
