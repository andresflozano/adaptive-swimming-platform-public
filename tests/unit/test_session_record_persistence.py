from pathlib import Path

import pytest

from adaptive_swimming.catalog.reference_workouts import (
    build_reference_workout,
)
from adaptive_swimming.domain.session_results import (
    CompletionStatus,
    GeneratedWorkout,
    WorkoutSessionResult,
)
from adaptive_swimming.domain.workout import EquipmentCode
from adaptive_swimming.persistence.session_records import (
    generated_workout_path,
    load_generated_workout,
    load_session_result,
    save_generated_workout,
    save_session_result,
    session_result_path,
)


def build_generated_workout() -> GeneratedWorkout:
    return GeneratedWorkout(
        generated_workout_id="GW_20260901_001_V1",
        workout_version=1,
        workout=build_reference_workout(),
        pool_length_meters=25,
        equipment_available=(
            EquipmentCode.FINS,
            EquipmentCode.PADDLES,
            EquipmentCode.KICKBOARD,
        ),
        generation_reason="BASELINE_SESSION",
    )


def build_blank_result() -> WorkoutSessionResult:
    return WorkoutSessionResult(
        session_result_id="SR_20260901_001_V1",
        generated_workout_id="GW_20260901_001_V1",
        result_version=1,
        completion_status=CompletionStatus.NOT_STARTED,
        completed_distance_meters=0,
    )


def test_generated_workout_path_uses_validated_id(
    tmp_path: Path,
) -> None:
    path = generated_workout_path(
        "GW_20260901_001_V1",
        tmp_path,
    )

    assert path == tmp_path / "GW_20260901_001_V1.json"


def test_session_result_path_uses_validated_id(
    tmp_path: Path,
) -> None:
    path = session_result_path(
        "SR_20260901_001_V1",
        tmp_path,
    )

    assert path == tmp_path / "SR_20260901_001_V1.json"


def test_generated_workout_round_trips(
    tmp_path: Path,
) -> None:
    generated = build_generated_workout()

    path = save_generated_workout(
        generated,
        tmp_path,
    )
    loaded = load_generated_workout(path)

    assert loaded == generated
    assert path.is_file()


def test_session_result_round_trips(
    tmp_path: Path,
) -> None:
    generated = build_generated_workout()
    result = build_blank_result()

    path = save_session_result(
        generated,
        result,
        tmp_path,
    )
    loaded = load_session_result(path)

    assert loaded == result
    assert path.is_file()


def test_generated_workout_refuses_overwrite(
    tmp_path: Path,
) -> None:
    generated = build_generated_workout()

    save_generated_workout(generated, tmp_path)

    with pytest.raises(
        FileExistsError,
        match="Refusing to overwrite",
    ):
        save_generated_workout(generated, tmp_path)


def test_session_result_refuses_overwrite(
    tmp_path: Path,
) -> None:
    generated = build_generated_workout()
    result = build_blank_result()

    save_session_result(generated, result, tmp_path)

    with pytest.raises(
        FileExistsError,
        match="Refusing to overwrite",
    ):
        save_session_result(generated, result, tmp_path)


def test_invalid_result_is_not_written(
    tmp_path: Path,
) -> None:
    generated = build_generated_workout()
    result = build_blank_result().model_copy(
        update={
            "generated_workout_id": "GW_20260901_002_V1",
        }
    )

    with pytest.raises(
        ValueError,
        match="does not belong",
    ):
        save_session_result(
            generated,
            result,
            tmp_path,
        )

    assert not list(tmp_path.iterdir())


def test_persistence_leaves_no_temporary_files(
    tmp_path: Path,
) -> None:
    generated = build_generated_workout()

    save_generated_workout(generated, tmp_path)

    temporary_files = tuple(path for path in tmp_path.iterdir() if path.suffix == ".tmp")

    assert temporary_files == ()


def test_persisted_generated_workout_preserves_metrics(
    tmp_path: Path,
) -> None:
    generated = build_generated_workout()

    path = save_generated_workout(
        generated,
        tmp_path,
    )
    loaded = load_generated_workout(path)

    assert loaded.planned_distance_meters == 2600
    assert loaded.configured_rest_seconds == 1050
    assert loaded.known_swim_seconds == 1324
    assert loaded.unresolved_distance_meters == 1200


def test_generated_workout_path_rejects_invalid_id(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="Invalid generated workout identifier",
    ):
        generated_workout_path(
            "../outside",
            tmp_path,
        )

    assert not tuple(tmp_path.iterdir())


def test_session_result_path_rejects_invalid_id(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="Invalid session result identifier",
    ):
        session_result_path(
            "../../outside",
            tmp_path,
        )

    assert not tuple(tmp_path.iterdir())
