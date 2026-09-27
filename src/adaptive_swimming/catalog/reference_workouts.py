from __future__ import annotations

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
    Target,
    TargetType,
    WorkoutBlock,
    WorkoutSession,
)

SOURCE_ID = "SRC_8C962466BDCC"
SOURCE_SHA256 = "8c962466bdcc1efa53f61787f84e6b6a216c4c5e6d0939520baa2d61d372b008"
SESSION_ID = "WT_SRC_8C962466BDCC_POOL_D01_V1"


def interval_group(
    *,
    sequence: int,
    repetitions: int,
    distance_meters: int,
    rest_seconds: int,
    source_text: str,
    exercise: ExerciseCode = ExerciseCode.FREESTYLE,
    intensity: IntensityCode = IntensityCode.UNRESOLVED,
    equipment: tuple[EquipmentCode, ...] = (),
    target: Target | None = None,
) -> SetGroup:
    return SetGroup(
        sequence=sequence,
        set_type=SetType.REPEATED_INTERVAL,
        rest=RestPolicy(
            seconds=rest_seconds,
            application=RestApplication.BETWEEN_REPETITIONS,
        ),
        items=(
            SetItem(
                sequence=1,
                repetitions=repetitions,
                distance_meters=distance_meters,
                exercise=exercise,
                intensity=intensity,
                equipment=equipment,
                target=target,
                source_text=source_text,
            ),
        ),
        source_text=source_text,
    )


def build_reference_workout() -> WorkoutSession:
    target_102 = Target(
        target_type=TargetType.REPETITION_COMPLETION_TIME,
        raw_value="1.42",
        target_seconds=102,
    )
    target_38 = Target(
        target_type=TargetType.REPETITION_COMPLETION_TIME,
        raw_value="38",
        target_seconds=38,
    )

    blocks = (
        WorkoutBlock(
            sequence=1,
            role=BlockRole.WARM_UP,
            provenance_type=ProvenanceType.SOURCE_EXPLICIT,
            source_text="200 m easy freestyle",
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
                            source_text="200 m easy freestyle",
                        ),
                    ),
                    source_text="200 m easy freestyle",
                ),
            ),
        ),
        WorkoutBlock(
            sequence=2,
            role=BlockRole.PREPARATION,
            provenance_type=ProvenanceType.SOURCE_EXPLICIT,
            source_text="2 x 100 m technique with inverted paddles, 60 s rest",
            set_groups=(
                interval_group(
                    sequence=1,
                    repetitions=2,
                    distance_meters=100,
                    rest_seconds=60,
                    equipment=(EquipmentCode.PADDLES_INVERTED,),
                    source_text="2 x 100 m technique with inverted paddles, 60 s rest",
                ),
            ),
        ),
        WorkoutBlock(
            sequence=3,
            role=BlockRole.MAIN_SET,
            provenance_type=ProvenanceType.SOURCE_EXPLICIT,
            source_text="5 x 100 m freestyle, 45 s rest, target 102 s",
            set_groups=(
                interval_group(
                    sequence=1,
                    repetitions=5,
                    distance_meters=100,
                    rest_seconds=45,
                    target=target_102,
                    source_text="5 x 100 m freestyle, 45 s rest, target 102 s",
                ),
            ),
        ),
        WorkoutBlock(
            sequence=4,
            role=BlockRole.MAIN_SET,
            provenance_type=ProvenanceType.SOURCE_EXPLICIT,
            source_text="4 x 50 m freestyle with fins, 30 s rest, target 38 s",
            set_groups=(
                interval_group(
                    sequence=1,
                    repetitions=4,
                    distance_meters=50,
                    rest_seconds=30,
                    equipment=(EquipmentCode.FINS,),
                    target=target_38,
                    source_text="4 x 50 m freestyle with fins, 30 s rest, target 38 s",
                ),
            ),
        ),
        WorkoutBlock(
            sequence=5,
            role=BlockRole.MAIN_SET,
            provenance_type=ProvenanceType.SOURCE_EXPLICIT,
            source_text="5 x 100 m freestyle, 45 s rest, target 102 s",
            set_groups=(
                interval_group(
                    sequence=1,
                    repetitions=5,
                    distance_meters=100,
                    rest_seconds=45,
                    target=target_102,
                    source_text="5 x 100 m freestyle, 45 s rest, target 102 s",
                ),
            ),
        ),
        WorkoutBlock(
            sequence=6,
            role=BlockRole.MAIN_SET,
            provenance_type=ProvenanceType.SOURCE_EXPLICIT,
            source_text="4 x 50 m freestyle with fins, 30 s rest, target 38 s",
            set_groups=(
                interval_group(
                    sequence=1,
                    repetitions=4,
                    distance_meters=50,
                    rest_seconds=30,
                    equipment=(EquipmentCode.FINS,),
                    target=target_38,
                    source_text="4 x 50 m freestyle with fins, 30 s rest, target 38 s",
                ),
            ),
        ),
        WorkoutBlock(
            sequence=7,
            role=BlockRole.TECHNIQUE,
            provenance_type=ProvenanceType.SOURCE_EXPLICIT,
            source_text="12 x 25 m kickboard kick, 30 s rest",
            set_groups=(
                interval_group(
                    sequence=1,
                    repetitions=12,
                    distance_meters=25,
                    rest_seconds=30,
                    exercise=ExerciseCode.KICKBOARD_KICK,
                    equipment=(EquipmentCode.KICKBOARD,),
                    source_text="12 x 25 m kickboard kick, 30 s rest",
                ),
            ),
        ),
        WorkoutBlock(
            sequence=8,
            role=BlockRole.TECHNIQUE,
            provenance_type=ProvenanceType.SOURCE_EXPLICIT,
            source_text="5 x 100 m ordered technique, 30 s rest",
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
                            source_text="100 m asymmetric technique",
                        ),
                        SetItem(
                            sequence=2,
                            distance_meters=100,
                            exercise=ExerciseCode.ASYMMETRIC,
                            source_text="100 m asymmetric technique",
                        ),
                        SetItem(
                            sequence=3,
                            distance_meters=100,
                            exercise=ExerciseCode.UNILATERAL,
                            source_text="100 m unilateral technique",
                        ),
                        SetItem(
                            sequence=4,
                            distance_meters=100,
                            exercise=ExerciseCode.UNILATERAL,
                            source_text="100 m unilateral technique",
                        ),
                        SetItem(
                            sequence=5,
                            distance_meters=100,
                            exercise=ExerciseCode.FREESTYLE,
                            equipment=(EquipmentCode.FINS, EquipmentCode.PADDLES),
                            source_text="100 m freestyle with fins and paddles",
                        ),
                    ),
                    source_text="5 x 100 m ordered technique, 30 s rest",
                ),
            ),
        ),
    )

    return WorkoutSession(
        session_id=SESSION_ID,
        environment=SessionEnvironment.POOL,
        source_id=SOURCE_ID,
        source_sha256=SOURCE_SHA256,
        source_section="Synthetic demonstration workout",
        blocks=blocks,
    )
