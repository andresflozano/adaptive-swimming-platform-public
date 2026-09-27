from pathlib import Path

from scripts.export_golden_workout import export_golden_workout

from adaptive_swimming.catalog.reference_workouts import (
    SESSION_ID,
    SOURCE_ID,
    build_reference_workout,
)
from adaptive_swimming.domain.workout import (
    BlockRole,
    EquipmentCode,
    ExerciseCode,
    RestApplication,
    SetType,
    WorkoutSession,
)


def test_golden_workout_reports_partial_swim_duration(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / f"{SESSION_ID}.json"
    workout = export_golden_workout(output_path)
    summary = workout.swim_duration_summary()

    assert summary.known_seconds == 1324
    assert summary.known_distance_meters == 1400
    assert summary.unresolved_distance_meters == 1200
    assert summary.total_distance_meters == 2600
    assert summary.is_complete is False
    assert workout.total_rest_seconds() == 1050


def test_golden_workout_has_1050_configured_rest_seconds(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / f"{SESSION_ID}.json"
    workout = export_golden_workout(output_path)

    assert workout.total_rest_seconds() == 1050
    assert workout.total_distance_meters() == 2600


def test_golden_workout_uses_explicit_rest_semantics(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / f"{SESSION_ID}.json"
    workout = export_golden_workout(output_path)

    repeated_group = workout.blocks[2].set_groups[0]
    ordered_group = workout.blocks[7].set_groups[0]

    assert repeated_group.rest is not None
    assert repeated_group.rest.seconds == 45
    assert repeated_group.rest.application == RestApplication.BETWEEN_REPETITIONS
    assert repeated_group.rest.include_after_final is False

    assert ordered_group.rest is not None
    assert ordered_group.rest.seconds == 30
    assert ordered_group.rest.application == RestApplication.BETWEEN_ITEMS
    assert ordered_group.rest.include_after_final is False


def test_export_golden_workout_round_trips(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / f"{SESSION_ID}.json"

    exported_workout = export_golden_workout(output_path)
    loaded_workout = WorkoutSession.model_validate_json(output_path.read_text(encoding="utf-8"))

    assert output_path.is_file()
    assert exported_workout == build_reference_workout()
    assert loaded_workout == exported_workout
    assert loaded_workout.session_id == SESSION_ID
    assert loaded_workout.source_id == SOURCE_ID
    assert loaded_workout.total_distance_meters() == 2600
    assert len(loaded_workout.blocks) == 8


def test_export_golden_workout_is_deterministic(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / f"{SESSION_ID}.json"

    export_golden_workout(output_path)
    first_export = output_path.read_bytes()

    export_golden_workout(output_path)
    second_export = output_path.read_bytes()

    assert second_export == first_export


def test_golden_workout_preserves_ordered_technical_set(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / f"{SESSION_ID}.json"
    workout = export_golden_workout(output_path)

    technical_group = workout.blocks[7].set_groups[0]

    assert technical_group.set_type == SetType.ORDERED_SEQUENCE
    assert [item.exercise for item in technical_group.items] == [
        ExerciseCode.ASYMMETRIC,
        ExerciseCode.ASYMMETRIC,
        ExerciseCode.UNILATERAL,
        ExerciseCode.UNILATERAL,
        ExerciseCode.FREESTYLE,
    ]
    assert technical_group.items[4].equipment == (
        EquipmentCode.FINS,
        EquipmentCode.PADDLES,
    )


def test_golden_workout_does_not_add_cooldown(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / f"{SESSION_ID}.json"
    workout = export_golden_workout(output_path)

    assert all(block.role != BlockRole.COOL_DOWN for block in workout.blocks)


def test_exported_json_excludes_private_source_fields(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / f"{SESSION_ID}.json"

    export_golden_workout(output_path)
    serialized_workout = output_path.read_text(encoding="utf-8").casefold()

    assert "source_filename" not in serialized_workout
