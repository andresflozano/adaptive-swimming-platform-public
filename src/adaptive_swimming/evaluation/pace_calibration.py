from __future__ import annotations

from collections import defaultdict
from statistics import mean, median

from pydantic import Field

from adaptive_swimming.domain.session_results import (
    CompletionStatus,
    GeneratedWorkout,
    WorkoutSessionResult,
    validate_session_result,
)
from adaptive_swimming.domain.workout import (
    EquipmentCode,
    ExerciseCode,
    IntensityCode,
    StrictDomainModel,
)


class PaceObservationKey(StrictDomainModel):
    exercise: ExerciseCode
    distance_meters: int = Field(gt=0)
    equipment: tuple[EquipmentCode, ...] = ()
    intensity: IntensityCode


class PaceObservation(StrictDomainModel):
    generated_workout_id: str
    session_result_id: str
    block_sequence: int = Field(ge=1)
    set_group_sequence: int = Field(ge=1)
    item_sequence: int = Field(ge=1)
    repetition_number: int = Field(ge=1)
    key: PaceObservationKey
    actual_seconds: int = Field(gt=0)


class ProvisionalPaceSummary(StrictDomainModel):
    key: PaceObservationKey
    sample_count: int = Field(ge=1)
    minimum_seconds: int = Field(gt=0)
    maximum_seconds: int = Field(gt=0)
    mean_seconds: float = Field(gt=0)
    median_seconds: float = Field(gt=0)
    observations: tuple[PaceObservation, ...] = Field(min_length=1)
    provisional: bool = True
    limitations: tuple[str, ...] = Field(min_length=1)


GroupingKey = tuple[
    ExerciseCode,
    int,
    tuple[EquipmentCode, ...],
    IntensityCode,
]


def extract_pace_observations(
    generated_workout: GeneratedWorkout,
    session_result: WorkoutSessionResult,
) -> tuple[PaceObservation, ...]:
    validate_session_result(generated_workout, session_result)

    if session_result.completion_status == CompletionStatus.NOT_STARTED:
        raise ValueError("Cannot extract pace observations from a NOT_STARTED session result.")

    if session_result.safety_issue_reported:
        raise ValueError(
            "Cannot extract pace observations from a session result with a reported safety issue."
        )

    planned_items = {
        (block.sequence, group.sequence, item.sequence): item
        for block in generated_workout.workout.blocks
        for group in block.set_groups
        for item in group.items
    }

    observations: list[PaceObservation] = []

    for block_result in session_result.block_results:
        for repetition in block_result.repetition_results:
            if not repetition.completed or repetition.actual_seconds is None:
                continue

            coordinate = (
                repetition.block_sequence,
                repetition.set_group_sequence,
                repetition.item_sequence,
            )
            item = planned_items[coordinate]

            observations.append(
                PaceObservation(
                    generated_workout_id=(generated_workout.generated_workout_id),
                    session_result_id=session_result.session_result_id,
                    block_sequence=repetition.block_sequence,
                    set_group_sequence=repetition.set_group_sequence,
                    item_sequence=repetition.item_sequence,
                    repetition_number=repetition.repetition_number,
                    key=PaceObservationKey(
                        exercise=item.exercise,
                        distance_meters=item.distance_meters,
                        equipment=item.equipment,
                        intensity=item.intensity,
                    ),
                    actual_seconds=repetition.actual_seconds,
                )
            )

    return tuple(observations)


def summarize_pace_observations(
    observations: tuple[PaceObservation, ...],
) -> tuple[ProvisionalPaceSummary, ...]:
    grouped: dict[GroupingKey, list[PaceObservation]] = defaultdict(list)

    for observation in observations:
        key = observation.key
        grouping_key = (
            key.exercise,
            key.distance_meters,
            key.equipment,
            key.intensity,
        )
        grouped[grouping_key].append(observation)

    summaries: list[ProvisionalPaceSummary] = []

    for grouping_key in sorted(
        grouped,
        key=lambda value: (
            value[0].value,
            value[1],
            tuple(equipment.value for equipment in value[2]),
            value[3].value,
        ),
    ):
        group = sorted(
            grouped[grouping_key],
            key=lambda observation: (
                observation.session_result_id,
                observation.block_sequence,
                observation.set_group_sequence,
                observation.item_sequence,
                observation.repetition_number,
            ),
        )
        values = [observation.actual_seconds for observation in group]
        exercise, distance, equipment, intensity = grouping_key

        summaries.append(
            ProvisionalPaceSummary(
                key=PaceObservationKey(
                    exercise=exercise,
                    distance_meters=distance,
                    equipment=equipment,
                    intensity=intensity,
                ),
                sample_count=len(values),
                minimum_seconds=min(values),
                maximum_seconds=max(values),
                mean_seconds=mean(values),
                median_seconds=median(values),
                observations=tuple(group),
                provisional=True,
                limitations=(
                    "Summary is descriptive and does not define a mandatory target.",
                    "Evidence is limited to the supplied completed session results.",
                    "Different workout structures and preceding workloads may affect pace.",
                ),
            )
        )

    return tuple(summaries)


def calibrate_pace_from_sessions(
    sessions: tuple[
        tuple[GeneratedWorkout, WorkoutSessionResult],
        ...,
    ],
) -> tuple[ProvisionalPaceSummary, ...]:
    observations = tuple(
        observation
        for generated_workout, session_result in sessions
        for observation in extract_pace_observations(
            generated_workout,
            session_result,
        )
    )
    return summarize_pace_observations(observations)
