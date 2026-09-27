from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from adaptive_swimming.domain.session_results import (
    GeneratedWorkout,
    WorkoutSessionResult,
    validate_session_result,
)
from adaptive_swimming.domain.workout import (
    BlockRole,
    EquipmentCode,
    ExerciseCode,
    IntensityCode,
    ProvenanceType,
    RestApplication,
    RestPolicy,
    SessionEnvironment,
    SetGroup,
    SetItem,
    SetType,
    StrictDomainModel,
    WorkoutBlock,
    WorkoutSession,
)
from adaptive_swimming.planning.time_feasibility import (
    WorkoutTimeFeasibility,
    evaluate_time_feasibility,
)


class ProposalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class AdaptationTraceEntry(StrictDomainModel):
    rule_id: str = Field(min_length=1)
    description: str = Field(min_length=1)


class NextWorkoutProposal(StrictDomainModel):
    proposal_id: str = Field(pattern=r"^NWP_[0-9]{8}_[0-9]{3}_V[0-9]+$")
    proposal_version: int = Field(ge=1)
    parent_generated_workout_id: str
    previous_session_result_id: str
    status: ProposalStatus = ProposalStatus.PROPOSED
    proposed_generated_workout: GeneratedWorkout
    adaptation_trace: tuple[AdaptationTraceEntry, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_proposal_state(self) -> NextWorkoutProposal:
        if self.status != ProposalStatus.PROPOSED:
            raise ValueError("New workout proposals must initially be PROPOSED.")

        if self.proposed_generated_workout.generated_workout_id == self.parent_generated_workout_id:
            raise ValueError("Proposed workout must use a new generated-workout ID.")

        return self

    @property
    def time_feasibility(self) -> WorkoutTimeFeasibility:
        return evaluate_time_feasibility(self.proposed_generated_workout)


def generated_text(instruction: str) -> str:
    return f"Engine proposal: {instruction}"


def build_pool_test_two_workout() -> WorkoutSession:
    blocks = (
        WorkoutBlock(
            sequence=1,
            role=BlockRole.WARM_UP,
            provenance_type=ProvenanceType.ENGINE_ADDED,
            source_text=generated_text("200 m recovery freestyle"),
            set_groups=(
                SetGroup(
                    sequence=1,
                    set_type=SetType.CONTINUOUS,
                    items=(
                        SetItem(
                            sequence=1,
                            distance_meters=200,
                            exercise=ExerciseCode.FREESTYLE,
                            intensity=IntensityCode.RECOVERY,
                            source_text=generated_text("200 m recovery freestyle"),
                        ),
                    ),
                    source_text=generated_text("200 m recovery freestyle"),
                ),
            ),
        ),
        WorkoutBlock(
            sequence=2,
            role=BlockRole.PREPARATION,
            provenance_type=ProvenanceType.ENGINE_ADDED,
            source_text=generated_text("2 x 100 m inverted-grip paddles"),
            set_groups=(
                SetGroup(
                    sequence=1,
                    set_type=SetType.REPEATED_INTERVAL,
                    rest=RestPolicy(
                        seconds=60,
                        application=(RestApplication.BETWEEN_REPETITIONS),
                    ),
                    items=(
                        SetItem(
                            sequence=1,
                            repetitions=2,
                            distance_meters=100,
                            exercise=ExerciseCode.FREESTYLE,
                            equipment=(EquipmentCode.PADDLES_INVERTED,),
                            source_text=generated_text("2 x 100 m inverted-grip paddles"),
                        ),
                    ),
                    source_text=generated_text("2 x 100 m inverted-grip paddles"),
                ),
            ),
        ),
        WorkoutBlock(
            sequence=3,
            role=BlockRole.MAIN_SET,
            provenance_type=ProvenanceType.ENGINE_ADDED,
            source_text=generated_text("3 x 100 m freestyle without fixed target"),
            set_groups=(
                SetGroup(
                    sequence=1,
                    set_type=SetType.REPEATED_INTERVAL,
                    rest=RestPolicy(
                        seconds=45,
                        application=(RestApplication.BETWEEN_REPETITIONS),
                    ),
                    items=(
                        SetItem(
                            sequence=1,
                            repetitions=3,
                            distance_meters=100,
                            exercise=ExerciseCode.FREESTYLE,
                            intensity=IntensityCode.AEROBIC,
                            target=None,
                            swimmer_instruction="Record each repetition time.",
                            source_text=generated_text("3 x 100 m freestyle, record pace"),
                        ),
                    ),
                    source_text=generated_text("3 x 100 m freestyle, 45 sec rest"),
                ),
            ),
        ),
        WorkoutBlock(
            sequence=4,
            role=BlockRole.MAIN_SET,
            provenance_type=ProvenanceType.ENGINE_ADDED,
            source_text=generated_text("4 x 50 m freestyle with fins"),
            set_groups=(
                SetGroup(
                    sequence=1,
                    set_type=SetType.REPEATED_INTERVAL,
                    rest=RestPolicy(
                        seconds=30,
                        application=(RestApplication.BETWEEN_REPETITIONS),
                    ),
                    items=(
                        SetItem(
                            sequence=1,
                            repetitions=4,
                            distance_meters=50,
                            exercise=ExerciseCode.FREESTYLE,
                            equipment=(EquipmentCode.FINS,),
                            target=None,
                            swimmer_instruction="Record each repetition time.",
                            source_text=generated_text("4 x 50 m with fins, record pace"),
                        ),
                    ),
                    source_text=generated_text("4 x 50 m with fins, 30 sec rest"),
                ),
            ),
        ),
        WorkoutBlock(
            sequence=5,
            role=BlockRole.TECHNIQUE,
            provenance_type=ProvenanceType.ENGINE_ADDED,
            source_text=generated_text("8 x 25 m kickboard"),
            set_groups=(
                SetGroup(
                    sequence=1,
                    set_type=SetType.REPEATED_INTERVAL,
                    rest=RestPolicy(
                        seconds=30,
                        application=(RestApplication.BETWEEN_REPETITIONS),
                    ),
                    items=(
                        SetItem(
                            sequence=1,
                            repetitions=8,
                            distance_meters=25,
                            exercise=ExerciseCode.KICKBOARD_KICK,
                            equipment=(EquipmentCode.KICKBOARD,),
                            source_text=generated_text("8 x 25 m kickboard"),
                        ),
                    ),
                    source_text=generated_text("8 x 25 m kickboard, 30 sec rest"),
                ),
            ),
        ),
        WorkoutBlock(
            sequence=6,
            role=BlockRole.TECHNIQUE,
            provenance_type=ProvenanceType.ENGINE_ADDED,
            source_text=generated_text("400 m ordered technique and easy finish"),
            set_groups=(
                SetGroup(
                    sequence=1,
                    set_type=SetType.ORDERED_SEQUENCE,
                    rest=RestPolicy(
                        seconds=30,
                        application=RestApplication.BETWEEN_ITEMS,
                    ),
                    items=(
                        SetItem(
                            sequence=1,
                            distance_meters=100,
                            exercise=ExerciseCode.ASYMMETRIC,
                            source_text=generated_text("100 m asymmetric"),
                        ),
                        SetItem(
                            sequence=2,
                            distance_meters=100,
                            exercise=ExerciseCode.UNILATERAL,
                            source_text=generated_text("100 m unilateral"),
                        ),
                        SetItem(
                            sequence=3,
                            distance_meters=100,
                            exercise=ExerciseCode.FREESTYLE,
                            equipment=(EquipmentCode.FINS,),
                            source_text=generated_text("100 m freestyle with fins"),
                        ),
                        SetItem(
                            sequence=4,
                            distance_meters=100,
                            exercise=ExerciseCode.FREESTYLE,
                            intensity=IntensityCode.RECOVERY,
                            source_text=generated_text("100 m recovery freestyle"),
                        ),
                    ),
                    source_text=generated_text("400 m ordered technique and easy finish"),
                ),
            ),
        ),
    )

    return WorkoutSession(
        session_id="WT_ENGINE_POOL_TEST_002_V1",
        environment=SessionEnvironment.POOL,
        source_id="SRC_8C962466BDCC",
        source_sha256=("8c962466bdcc1efa53f61787f84e6b6a216c4c5e6d0939520baa2d61d372b008"),
        source_section=generated_text("Pool Test 2, 60-minute proposal"),
        blocks=blocks,
    )


def build_pool_test_two_proposal(
    parent_generated_workout: GeneratedWorkout,
    previous_result: WorkoutSessionResult,
) -> NextWorkoutProposal:
    validate_session_result(
        parent_generated_workout,
        previous_result,
    )

    proposed_workout = build_pool_test_two_workout()

    generated = GeneratedWorkout(
        generated_workout_id="GW_20260903_001_V1",
        workout_version=1,
        workout=proposed_workout,
        pool_length_meters=12.5,
        available_training_seconds=3600,
        equipment_available=(
            EquipmentCode.FINS,
            EquipmentCode.PADDLES,
            EquipmentCode.KICKBOARD,
        ),
        generation_reason=("POOL_TEST_2_TIME_CONSTRAINED_PROPOSAL"),
    )

    return NextWorkoutProposal(
        proposal_id="NWP_20260903_001_V1",
        proposal_version=1,
        parent_generated_workout_id=(parent_generated_workout.generated_workout_id),
        previous_session_result_id=(previous_result.session_result_id),
        status=ProposalStatus.PROPOSED,
        proposed_generated_workout=generated,
        adaptation_trace=(
            AdaptationTraceEntry(
                rule_id="TIME_BUDGET_60_MINUTES",
                description=("Set the available training time to 60 minutes."),
            ),
            AdaptationTraceEntry(
                rule_id="BASELINE_COMPLETION_EVIDENCE",
                description=("Pool Test 1 recorded 1,100 m in 45 minutes."),
            ),
            AdaptationTraceEntry(
                rule_id="REDUCE_PLANNED_DISTANCE",
                description=("Reduced planned distance from 2,600 m to 1,500 m."),
            ),
            AdaptationTraceEntry(
                rule_id="REDUCE_REPETITIVE_STRUCTURE",
                description=("Removed the repeated second 100 m and 50 m main-set sequence."),
            ),
            AdaptationTraceEntry(
                rule_id="PACE_CALIBRATION_REQUIRED",
                description=(
                    "Removed fixed completion targets and will "
                    "record actual pace during Pool Test 2."
                ),
            ),
            AdaptationTraceEntry(
                rule_id="PRESERVE_REST",
                description=("Preserved comparable rest durations."),
            ),
        ),
        limitations=(
            ("Proposal is based on one formally recorded pool session."),
            ("Untargeted swim duration and transition time remain unresolved."),
            ("The proposed 1,500 m distance is not yet validated in the pool."),
            ("No validated progression or target-calibration rule exists yet."),
        ),
    )
