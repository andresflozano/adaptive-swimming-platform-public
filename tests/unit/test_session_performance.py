import pytest

from adaptive_swimming.catalog.reference_workouts import (
    build_reference_workout,
)
from adaptive_swimming.domain.session_results import (
    BlockResult,
    CompletionStatus,
    GeneratedWorkout,
    RepetitionResult,
    WorkoutSessionResult,
)
from adaptive_swimming.domain.workout import EquipmentCode
from adaptive_swimming.evaluation.session_performance import (
    evaluate_session_performance,
    prescribed_rest_after_seconds,
    safe_ratio,
)
from adaptive_swimming.planning.workout_proposal import (
    build_pool_test_two_workout,
)


def build_completed_pool_test_two_result() -> WorkoutSessionResult:
    return WorkoutSessionResult(
        session_result_id="SR_20260903_001_V2",
        generated_workout_id="GW_20260903_001_V1",
        result_version=2,
        completion_status=(CompletionStatus.COMPLETED_AS_WRITTEN),
        completed_distance_meters=1500,
        actual_total_seconds=3093,
        perceived_exertion=7,
        equipment_used=(
            EquipmentCode.PADDLES,
            EquipmentCode.FINS,
            EquipmentCode.KICKBOARD,
        ),
        block_results=(
            BlockResult(
                block_sequence=1,
                completed_distance_meters=200,
                completed_as_written=True,
            ),
            BlockResult(
                block_sequence=2,
                completed_distance_meters=200,
                completed_as_written=True,
                repetition_results=(
                    RepetitionResult(
                        block_sequence=2,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=1,
                        actual_seconds=157,
                        rest_after_seconds=60,
                    ),
                    RepetitionResult(
                        block_sequence=2,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=2,
                        actual_seconds=157,
                        rest_after_seconds=None,
                    ),
                ),
            ),
            BlockResult(
                block_sequence=3,
                completed_distance_meters=300,
                completed_as_written=True,
                repetition_results=(
                    RepetitionResult(
                        block_sequence=3,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=1,
                        actual_seconds=145,
                        rest_after_seconds=45,
                    ),
                    RepetitionResult(
                        block_sequence=3,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=2,
                        actual_seconds=145,
                        rest_after_seconds=45,
                    ),
                    RepetitionResult(
                        block_sequence=3,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=3,
                        actual_seconds=147,
                        rest_after_seconds=None,
                    ),
                ),
            ),
            BlockResult(
                block_sequence=4,
                completed_distance_meters=200,
                completed_as_written=True,
                repetition_results=(
                    RepetitionResult(
                        block_sequence=4,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=1,
                        actual_seconds=65,
                        rest_after_seconds=30,
                    ),
                    RepetitionResult(
                        block_sequence=4,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=2,
                        actual_seconds=64,
                        rest_after_seconds=30,
                    ),
                    RepetitionResult(
                        block_sequence=4,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=3,
                        actual_seconds=62,
                        rest_after_seconds=30,
                    ),
                    RepetitionResult(
                        block_sequence=4,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=4,
                        actual_seconds=64,
                        rest_after_seconds=None,
                    ),
                ),
            ),
            BlockResult(
                block_sequence=5,
                completed_distance_meters=200,
                completed_as_written=True,
                repetition_results=tuple(
                    RepetitionResult(
                        block_sequence=5,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=index,
                        actual_seconds=seconds,
                        rest_after_seconds=(30 if index < 8 else None),
                    )
                    for index, seconds in enumerate(
                        (
                            58,
                            60,
                            60,
                            59,
                            63,
                            64,
                            66,
                            64,
                        ),
                        start=1,
                    )
                ),
            ),
            BlockResult(
                block_sequence=6,
                completed_distance_meters=400,
                completed_as_written=True,
                repetition_results=(
                    RepetitionResult(
                        block_sequence=6,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=1,
                        actual_seconds=151,
                        rest_after_seconds=30,
                    ),
                    RepetitionResult(
                        block_sequence=6,
                        set_group_sequence=1,
                        item_sequence=2,
                        repetition_number=1,
                        actual_seconds=183,
                        rest_after_seconds=30,
                    ),
                    RepetitionResult(
                        block_sequence=6,
                        set_group_sequence=1,
                        item_sequence=3,
                        repetition_number=1,
                        actual_seconds=144,
                        rest_after_seconds=30,
                    ),
                    RepetitionResult(
                        block_sequence=6,
                        set_group_sequence=1,
                        item_sequence=4,
                        repetition_number=1,
                        actual_seconds=177,
                        rest_after_seconds=None,
                    ),
                ),
            ),
        ),
        safety_issue_reported=False,
    )


def build_pool_test_two_generated_workout() -> GeneratedWorkout:
    return GeneratedWorkout(
        generated_workout_id="GW_20260903_001_V1",
        workout_version=1,
        workout=build_pool_test_two_workout(),
        pool_length_meters=12.5,
        available_training_seconds=3600,
        equipment_available=(
            EquipmentCode.FINS,
            EquipmentCode.PADDLES,
            EquipmentCode.KICKBOARD,
        ),
        generation_reason=("POOL_TEST_2_TIME_CONSTRAINED_PROPOSAL"),
    )


def test_ordered_sequence_between_item_rests_are_counted() -> None:
    evaluation = evaluate_session_performance(
        build_pool_test_two_generated_workout(),
        build_completed_pool_test_two_result(),
    )

    assert evaluation.comparable_recorded_rest_count == 16
    assert evaluation.matching_recorded_rest_count == 16
    assert evaluation.recorded_rest_adherence_ratio == 1.0


def test_final_ordered_item_has_no_comparable_rest() -> None:
    generated = build_pool_test_two_generated_workout()

    rest = prescribed_rest_after_seconds(
        generated,
        block_sequence=6,
        set_group_sequence=1,
        item_sequence=4,
        repetition_number=1,
    )

    assert rest is None


def test_nonfinal_ordered_item_has_prescribed_rest() -> None:
    generated = build_pool_test_two_generated_workout()

    rest = prescribed_rest_after_seconds(
        generated,
        block_sequence=6,
        set_group_sequence=1,
        item_sequence=2,
        repetition_number=1,
    )

    assert rest == 30


def test_target_free_workout_has_no_timed_repetition_ratio() -> None:
    parent = build_generated_workout()
    result = build_pool_test_one_result()

    target_free_workout = parent.model_copy(
        update={
            "workout": parent.workout.model_copy(
                update={
                    "blocks": tuple(
                        block.model_copy(
                            update={
                                "set_groups": tuple(
                                    group.model_copy(
                                        update={
                                            "items": tuple(
                                                item.model_copy(update={"target": None})
                                                for item in group.items
                                            )
                                        }
                                    )
                                    for group in block.set_groups
                                )
                            }
                        )
                        for block in parent.workout.blocks
                    )
                }
            )
        }
    )

    evaluation = evaluate_session_performance(
        target_free_workout,
        result,
    )

    assert evaluation.planned_timed_repetition_count == 0
    assert evaluation.observed_timed_repetition_count == 0
    assert evaluation.timed_repetition_completion_ratio is None
    assert evaluation.observed_target_count == 0
    assert evaluation.observed_target_adherence_ratio is None


def build_generated_workout() -> GeneratedWorkout:
    return GeneratedWorkout(
        generated_workout_id="GW_20260901_001_V1",
        workout_version=1,
        workout=build_reference_workout(),
        pool_length_meters=12.5,
        equipment_available=(
            EquipmentCode.FINS,
            EquipmentCode.PADDLES,
            EquipmentCode.KICKBOARD,
        ),
        generation_reason="BASELINE_SESSION",
    )


def build_pool_test_one_result() -> WorkoutSessionResult:
    return WorkoutSessionResult(
        session_result_id="SR_20260901_001_V2",
        generated_workout_id="GW_20260901_001_V1",
        result_version=2,
        completion_status=CompletionStatus.STOPPED_EARLY,
        completed_distance_meters=1100,
        actual_total_seconds=2700,
        perceived_exertion=5,
        equipment_used=(
            EquipmentCode.PADDLES,
            EquipmentCode.FINS,
        ),
        block_results=(
            BlockResult(
                block_sequence=1,
                completed_distance_meters=200,
                completed_as_written=True,
                actual_seconds=261,
            ),
            BlockResult(
                block_sequence=2,
                completed_distance_meters=200,
                completed_as_written=True,
                actual_seconds=310,
                repetition_results=(
                    RepetitionResult(
                        block_sequence=2,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=1,
                        completed=True,
                        actual_seconds=155,
                        rest_after_seconds=60,
                    ),
                    RepetitionResult(
                        block_sequence=2,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=2,
                        completed=True,
                        actual_seconds=155,
                        rest_after_seconds=None,
                    ),
                ),
            ),
            BlockResult(
                block_sequence=3,
                completed_distance_meters=500,
                completed_as_written=True,
                actual_seconds=774,
                repetition_results=(
                    RepetitionResult(
                        block_sequence=3,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=1,
                        actual_seconds=153,
                        rest_after_seconds=45,
                    ),
                    RepetitionResult(
                        block_sequence=3,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=2,
                        actual_seconds=150,
                        rest_after_seconds=45,
                    ),
                    RepetitionResult(
                        block_sequence=3,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=3,
                        actual_seconds=155,
                        rest_after_seconds=45,
                    ),
                    RepetitionResult(
                        block_sequence=3,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=4,
                        actual_seconds=160,
                        rest_after_seconds=45,
                    ),
                    RepetitionResult(
                        block_sequence=3,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=5,
                        actual_seconds=156,
                        rest_after_seconds=None,
                    ),
                ),
            ),
            BlockResult(
                block_sequence=4,
                completed_distance_meters=200,
                completed_as_written=True,
                actual_seconds=267,
                repetition_results=(
                    RepetitionResult(
                        block_sequence=4,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=1,
                        actual_seconds=62,
                        rest_after_seconds=30,
                    ),
                    RepetitionResult(
                        block_sequence=4,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=2,
                        actual_seconds=65,
                        rest_after_seconds=30,
                    ),
                    RepetitionResult(
                        block_sequence=4,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=3,
                        actual_seconds=65,
                        rest_after_seconds=30,
                    ),
                    RepetitionResult(
                        block_sequence=4,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=4,
                        actual_seconds=75,
                        rest_after_seconds=None,
                    ),
                ),
            ),
        ),
        safety_issue_reported=False,
        notes=(
            "Available training time was 45 minutes. "
            "Blocks 1 through 4 were completed as written. "
            "Blocks 5 through 8 were not started because time ended."
        ),
    )


def build_single_repetition_result(
    *,
    actual_seconds: int | None,
    rest_after_seconds: int | None,
    repetition_number: int = 1,
) -> WorkoutSessionResult:
    return WorkoutSessionResult(
        session_result_id="SR_20260901_002_V1",
        generated_workout_id="GW_20260901_001_V1",
        result_version=1,
        completion_status=(CompletionStatus.COMPLETED_WITH_MODIFICATIONS),
        completed_distance_meters=500,
        actual_total_seconds=600,
        block_results=(
            BlockResult(
                block_sequence=3,
                completed_distance_meters=500,
                completed_as_written=True,
                repetition_results=(
                    RepetitionResult(
                        block_sequence=3,
                        set_group_sequence=1,
                        item_sequence=1,
                        repetition_number=repetition_number,
                        completed=True,
                        actual_seconds=actual_seconds,
                        rest_after_seconds=rest_after_seconds,
                    ),
                ),
            ),
        ),
        safety_issue_reported=False,
    )


def test_pool_test_one_evaluation_reports_expected_observations() -> None:
    evaluation = evaluate_session_performance(
        build_generated_workout(),
        build_pool_test_one_result(),
    )

    assert evaluation.planned_distance_meters == 2600
    assert evaluation.completed_distance_meters == 1100
    assert evaluation.distance_completion_ratio == pytest.approx(1100 / 2600)

    assert evaluation.planned_block_count == 8
    assert evaluation.reported_block_count == 4
    assert evaluation.block_reporting_ratio == 0.5

    assert evaluation.planned_timed_repetition_count == 18
    assert evaluation.observed_timed_repetition_count == 9
    assert evaluation.timed_repetition_completion_ratio == 0.5

    assert evaluation.observed_target_count == 9
    assert evaluation.observed_targets_met_count == 0
    assert evaluation.observed_target_adherence_ratio == 0.0

    assert evaluation.comparable_recorded_rest_count == 8
    assert evaluation.matching_recorded_rest_count == 8
    assert evaluation.recorded_rest_adherence_ratio == 1.0

    assert evaluation.actual_total_seconds == 2700
    assert evaluation.perceived_exertion == 5
    assert evaluation.safety_issue_reported is False
    assert evaluation.completion_status == CompletionStatus.STOPPED_EARLY


def test_target_is_met_when_actual_time_equals_target() -> None:
    result = build_single_repetition_result(
        actual_seconds=102,
        rest_after_seconds=45,
    )

    evaluation = evaluate_session_performance(
        build_generated_workout(),
        result,
    )

    assert evaluation.observed_target_count == 1
    assert evaluation.observed_targets_met_count == 1
    assert evaluation.observed_target_adherence_ratio == 1.0


def test_target_is_missed_when_actual_time_exceeds_target() -> None:
    result = build_single_repetition_result(
        actual_seconds=103,
        rest_after_seconds=45,
    )

    evaluation = evaluate_session_performance(
        build_generated_workout(),
        result,
    )

    assert evaluation.observed_target_count == 1
    assert evaluation.observed_targets_met_count == 0
    assert evaluation.observed_target_adherence_ratio == 0.0


def test_missing_actual_time_is_not_an_observed_target() -> None:
    result = build_single_repetition_result(
        actual_seconds=None,
        rest_after_seconds=45,
    )

    evaluation = evaluate_session_performance(
        build_generated_workout(),
        result,
    )

    assert evaluation.observed_timed_repetition_count == 1
    assert evaluation.observed_target_count == 0
    assert evaluation.observed_targets_met_count == 0
    assert evaluation.observed_target_adherence_ratio is None


def test_matching_recorded_rest_is_counted() -> None:
    result = build_single_repetition_result(
        actual_seconds=102,
        rest_after_seconds=45,
    )

    evaluation = evaluate_session_performance(
        build_generated_workout(),
        result,
    )

    assert evaluation.comparable_recorded_rest_count == 1
    assert evaluation.matching_recorded_rest_count == 1
    assert evaluation.recorded_rest_adherence_ratio == 1.0


def test_different_recorded_rest_is_not_matching() -> None:
    result = build_single_repetition_result(
        actual_seconds=102,
        rest_after_seconds=60,
    )

    evaluation = evaluate_session_performance(
        build_generated_workout(),
        result,
    )

    assert evaluation.comparable_recorded_rest_count == 1
    assert evaluation.matching_recorded_rest_count == 0
    assert evaluation.recorded_rest_adherence_ratio == 0.0


def test_final_repetition_without_prescribed_rest_is_excluded() -> None:
    result = build_single_repetition_result(
        actual_seconds=102,
        rest_after_seconds=None,
        repetition_number=5,
    )

    evaluation = evaluate_session_performance(
        build_generated_workout(),
        result,
    )

    assert evaluation.comparable_recorded_rest_count == 0
    assert evaluation.matching_recorded_rest_count == 0
    assert evaluation.recorded_rest_adherence_ratio is None


def test_safe_ratio_returns_none_for_zero_denominator() -> None:
    assert safe_ratio(0, 0) is None


def test_safe_ratio_rejects_negative_input() -> None:
    with pytest.raises(
        ValueError,
        match="Ratio inputs cannot be negative",
    ):
        safe_ratio(-1, 10)


def test_safe_ratio_rejects_numerator_above_denominator() -> None:
    with pytest.raises(
        ValueError,
        match="numerator cannot exceed denominator",
    ):
        safe_ratio(11, 10)


def test_evaluation_rejects_invalid_result_linkage() -> None:
    result = build_pool_test_one_result().model_copy(
        update={
            "generated_workout_id": "GW_20260901_999_V1",
        }
    )

    with pytest.raises(
        ValueError,
        match="does not belong",
    ):
        evaluate_session_performance(
            build_generated_workout(),
            result,
        )
