import pytest
from pydantic import ValidationError

from adaptive_swimming.catalog.reference_workouts import (
    build_reference_workout,
)
from adaptive_swimming.domain.session_results import (
    BlockResult,
    CompletionStatus,
    GeneratedWorkout,
    RepetitionResult,
    WorkoutSessionResult,
    validate_session_result,
)
from adaptive_swimming.domain.workout import EquipmentCode


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


def build_completed_result() -> WorkoutSessionResult:
    return WorkoutSessionResult(
        session_result_id="SR_20260901_001_V1",
        generated_workout_id="GW_20260901_001_V1",
        result_version=1,
        completion_status=(CompletionStatus.COMPLETED_AS_WRITTEN),
        completed_distance_meters=2600,
        actual_total_seconds=4200,
        perceived_exertion=7,
        equipment_used=(
            EquipmentCode.FINS,
            EquipmentCode.PADDLES,
            EquipmentCode.KICKBOARD,
        ),
        block_results=(),
        safety_issue_reported=False,
        notes="Baseline pool session.",
    )


def test_generated_workout_preserves_planned_snapshot() -> None:
    generated = build_generated_workout()

    assert generated.planned_distance_meters == 2600
    assert generated.configured_rest_seconds == 1050
    assert generated.known_swim_seconds == 1324
    assert generated.unresolved_distance_meters == 1200
    assert generated.pool_length_meters == 25


def test_generated_workout_is_immutable() -> None:
    generated = build_generated_workout()

    with pytest.raises(ValidationError):
        generated.workout_version = 2


def test_session_result_round_trips_through_json() -> None:
    result = build_completed_result()

    loaded = WorkoutSessionResult.model_validate_json(result.model_dump_json())

    assert loaded == result


def test_session_result_validates_against_generated_workout() -> None:
    generated = build_generated_workout()
    result = build_completed_result()

    validate_session_result(generated, result)


def test_session_result_rejects_wrong_generated_workout() -> None:
    generated = build_generated_workout()
    result = build_completed_result().model_copy(
        update={
            "generated_workout_id": "GW_20260901_002_V1",
        }
    )

    with pytest.raises(
        ValueError,
        match="does not belong",
    ):
        validate_session_result(generated, result)


def test_session_result_rejects_excess_distance() -> None:
    generated = build_generated_workout()
    result = build_completed_result().model_copy(
        update={
            "completed_distance_meters": 2700,
        }
    )

    with pytest.raises(
        ValueError,
        match="cannot exceed planned distance",
    ):
        validate_session_result(generated, result)


def test_not_started_session_requires_zero_distance() -> None:
    with pytest.raises(ValidationError):
        WorkoutSessionResult(
            session_result_id="SR_20260901_001_V1",
            generated_workout_id="GW_20260901_001_V1",
            result_version=1,
            completion_status=CompletionStatus.NOT_STARTED,
            completed_distance_meters=100,
        )


def test_not_started_session_rejects_perceived_exertion() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot have perceived exertion",
    ):
        WorkoutSessionResult(
            session_result_id="SR_20260901_001_V1",
            generated_workout_id="GW_20260901_001_V1",
            result_version=1,
            completion_status=CompletionStatus.NOT_STARTED,
            completed_distance_meters=0,
            perceived_exertion=1,
        )


def test_not_started_session_rejects_equipment_used() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot have equipment used",
    ):
        WorkoutSessionResult(
            session_result_id="SR_20260901_001_V1",
            generated_workout_id="GW_20260901_001_V1",
            result_version=1,
            completion_status=CompletionStatus.NOT_STARTED,
            completed_distance_meters=0,
            equipment_used=(EquipmentCode.FINS,),
        )


def test_not_started_session_rejects_block_results() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot have block results",
    ):
        WorkoutSessionResult(
            session_result_id="SR_20260901_001_V1",
            generated_workout_id="GW_20260901_001_V1",
            result_version=1,
            completion_status=CompletionStatus.NOT_STARTED,
            completed_distance_meters=0,
            block_results=(
                BlockResult(
                    block_sequence=1,
                    completed_distance_meters=0,
                    completed_as_written=False,
                ),
            ),
        )


def test_incomplete_repetition_rejects_actual_time() -> None:
    with pytest.raises(
        ValidationError,
        match="Incomplete repetitions",
    ):
        RepetitionResult(
            block_sequence=3,
            set_group_sequence=1,
            item_sequence=1,
            repetition_number=5,
            completed=False,
            actual_seconds=108,
        )


def test_session_result_rejects_unknown_block() -> None:
    generated = build_generated_workout()
    result = build_completed_result().model_copy(
        update={
            "block_results": (
                BlockResult(
                    block_sequence=9,
                    completed_distance_meters=100,
                    completed_as_written=False,
                ),
            )
        }
    )

    with pytest.raises(
        ValueError,
        match="unknown block sequences",
    ):
        validate_session_result(generated, result)


def test_session_result_rejects_duplicate_block_results() -> None:
    generated = build_generated_workout()
    block_result = BlockResult(
        block_sequence=1,
        completed_distance_meters=200,
        completed_as_written=True,
    )
    result = build_completed_result().model_copy(
        update={
            "block_results": (
                block_result,
                block_result,
            )
        }
    )

    with pytest.raises(
        ValueError,
        match="duplicate sequences",
    ):
        validate_session_result(generated, result)


def test_not_started_session_allows_safety_issue_and_notes() -> None:
    result = WorkoutSessionResult(
        session_result_id="SR_20260901_001_V1",
        generated_workout_id="GW_20260901_001_V1",
        result_version=1,
        completion_status=CompletionStatus.NOT_STARTED,
        completed_distance_meters=0,
        safety_issue_reported=True,
        notes="Session was not started because of a reported safety concern.",
    )

    assert result.safety_issue_reported is True
    assert result.notes is not None


def test_generated_workout_id_version_must_match() -> None:
    with pytest.raises(
        ValidationError,
        match="ID version must match workout_version",
    ):
        GeneratedWorkout(
            generated_workout_id="GW_20260901_001_V2",
            workout_version=1,
            workout=build_reference_workout(),
            pool_length_meters=25,
            generation_reason="BASELINE_SESSION",
        )


def test_session_result_id_version_must_match() -> None:
    with pytest.raises(
        ValidationError,
        match="ID version must match result_version",
    ):
        WorkoutSessionResult(
            session_result_id="SR_20260901_001_V2",
            generated_workout_id="GW_20260901_001_V1",
            result_version=1,
            completion_status=CompletionStatus.NOT_STARTED,
            completed_distance_meters=0,
        )


def test_session_result_rejects_unavailable_equipment() -> None:
    generated = build_generated_workout().model_copy(
        update={"equipment_available": (EquipmentCode.FINS,)}
    )
    result = build_completed_result().model_copy(
        update={"equipment_used": (EquipmentCode.PADDLES,)}
    )

    with pytest.raises(
        ValueError,
        match="Equipment used",
    ):
        validate_session_result(generated, result)


def test_block_result_rejects_excess_planned_distance() -> None:
    generated = build_generated_workout()
    result = build_completed_result().model_copy(
        update={
            "completion_status": (CompletionStatus.COMPLETED_WITH_MODIFICATIONS),
            "completed_distance_meters": 300,
            "block_results": (
                BlockResult(
                    block_sequence=1,
                    completed_distance_meters=300,
                    completed_as_written=False,
                ),
            ),
        }
    )

    with pytest.raises(
        ValueError,
        match="Completed block distance",
    ):
        validate_session_result(generated, result)


def test_repetition_result_must_match_parent_block() -> None:
    generated = build_generated_workout()
    result = build_completed_result().model_copy(
        update={
            "completion_status": (CompletionStatus.COMPLETED_WITH_MODIFICATIONS),
            "completed_distance_meters": 500,
            "block_results": (
                BlockResult(
                    block_sequence=3,
                    completed_distance_meters=500,
                    completed_as_written=True,
                    repetition_results=(
                        RepetitionResult(
                            block_sequence=4,
                            set_group_sequence=1,
                            item_sequence=1,
                            repetition_number=1,
                            actual_seconds=100,
                        ),
                    ),
                ),
            ),
        }
    )

    with pytest.raises(
        ValueError,
        match="parent block result",
    ):
        validate_session_result(generated, result)


def test_repetition_result_rejects_unknown_set_group() -> None:
    generated = build_generated_workout()
    result = build_completed_result().model_copy(
        update={
            "completion_status": (CompletionStatus.COMPLETED_WITH_MODIFICATIONS),
            "completed_distance_meters": 500,
            "block_results": (
                BlockResult(
                    block_sequence=3,
                    completed_distance_meters=500,
                    completed_as_written=True,
                    repetition_results=(
                        RepetitionResult(
                            block_sequence=3,
                            set_group_sequence=99,
                            item_sequence=1,
                            repetition_number=1,
                            actual_seconds=100,
                        ),
                    ),
                ),
            ),
        }
    )

    with pytest.raises(
        ValueError,
        match="unknown set group",
    ):
        validate_session_result(generated, result)


def test_repetition_result_rejects_unknown_item() -> None:
    generated = build_generated_workout()
    result = build_completed_result().model_copy(
        update={
            "completion_status": (CompletionStatus.COMPLETED_WITH_MODIFICATIONS),
            "completed_distance_meters": 500,
            "block_results": (
                BlockResult(
                    block_sequence=3,
                    completed_distance_meters=500,
                    completed_as_written=True,
                    repetition_results=(
                        RepetitionResult(
                            block_sequence=3,
                            set_group_sequence=1,
                            item_sequence=99,
                            repetition_number=1,
                            actual_seconds=100,
                        ),
                    ),
                ),
            ),
        }
    )

    with pytest.raises(
        ValueError,
        match="unknown item",
    ):
        validate_session_result(generated, result)


def test_repetition_result_rejects_excess_repetition() -> None:
    generated = build_generated_workout()
    result = build_completed_result().model_copy(
        update={
            "completion_status": (CompletionStatus.COMPLETED_WITH_MODIFICATIONS),
            "completed_distance_meters": 500,
            "block_results": (
                BlockResult(
                    block_sequence=3,
                    completed_distance_meters=500,
                    completed_as_written=True,
                    repetition_results=(
                        RepetitionResult(
                            block_sequence=3,
                            set_group_sequence=1,
                            item_sequence=1,
                            repetition_number=6,
                            actual_seconds=100,
                        ),
                    ),
                ),
            ),
        }
    )

    with pytest.raises(
        ValueError,
        match="exceeds planned repetition count",
    ):
        validate_session_result(generated, result)


def test_session_result_rejects_duplicate_repetition_coordinates() -> None:
    generated = build_generated_workout()
    repetition = RepetitionResult(
        block_sequence=3,
        set_group_sequence=1,
        item_sequence=1,
        repetition_number=1,
        actual_seconds=100,
    )
    result = build_completed_result().model_copy(
        update={
            "completion_status": (CompletionStatus.COMPLETED_WITH_MODIFICATIONS),
            "completed_distance_meters": 500,
            "block_results": (
                BlockResult(
                    block_sequence=3,
                    completed_distance_meters=500,
                    completed_as_written=True,
                    repetition_results=(
                        repetition,
                        repetition,
                    ),
                ),
            ),
        }
    )

    with pytest.raises(
        ValueError,
        match="duplicate coordinates",
    ):
        validate_session_result(generated, result)


def test_session_completed_as_written_requires_planned_distance() -> None:
    generated = build_generated_workout()
    result = build_completed_result().model_copy(
        update={
            "completed_distance_meters": 2500,
        }
    )

    with pytest.raises(
        ValueError,
        match="must match the planned distance",
    ):
        validate_session_result(generated, result)


def test_complete_block_results_reconcile_to_session_distance() -> None:
    generated = build_generated_workout()
    block_distances = (
        200,
        200,
        500,
        200,
        500,
        200,
        300,
        500,
    )
    result = build_completed_result().model_copy(
        update={
            "block_results": tuple(
                BlockResult(
                    block_sequence=sequence,
                    completed_distance_meters=distance,
                    completed_as_written=True,
                )
                for sequence, distance in enumerate(
                    block_distances,
                    start=1,
                )
            )
        }
    )

    validate_session_result(generated, result)


def test_reported_block_distance_cannot_exceed_session_distance() -> None:
    generated = build_generated_workout()
    result = build_completed_result().model_copy(
        update={
            "completion_status": (CompletionStatus.COMPLETED_WITH_MODIFICATIONS),
            "completed_distance_meters": 100,
            "block_results": (
                BlockResult(
                    block_sequence=1,
                    completed_distance_meters=200,
                    completed_as_written=True,
                ),
            ),
        }
    )

    with pytest.raises(
        ValueError,
        match="Reported block distance cannot exceed",
    ):
        validate_session_result(generated, result)


def test_complete_block_results_must_reconcile_to_session_distance() -> None:
    generated = build_generated_workout()
    block_distances = (
        100,
        200,
        500,
        200,
        500,
        200,
        300,
        500,
    )
    result = build_completed_result().model_copy(
        update={
            "completion_status": (CompletionStatus.COMPLETED_WITH_MODIFICATIONS),
            "completed_distance_meters": 2600,
            "block_results": tuple(
                BlockResult(
                    block_sequence=sequence,
                    completed_distance_meters=distance,
                    completed_as_written=(
                        distance == generated.workout.blocks[sequence - 1].total_distance_meters()
                    ),
                )
                for sequence, distance in enumerate(
                    block_distances,
                    start=1,
                )
            ),
        }
    )

    with pytest.raises(
        ValueError,
        match="Complete block results must reconcile",
    ):
        validate_session_result(generated, result)


def test_completed_as_written_rejects_modified_block() -> None:
    generated = build_generated_workout()
    block_distances = (
        200,
        200,
        500,
        200,
        500,
        200,
        300,
        500,
    )
    result = build_completed_result().model_copy(
        update={
            "block_results": tuple(
                BlockResult(
                    block_sequence=sequence,
                    completed_distance_meters=distance,
                    completed_as_written=sequence != 8,
                )
                for sequence, distance in enumerate(
                    block_distances,
                    start=1,
                )
            )
        }
    )

    with pytest.raises(
        ValueError,
        match="cannot contain modified block results",
    ):
        validate_session_result(generated, result)


def test_generated_workout_accepts_fractional_pool_length() -> None:
    generated = GeneratedWorkout(
        generated_workout_id="GW_20260901_001_V1",
        workout_version=1,
        workout=build_reference_workout(),
        pool_length_meters=12.5,
        generation_reason="BASELINE_SESSION",
    )

    assert generated.pool_length_meters == 12.5

    loaded = GeneratedWorkout.model_validate_json(generated.model_dump_json())

    assert loaded == generated
    assert loaded.pool_length_meters == 12.5
