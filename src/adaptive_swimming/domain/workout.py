from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from adaptive_swimming.domain.source_identity import SOURCE_ID_PATTERN


class StrictDomainModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class SessionEnvironment(StrEnum):
    POOL = "POOL"
    OPEN_WATER = "OPEN_WATER"


class BlockRole(StrEnum):
    WARM_UP = "WARM_UP"
    PREPARATION = "PREPARATION"
    MAIN_SET = "MAIN_SET"
    TECHNIQUE = "TECHNIQUE"
    COOL_DOWN = "COOL_DOWN"


class SetType(StrEnum):
    REPEATED_INTERVAL = "REPEATED_INTERVAL"
    ORDERED_SEQUENCE = "ORDERED_SEQUENCE"
    CONTINUOUS = "CONTINUOUS"


class RestApplication(StrEnum):
    BETWEEN_REPETITIONS = "BETWEEN_REPETITIONS"
    BETWEEN_ITEMS = "BETWEEN_ITEMS"
    BETWEEN_CYCLES = "BETWEEN_CYCLES"


class ExerciseCode(StrEnum):
    FREESTYLE = "FREESTYLE"
    ASYMMETRIC = "ASYMMETRIC"
    UNILATERAL = "UNILATERAL"
    KICKBOARD_KICK = "KICKBOARD_KICK"


class EquipmentCode(StrEnum):
    FINS = "FINS"
    PADDLES = "PADDLES"
    PADDLES_INVERTED = "PADDLES_INVERTED"
    KICKBOARD = "KICKBOARD"


class IntensityCode(StrEnum):
    RECOVERY = "RECOVERY"
    AEROBIC = "AEROBIC"
    SUPER_AEROBIC = "SUPER_AEROBIC"
    AEROBIC_MEDIUM = "AEROBIC_MEDIUM"
    MVO2 = "MVO2"
    LACTATE_RESISTANCE = "LACTATE_RESISTANCE"
    MAXIMUM = "MAXIMUM"
    UNRESOLVED = "UNRESOLVED"


class TargetType(StrEnum):
    REPETITION_COMPLETION_TIME = "REPETITION_COMPLETION_TIME"
    UNRESOLVED = "UNRESOLVED"


class ProvenanceType(StrEnum):
    SOURCE_EXPLICIT = "SOURCE_EXPLICIT"
    SOURCE_INFERRED = "SOURCE_INFERRED"
    ENGINE_ADDED = "ENGINE_ADDED"


class Target(StrictDomainModel):
    target_type: TargetType
    raw_value: str
    target_seconds: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_target_seconds(self) -> Target:
        if (
            self.target_type == TargetType.REPETITION_COMPLETION_TIME
            and self.target_seconds is None
        ):
            raise ValueError("Repetition completion targets require target_seconds.")

        if self.target_type == TargetType.UNRESOLVED and self.target_seconds is not None:
            raise ValueError("Unresolved targets cannot contain target_seconds.")

        return self


class RestPolicy(StrictDomainModel):
    seconds: int = Field(gt=0)
    application: RestApplication
    include_after_final: bool = False

    def occurrence_count(self, unit_count: int) -> int:
        if unit_count < 1:
            raise ValueError("Rest unit count must be at least one.")

        if self.include_after_final:
            return unit_count

        return unit_count - 1


class SwimDurationSummary(StrictDomainModel):
    known_seconds: int = Field(ge=0)
    known_distance_meters: int = Field(ge=0)
    unresolved_distance_meters: int = Field(ge=0)

    @property
    def is_complete(self) -> bool:
        return self.unresolved_distance_meters == 0

    @property
    def total_distance_meters(self) -> int:
        return self.known_distance_meters + self.unresolved_distance_meters

    def scaled(self, multiplier: int) -> SwimDurationSummary:
        if multiplier < 1:
            raise ValueError("Duration summary multiplier must be at least one.")

        return SwimDurationSummary(
            known_seconds=self.known_seconds * multiplier,
            known_distance_meters=(self.known_distance_meters * multiplier),
            unresolved_distance_meters=(self.unresolved_distance_meters * multiplier),
        )

    def __add__(
        self,
        other: SwimDurationSummary,
    ) -> SwimDurationSummary:
        return SwimDurationSummary(
            known_seconds=(self.known_seconds + other.known_seconds),
            known_distance_meters=(self.known_distance_meters + other.known_distance_meters),
            unresolved_distance_meters=(
                self.unresolved_distance_meters + other.unresolved_distance_meters
            ),
        )


def empty_swim_duration_summary() -> SwimDurationSummary:
    return SwimDurationSummary(
        known_seconds=0,
        known_distance_meters=0,
        unresolved_distance_meters=0,
    )


class SetItem(StrictDomainModel):
    sequence: int = Field(ge=1)
    repetitions: int = Field(default=1, ge=1)
    distance_meters: int = Field(ge=25)
    exercise: ExerciseCode
    intensity: IntensityCode = IntensityCode.UNRESOLVED
    equipment: tuple[EquipmentCode, ...] = ()
    target: Target | None = None
    swimmer_instruction: str | None = None
    source_text: str

    def swim_duration_summary(self) -> SwimDurationSummary:
        total_distance = self.repetitions * self.distance_meters

        if (
            self.target is None
            or self.target.target_type != TargetType.REPETITION_COMPLETION_TIME
            or self.target.target_seconds is None
        ):
            return SwimDurationSummary(
                known_seconds=0,
                known_distance_meters=0,
                unresolved_distance_meters=total_distance,
            )

        return SwimDurationSummary(
            known_seconds=(self.repetitions * self.target.target_seconds),
            known_distance_meters=total_distance,
            unresolved_distance_meters=0,
        )


class SetGroup(StrictDomainModel):
    sequence: int = Field(ge=1)
    set_type: SetType
    repeat_cycles: int = Field(default=1, ge=1)
    rest: RestPolicy | None = None
    items: tuple[SetItem, ...] = Field(min_length=1)
    source_text: str

    @model_validator(mode="after")
    def validate_set_shape(self) -> SetGroup:
        if self.set_type == SetType.CONTINUOUS and len(self.items) != 1:
            raise ValueError("Continuous sets must contain exactly one item.")

        if self.set_type == SetType.REPEATED_INTERVAL and len(self.items) != 1:
            raise ValueError("Repeated interval sets must contain exactly one item.")

        if self.set_type == SetType.CONTINUOUS and self.rest is not None:
            raise ValueError("Continuous sets cannot define a rest policy.")

        if (
            self.set_type == SetType.REPEATED_INTERVAL
            and self.rest is not None
            and self.rest.application != RestApplication.BETWEEN_REPETITIONS
        ):
            raise ValueError("Repeated interval rest must apply between repetitions.")

        if (
            self.set_type == SetType.ORDERED_SEQUENCE
            and self.rest is not None
            and self.rest.application != RestApplication.BETWEEN_ITEMS
        ):
            raise ValueError("Ordered sequence rest must apply between items.")

        return self

    def swim_duration_summary(self) -> SwimDurationSummary:
        summary = empty_swim_duration_summary()

        for item in self.items:
            summary += item.swim_duration_summary()

        return summary.scaled(self.repeat_cycles)

    def total_rest_seconds(self) -> int:
        if self.rest is None:
            return 0

        if self.rest.application == RestApplication.BETWEEN_REPETITIONS:
            occurrences_per_cycle = sum(
                self.rest.occurrence_count(item.repetitions) for item in self.items
            )
            return self.repeat_cycles * occurrences_per_cycle * self.rest.seconds

        if self.rest.application == RestApplication.BETWEEN_ITEMS:
            occurrences_per_cycle = self.rest.occurrence_count(len(self.items))
            return self.repeat_cycles * occurrences_per_cycle * self.rest.seconds

        if self.rest.application == RestApplication.BETWEEN_CYCLES:
            occurrences = self.rest.occurrence_count(self.repeat_cycles)
            return occurrences * self.rest.seconds

        raise ValueError(f"Unsupported rest application: {self.rest.application}")

    def total_distance_meters(self) -> int:
        cycle_distance = sum(item.repetitions * item.distance_meters for item in self.items)
        return self.repeat_cycles * cycle_distance


class WorkoutBlock(StrictDomainModel):
    sequence: int = Field(ge=1)
    role: BlockRole
    set_groups: tuple[SetGroup, ...] = Field(min_length=1)
    provenance_type: ProvenanceType
    source_text: str

    def total_distance_meters(self) -> int:
        return sum(set_group.total_distance_meters() for set_group in self.set_groups)

    def swim_duration_summary(self) -> SwimDurationSummary:
        summary = empty_swim_duration_summary()

        for set_group in self.set_groups:
            summary += set_group.swim_duration_summary()

        return summary

    def total_rest_seconds(self) -> int:
        return sum(set_group.total_rest_seconds() for set_group in self.set_groups)


class WorkoutSession(StrictDomainModel):
    session_id: str
    environment: SessionEnvironment
    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_section: str
    blocks: tuple[WorkoutBlock, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_sequences(self) -> WorkoutSession:
        block_sequences = [block.sequence for block in self.blocks]

        if len(block_sequences) != len(set(block_sequences)):
            raise ValueError("Block sequences must be unique.")

        for block in self.blocks:
            set_group_sequences = [set_group.sequence for set_group in block.set_groups]

            if len(set_group_sequences) != len(set(set_group_sequences)):
                raise ValueError("Set group sequences must be unique within a block.")

            for set_group in block.set_groups:
                item_sequences = [item.sequence for item in set_group.items]

                if len(item_sequences) != len(set(item_sequences)):
                    raise ValueError("Set item sequences must be unique within a set group.")

        return self

    def total_distance_meters(self) -> int:
        return sum(block.total_distance_meters() for block in self.blocks)

    def swim_duration_summary(self) -> SwimDurationSummary:
        summary = empty_swim_duration_summary()

        for block in self.blocks:
            summary += block.swim_duration_summary()

        return summary

    def total_rest_seconds(self) -> int:
        return sum(block.total_rest_seconds() for block in self.blocks)
