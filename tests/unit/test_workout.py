import pytest
from pydantic import ValidationError

from adaptive_swimming.catalog.reference_workouts import (
    SOURCE_ID,
    SOURCE_SHA256,
    build_reference_workout,
)
from adaptive_swimming.domain.workout import (
    ExerciseCode,
    RestApplication,
    RestPolicy,
    SessionEnvironment,
    SetGroup,
    SetItem,
    SetType,
    SwimDurationSummary,
    Target,
    TargetType,
    WorkoutSession,
)


def test_set_item_can_omit_swimmer_instruction() -> None:
    item = SetItem(
        sequence=1,
        distance_meters=100,
        exercise=ExerciseCode.FREESTYLE,
        source_text="Synthetic test item.",
    )

    assert item.swimmer_instruction is None


def test_set_item_preserves_swimmer_instruction_in_json() -> None:
    item = SetItem(
        sequence=1,
        distance_meters=100,
        exercise=ExerciseCode.FREESTYLE,
        swimmer_instruction="Record each repetition time.",
        source_text="Synthetic pace-observation item.",
    )

    loaded = SetItem.model_validate_json(item.model_dump_json())

    assert loaded == item
    assert loaded.swimmer_instruction == "Record each repetition time."


def test_targeted_item_has_known_swim_duration() -> None:
    item = SetItem(
        sequence=1,
        repetitions=5,
        distance_meters=100,
        exercise=ExerciseCode.FREESTYLE,
        target=Target(
            target_type=TargetType.REPETITION_COMPLETION_TIME,
            raw_value="1.42",
            target_seconds=102,
        ),
        source_text="5x100 a 1.42",
    )

    summary = item.swim_duration_summary()

    assert summary.known_seconds == 510
    assert summary.known_distance_meters == 500
    assert summary.unresolved_distance_meters == 0
    assert summary.total_distance_meters == 500
    assert summary.is_complete is True


def test_untargeted_item_has_unresolved_swim_duration() -> None:
    item = SetItem(
        sequence=1,
        repetitions=12,
        distance_meters=25,
        exercise=ExerciseCode.KICKBOARD_KICK,
        source_text="12x25 kickboard kick",
    )

    summary = item.swim_duration_summary()

    assert summary.known_seconds == 0
    assert summary.known_distance_meters == 0
    assert summary.unresolved_distance_meters == 300
    assert summary.total_distance_meters == 300
    assert summary.is_complete is False


def test_duration_summary_adds_known_and_unresolved_values() -> None:
    left = SwimDurationSummary(
        known_seconds=510,
        known_distance_meters=500,
        unresolved_distance_meters=200,
    )
    right = SwimDurationSummary(
        known_seconds=152,
        known_distance_meters=200,
        unresolved_distance_meters=300,
    )

    summary = left + right

    assert summary.known_seconds == 662
    assert summary.known_distance_meters == 700
    assert summary.unresolved_distance_meters == 500
    assert summary.total_distance_meters == 1200
    assert summary.is_complete is False


def test_duration_summary_scales_for_repeat_cycles() -> None:
    summary = SwimDurationSummary(
        known_seconds=38,
        known_distance_meters=50,
        unresolved_distance_meters=25,
    )

    scaled = summary.scaled(4)

    assert scaled.known_seconds == 152
    assert scaled.known_distance_meters == 200
    assert scaled.unresolved_distance_meters == 100


def test_duration_summary_rejects_invalid_multiplier() -> None:
    summary = SwimDurationSummary(
        known_seconds=38,
        known_distance_meters=50,
        unresolved_distance_meters=0,
    )

    with pytest.raises(
        ValueError,
        match="Duration summary multiplier must be at least one",
    ):
        summary.scaled(0)


def test_reference_workout_reports_partial_swim_duration() -> None:
    workout = build_reference_workout()
    summary = workout.swim_duration_summary()

    assert summary.known_seconds == 1324
    assert summary.known_distance_meters == 1400
    assert summary.unresolved_distance_meters == 1200
    assert summary.total_distance_meters == 2600
    assert summary.is_complete is False

    assert workout.total_rest_seconds() == 1050
    assert workout.total_distance_meters() == 2600


def test_rest_policy_counts_only_between_units_by_default() -> None:
    rest = RestPolicy(
        seconds=30,
        application=RestApplication.BETWEEN_REPETITIONS,
    )

    assert rest.occurrence_count(1) == 0
    assert rest.occurrence_count(4) == 3


def test_rest_policy_can_include_rest_after_final_unit() -> None:
    rest = RestPolicy(
        seconds=30,
        application=RestApplication.BETWEEN_REPETITIONS,
        include_after_final=True,
    )

    assert rest.occurrence_count(4) == 4


def test_rest_policy_rejects_invalid_unit_count() -> None:
    rest = RestPolicy(
        seconds=30,
        application=RestApplication.BETWEEN_REPETITIONS,
    )

    with pytest.raises(
        ValueError,
        match="Rest unit count must be at least one",
    ):
        rest.occurrence_count(0)


def test_repeated_interval_calculates_rest_between_repetitions() -> None:
    set_group = SetGroup(
        sequence=1,
        set_type=SetType.REPEATED_INTERVAL,
        rest=RestPolicy(
            seconds=45,
            application=RestApplication.BETWEEN_REPETITIONS,
        ),
        items=(
            SetItem(
                sequence=1,
                repetitions=5,
                distance_meters=100,
                exercise=ExerciseCode.FREESTYLE,
                source_text="5x100",
            ),
        ),
        source_text="5x100 con 45 segundos de pausa",
    )

    assert set_group.total_rest_seconds() == 180


def test_ordered_sequence_calculates_rest_between_items() -> None:
    set_group = SetGroup(
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
                exercise=ExerciseCode.UNILATERAL,
                source_text="100 m unilateral technique",
            ),
        ),
        source_text="2x100 técnico",
    )

    assert set_group.total_rest_seconds() == 30


def test_continuous_set_has_zero_rest_seconds() -> None:
    set_group = SetGroup(
        sequence=1,
        set_type=SetType.CONTINUOUS,
        items=(
            SetItem(
                sequence=1,
                distance_meters=200,
                exercise=ExerciseCode.FREESTYLE,
                source_text="200 m easy freestyle",
            ),
        ),
        source_text="200 m easy freestyle",
    )

    assert set_group.total_rest_seconds() == 0


def test_reference_workout_has_1050_rest_seconds() -> None:
    workout = build_reference_workout()

    assert workout.total_rest_seconds() == 1050
    assert workout.total_distance_meters() == 2600


def test_continuous_set_rejects_rest_policy() -> None:
    with pytest.raises(ValidationError):
        SetGroup(
            sequence=1,
            set_type=SetType.CONTINUOUS,
            rest=RestPolicy(
                seconds=30,
                application=RestApplication.BETWEEN_REPETITIONS,
            ),
            items=(
                SetItem(
                    sequence=1,
                    distance_meters=200,
                    exercise=ExerciseCode.FREESTYLE,
                    source_text="200 m easy freestyle",
                ),
            ),
            source_text="200 m easy freestyle",
        )


def test_repeated_interval_requires_repetition_rest_semantics() -> None:
    with pytest.raises(ValidationError):
        SetGroup(
            sequence=1,
            set_type=SetType.REPEATED_INTERVAL,
            rest=RestPolicy(
                seconds=30,
                application=RestApplication.BETWEEN_ITEMS,
            ),
            items=(
                SetItem(
                    sequence=1,
                    repetitions=4,
                    distance_meters=50,
                    exercise=ExerciseCode.FREESTYLE,
                    source_text="4x50",
                ),
            ),
            source_text="4x50 con 30 segundos de pausa",
        )


def test_ordered_sequence_requires_between_item_rest() -> None:
    with pytest.raises(ValidationError):
        SetGroup(
            sequence=1,
            set_type=SetType.ORDERED_SEQUENCE,
            rest=RestPolicy(
                seconds=30,
                application=RestApplication.BETWEEN_REPETITIONS,
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
                    exercise=ExerciseCode.UNILATERAL,
                    source_text="100 m unilateral technique",
                ),
            ),
            source_text="2x100 técnico",
        )


def test_build_reference_workout_total_distance_is_2600_meters() -> None:
    assert build_reference_workout().total_distance_meters() == 2600


def test_build_reference_workout_is_immutable() -> None:
    session = build_reference_workout()

    with pytest.raises(ValidationError):
        session.session_id = "changed"


def test_completion_target_requires_seconds() -> None:
    with pytest.raises(ValidationError):
        Target(
            target_type=TargetType.REPETITION_COMPLETION_TIME,
            raw_value="1.42",
        )


def test_duplicate_block_sequences_are_rejected() -> None:
    session = build_reference_workout()
    duplicate = session.blocks[0].model_copy(update={"sequence": 1})

    with pytest.raises(ValidationError):
        WorkoutSession(
            session_id="invalid",
            environment=SessionEnvironment.POOL,
            source_id=SOURCE_ID,
            source_sha256=SOURCE_SHA256,
            source_section="Synthetic demonstration workout",
            blocks=(session.blocks[0], duplicate),
        )
