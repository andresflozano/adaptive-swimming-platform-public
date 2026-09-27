from __future__ import annotations

import pytest
from pydantic import ValidationError

from adaptive_swimming.catalog.reference_workouts import build_reference_workout
from adaptive_swimming.domain.session_results import (
    BlockResult,
    CompletionStatus,
    GeneratedWorkout,
    RepetitionResult,
    WorkoutSessionResult,
)
from adaptive_swimming.domain.workout import (
    EquipmentCode,
    ExerciseCode,
    IntensityCode,
)
from adaptive_swimming.evaluation.pace_calibration import (
    ProvisionalPaceSummary,
    calibrate_pace_from_sessions,
    extract_pace_observations,
    summarize_pace_observations,
)
from adaptive_swimming.planning.workout_proposal import build_pool_test_two_workout


def repetition(
    *,
    block: int,
    repetition_number: int,
    seconds: int | None,
    item: int = 1,
    completed: bool = True,
) -> RepetitionResult:
    return RepetitionResult(
        block_sequence=block,
        set_group_sequence=1,
        item_sequence=item,
        repetition_number=repetition_number,
        completed=completed,
        actual_seconds=seconds,
    )


def build_test_one_pair() -> tuple[GeneratedWorkout, WorkoutSessionResult]:
    workout = GeneratedWorkout(
        generated_workout_id="GW_20260901_001_V1",
        workout_version=1,
        workout=build_reference_workout(),
        pool_length_meters=12.5,
        generation_reason="BASELINE_SESSION",
    )
    result = WorkoutSessionResult(
        session_result_id="SR_20260901_001_V2",
        generated_workout_id=workout.generated_workout_id,
        result_version=2,
        completion_status=CompletionStatus.STOPPED_EARLY,
        completed_distance_meters=700,
        actual_total_seconds=2700,
        block_results=(
            BlockResult(
                block_sequence=3,
                completed_distance_meters=500,
                completed_as_written=True,
                repetition_results=tuple(
                    repetition(block=3, repetition_number=index, seconds=seconds)
                    for index, seconds in enumerate((153, 150, 155, 160, 156), start=1)
                ),
            ),
            BlockResult(
                block_sequence=4,
                completed_distance_meters=200,
                completed_as_written=True,
                repetition_results=tuple(
                    repetition(block=4, repetition_number=index, seconds=seconds)
                    for index, seconds in enumerate((62, 65, 65, 75), start=1)
                ),
            ),
        ),
    )
    return workout, result


def build_test_two_pair() -> tuple[GeneratedWorkout, WorkoutSessionResult]:
    workout = GeneratedWorkout(
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
        generation_reason="POOL_TEST_2_TIME_CONSTRAINED_PROPOSAL",
    )
    result = WorkoutSessionResult(
        session_result_id="SR_20260903_001_V2",
        generated_workout_id=workout.generated_workout_id,
        result_version=2,
        completion_status=CompletionStatus.STOPPED_EARLY,
        completed_distance_meters=500,
        actual_total_seconds=3093,
        block_results=(
            BlockResult(
                block_sequence=3,
                completed_distance_meters=300,
                completed_as_written=True,
                repetition_results=tuple(
                    repetition(block=3, repetition_number=index, seconds=seconds)
                    for index, seconds in enumerate((145, 145, 147), start=1)
                ),
            ),
            BlockResult(
                block_sequence=4,
                completed_distance_meters=200,
                completed_as_written=True,
                repetition_results=tuple(
                    repetition(block=4, repetition_number=index, seconds=seconds)
                    for index, seconds in enumerate((65, 64, 62, 64), start=1)
                ),
            ),
        ),
    )
    return workout, result


def test_extracts_completed_repetitions_with_actual_times() -> None:
    workout, result = build_test_one_pair()
    observations = extract_pace_observations(workout, result)
    assert len(observations) == 9
    assert observations[0].actual_seconds == 153


def test_excludes_repetition_without_actual_time() -> None:
    workout, result = build_test_one_pair()
    block = result.block_results[0].model_copy(
        update={"repetition_results": (repetition(block=3, repetition_number=1, seconds=None),)}
    )
    altered = result.model_copy(
        update={"completed_distance_meters": 500, "block_results": (block,)}
    )
    assert extract_pace_observations(workout, altered) == ()


def test_excludes_incomplete_repetition() -> None:
    workout, result = build_test_one_pair()
    block = result.block_results[0].model_copy(
        update={
            "repetition_results": (
                repetition(
                    block=3,
                    repetition_number=1,
                    seconds=None,
                    completed=False,
                ),
            )
        }
    )
    altered = result.model_copy(
        update={"completed_distance_meters": 500, "block_results": (block,)}
    )
    assert extract_pace_observations(workout, altered) == ()


def test_rejects_invalid_workout_result_linkage() -> None:
    workout, result = build_test_one_pair()
    invalid = result.model_copy(update={"generated_workout_id": "GW_20260901_999_V1"})
    with pytest.raises(ValueError, match="does not belong"):
        extract_pace_observations(workout, invalid)


def test_rejects_not_started_session_result() -> None:
    workout, result = build_test_one_pair()
    payload = result.model_dump()
    payload.update(
        {
            "completion_status": CompletionStatus.NOT_STARTED,
            "completed_distance_meters": 0,
            "actual_total_seconds": None,
            "perceived_exertion": None,
            "equipment_used": (),
            "block_results": (),
        }
    )
    not_started = WorkoutSessionResult.model_validate(payload)

    with pytest.raises(ValueError, match="NOT_STARTED"):
        extract_pace_observations(workout, not_started)


def test_rejects_session_result_with_reported_safety_issue() -> None:
    workout, result = build_test_one_pair()
    payload = result.model_dump()
    payload["safety_issue_reported"] = True
    safety_flagged = WorkoutSessionResult.model_validate(payload)

    with pytest.raises(ValueError, match="reported safety issue"):
        extract_pace_observations(workout, safety_flagged)


def test_multi_session_calibration_fails_when_one_result_reports_safety_issue() -> None:
    valid_pair = build_test_one_pair()
    workout, result = build_test_two_pair()
    payload = result.model_dump()
    payload["safety_issue_reported"] = True
    safety_flagged = WorkoutSessionResult.model_validate(payload)

    with pytest.raises(ValueError, match="reported safety issue"):
        calibrate_pace_from_sessions(
            (
                valid_pair,
                (workout, safety_flagged),
            )
        )


def test_observation_uses_planned_metadata_and_source_ids() -> None:
    workout, result = build_test_one_pair()
    observation = extract_pace_observations(workout, result)[0]
    assert observation.generated_workout_id == workout.generated_workout_id
    assert observation.session_result_id == result.session_result_id
    assert observation.key.exercise == ExerciseCode.FREESTYLE
    assert observation.key.distance_meters == 100
    assert observation.key.equipment == ()
    assert observation.key.intensity == IntensityCode.UNRESOLVED


def test_strict_summary_keeps_intensities_separate() -> None:
    summaries = calibrate_pace_from_sessions((build_test_one_pair(), build_test_two_pair()))
    hundred_meter = [summary for summary in summaries if summary.key.distance_meters == 100]
    assert sorted(summary.sample_count for summary in hundred_meter) == [3, 5]
    assert {summary.key.intensity for summary in hundred_meter} == {
        IntensityCode.AEROBIC,
        IntensityCode.UNRESOLVED,
    }


def test_summary_combines_comparable_fifty_meter_fins() -> None:
    summaries = calibrate_pace_from_sessions((build_test_one_pair(), build_test_two_pair()))
    summary = next(summary for summary in summaries if summary.key.distance_meters == 50)
    assert summary.key.exercise == ExerciseCode.FREESTYLE
    assert summary.key.equipment == (EquipmentCode.FINS,)
    assert summary.sample_count == 8
    assert summary.minimum_seconds == 62
    assert summary.maximum_seconds == 75
    assert summary.mean_seconds == pytest.approx(65.25)
    assert summary.median_seconds == pytest.approx(64.5)


def test_summary_preserves_all_observation_lineage() -> None:
    summaries = calibrate_pace_from_sessions((build_test_one_pair(), build_test_two_pair()))
    summary = next(summary for summary in summaries if summary.key.distance_meters == 50)
    assert {observation.session_result_id for observation in summary.observations} == {
        "SR_20260901_001_V2",
        "SR_20260903_001_V2",
    }


def test_summaries_are_deterministically_ordered() -> None:
    summaries = calibrate_pace_from_sessions((build_test_two_pair(), build_test_one_pair()))
    keys = [
        (
            summary.key.exercise.value,
            summary.key.distance_meters,
            tuple(value.value for value in summary.key.equipment),
            summary.key.intensity.value,
        )
        for summary in summaries
    ]
    assert keys == sorted(keys)


def test_empty_observations_return_no_summaries() -> None:
    assert summarize_pace_observations(()) == ()


def test_summary_is_provisional_and_documents_limitations() -> None:
    summaries = calibrate_pace_from_sessions((build_test_one_pair(),))
    assert all(summary.provisional for summary in summaries)
    assert all(summary.limitations for summary in summaries)
    assert all(
        "does not define a mandatory target" in summary.limitations[0] for summary in summaries
    )


def test_summary_round_trips_through_json() -> None:
    summary = calibrate_pace_from_sessions((build_test_one_pair(),))[0]
    loaded = ProvisionalPaceSummary.model_validate_json(summary.model_dump_json())
    assert loaded == summary


def test_summary_is_immutable() -> None:
    summary = calibrate_pace_from_sessions((build_test_one_pair(),))[0]
    with pytest.raises(ValidationError):
        summary.sample_count = 99


def test_calibration_does_not_modify_inputs() -> None:
    workout, result = build_test_one_pair()
    workout_before = workout.model_dump_json()
    result_before = result.model_dump_json()
    calibrate_pace_from_sessions(((workout, result),))
    assert workout.model_dump_json() == workout_before
    assert result.model_dump_json() == result_before
