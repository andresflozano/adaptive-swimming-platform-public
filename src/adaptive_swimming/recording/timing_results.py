from __future__ import annotations

from adaptive_swimming.domain.session_results import (
    GeneratedWorkout,
    RepetitionResult,
)
from adaptive_swimming.domain.workout import TargetType
from adaptive_swimming.recording.workout_timing import ItemTimingSummary


def convert_item_timing_to_repetition_results(
    *,
    generated_workout: GeneratedWorkout,
    summary: ItemTimingSummary,
    require_complete_capture: bool = True,
) -> tuple[RepetitionResult, ...]:
    blocks = tuple(
        block
        for block in generated_workout.workout.blocks
        if block.sequence == summary.block_sequence
    )
    if len(blocks) != 1:
        raise ValueError(
            f"Timing summary must reference exactly one planned block; found {len(blocks)}."
        )

    groups = tuple(
        group for group in blocks[0].set_groups if group.sequence == summary.set_group_sequence
    )
    if len(groups) != 1:
        raise ValueError(
            f"Timing summary must reference exactly one planned set group; found {len(groups)}."
        )

    items = tuple(item for item in groups[0].items if item.sequence == summary.item_sequence)
    if len(items) != 1:
        raise ValueError(
            f"Timing summary must reference exactly one planned item; found {len(items)}."
        )

    item = items[0]
    captured_count = len(summary.repetitions)
    if captured_count > item.repetitions:
        raise ValueError("Timing capture exceeds the planned repetition count.")
    if require_complete_capture and captured_count != item.repetitions:
        raise ValueError("Complete timing conversion requires every planned repetition.")

    planned_target_seconds = None
    if item.target is not None and item.target.target_type == TargetType.REPETITION_COMPLETION_TIME:
        planned_target_seconds = item.target.target_seconds

    if summary.target_seconds != planned_target_seconds:
        raise ValueError(
            "Timing summary target must match the planned repetition-completion target."
        )

    expected_numbers = tuple(range(1, captured_count + 1))
    observed_numbers = tuple(repetition.repetition_number for repetition in summary.repetitions)
    if observed_numbers != expected_numbers:
        raise ValueError("Calculated repetition numbers must be consecutive and start at 1.")

    results: list[RepetitionResult] = []
    for index, repetition in enumerate(summary.repetitions):
        rest_after_seconds = (
            summary.repetitions[index + 1].rest_before_seconds
            if index + 1 < captured_count
            else None
        )
        timing_note = f"Elapsed timing calculation: {repetition.formula}."
        notes = f"{timing_note} {repetition.note}" if repetition.note is not None else timing_note
        results.append(
            RepetitionResult(
                block_sequence=summary.block_sequence,
                set_group_sequence=summary.set_group_sequence,
                item_sequence=summary.item_sequence,
                repetition_number=repetition.repetition_number,
                completed=True,
                actual_seconds=repetition.actual_seconds,
                rest_after_seconds=rest_after_seconds,
                notes=notes,
            )
        )

    return tuple(results)
