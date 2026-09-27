from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from adaptive_swimming.domain.workout import (
    EquipmentCode,
    StrictDomainModel,
    WorkoutSession,
)


def extract_id_version(identifier: str) -> int:
    version_text = identifier.rsplit("_V", maxsplit=1)[1]
    return int(version_text)


class CompletionStatus(StrEnum):
    COMPLETED_AS_WRITTEN = "COMPLETED_AS_WRITTEN"
    COMPLETED_WITH_MODIFICATIONS = "COMPLETED_WITH_MODIFICATIONS"
    STOPPED_EARLY = "STOPPED_EARLY"
    NOT_STARTED = "NOT_STARTED"


class GeneratedWorkout(StrictDomainModel):
    generated_workout_id: str = Field(pattern=r"^GW_[0-9]{8}_[0-9]{3}_V[0-9]+$")
    workout_version: int = Field(ge=1)
    workout: WorkoutSession
    pool_length_meters: float = Field(gt=0)
    available_training_seconds: int | None = Field(
        default=None,
        gt=0,
    )
    equipment_available: tuple[EquipmentCode, ...] = ()
    generation_reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identifier_version(self) -> GeneratedWorkout:
        if extract_id_version(self.generated_workout_id) != self.workout_version:
            raise ValueError("Generated workout ID version must match workout_version.")

        return self

    @property
    def planned_distance_meters(self) -> int:
        return self.workout.total_distance_meters()

    @property
    def configured_rest_seconds(self) -> int:
        return self.workout.total_rest_seconds()

    @property
    def known_swim_seconds(self) -> int:
        return self.workout.swim_duration_summary().known_seconds

    @property
    def unresolved_distance_meters(self) -> int:
        return self.workout.swim_duration_summary().unresolved_distance_meters


class RepetitionResult(StrictDomainModel):
    block_sequence: int = Field(ge=1)
    set_group_sequence: int = Field(ge=1)
    item_sequence: int = Field(ge=1)
    repetition_number: int = Field(ge=1)
    completed: bool = True
    actual_seconds: int | None = Field(
        default=None,
        gt=0,
    )
    rest_after_seconds: int | None = Field(
        default=None,
        ge=0,
    )
    notes: str | None = None

    @model_validator(mode="after")
    def validate_completed_repetition(
        self,
    ) -> RepetitionResult:
        if not self.completed and self.actual_seconds is not None:
            raise ValueError("Incomplete repetitions cannot have an actual time.")

        return self


class BlockResult(StrictDomainModel):
    block_sequence: int = Field(ge=1)
    completed_distance_meters: int = Field(ge=0)
    completed_as_written: bool
    actual_seconds: int | None = Field(
        default=None,
        gt=0,
    )
    repetition_results: tuple[RepetitionResult, ...] = ()
    notes: str | None = None


class WorkoutSessionResult(StrictDomainModel):
    session_result_id: str = Field(pattern=r"^SR_[0-9]{8}_[0-9]{3}_V[0-9]+$")
    generated_workout_id: str = Field(pattern=r"^GW_[0-9]{8}_[0-9]{3}_V[0-9]+$")
    result_version: int = Field(ge=1)
    completion_status: CompletionStatus
    completed_distance_meters: int = Field(ge=0)
    actual_total_seconds: int | None = Field(
        default=None,
        gt=0,
    )
    perceived_exertion: int | None = Field(
        default=None,
        ge=1,
        le=10,
    )
    equipment_used: tuple[EquipmentCode, ...] = ()
    block_results: tuple[BlockResult, ...] = ()
    safety_issue_reported: bool = False
    notes: str | None = None

    @model_validator(mode="after")
    def validate_completion_status(
        self,
    ) -> WorkoutSessionResult:
        if self.completion_status == CompletionStatus.NOT_STARTED:
            if self.completed_distance_meters != 0:
                raise ValueError(
                    "A session that was not started must have zero completed distance."
                )

            if self.actual_total_seconds is not None:
                raise ValueError("A session that was not started cannot have an actual total time.")

            if self.perceived_exertion is not None:
                raise ValueError("A session that was not started cannot have perceived exertion.")

            if self.equipment_used:
                raise ValueError("A session that was not started cannot have equipment used.")

            if self.block_results:
                raise ValueError("A session that was not started cannot have block results.")

        if extract_id_version(self.session_result_id) != self.result_version:
            raise ValueError("Session result ID version must match result_version.")

        return self


def validate_session_result(
    generated_workout: GeneratedWorkout,
    session_result: WorkoutSessionResult,
) -> None:
    if session_result.generated_workout_id != generated_workout.generated_workout_id:
        raise ValueError("Session result does not belong to the generated workout.")

    if session_result.completed_distance_meters > generated_workout.planned_distance_meters:
        raise ValueError("Completed distance cannot exceed planned distance.")

    if (
        session_result.completion_status == CompletionStatus.COMPLETED_AS_WRITTEN
        and session_result.completed_distance_meters != generated_workout.planned_distance_meters
    ):
        raise ValueError("A session completed as written must match the planned distance.")

    unavailable_equipment = set(session_result.equipment_used) - set(
        generated_workout.equipment_available
    )

    if unavailable_equipment:
        raise ValueError("Equipment used must be included in equipment available.")

    planned_blocks = {block.sequence: block for block in generated_workout.workout.blocks}
    observed_block_sequences = [
        block_result.block_sequence for block_result in session_result.block_results
    ]

    if len(observed_block_sequences) != len(set(observed_block_sequences)):
        raise ValueError("Block results cannot contain duplicate sequences.")

    unknown_sequences = set(observed_block_sequences) - set(planned_blocks)

    if unknown_sequences:
        raise ValueError("Block results contain unknown block sequences.")

    reported_distance = 0
    repetition_coordinates: set[tuple[int, int, int, int]] = set()

    for block_result in session_result.block_results:
        planned_block = planned_blocks[block_result.block_sequence]

        if block_result.completed_distance_meters > planned_block.total_distance_meters():
            raise ValueError("Completed block distance cannot exceed planned block distance.")

        reported_distance += block_result.completed_distance_meters

        planned_groups = {set_group.sequence: set_group for set_group in planned_block.set_groups}

        for repetition_result in block_result.repetition_results:
            if repetition_result.block_sequence != block_result.block_sequence:
                raise ValueError(
                    "Repetition result block sequence must match its parent block result."
                )

            set_group = planned_groups.get(repetition_result.set_group_sequence)

            if set_group is None:
                raise ValueError("Repetition result references an unknown set group.")

            planned_items = {item.sequence: item for item in set_group.items}
            item = planned_items.get(repetition_result.item_sequence)

            if item is None:
                raise ValueError("Repetition result references an unknown item.")

            if repetition_result.repetition_number > item.repetitions:
                raise ValueError("Repetition result exceeds planned repetition count.")

            coordinate = (
                repetition_result.block_sequence,
                repetition_result.set_group_sequence,
                repetition_result.item_sequence,
                repetition_result.repetition_number,
            )

            if coordinate in repetition_coordinates:
                raise ValueError("Repetition results cannot contain duplicate coordinates.")

            repetition_coordinates.add(coordinate)

    if reported_distance > session_result.completed_distance_meters:
        raise ValueError("Reported block distance cannot exceed session completed distance.")

    all_blocks_reported = set(observed_block_sequences) == set(planned_blocks)

    if all_blocks_reported and reported_distance != session_result.completed_distance_meters:
        raise ValueError("Complete block results must reconcile to session completed distance.")

    if (
        session_result.completion_status == CompletionStatus.COMPLETED_AS_WRITTEN
        and session_result.block_results
    ):
        if not all_blocks_reported:
            raise ValueError(
                "A session completed as written must report "
                "every block when block results are provided."
            )

        if not all(
            block_result.completed_as_written for block_result in session_result.block_results
        ):
            raise ValueError(
                "A session completed as written cannot contain modified block results."
            )
