import pytest
from pydantic import ValidationError

from adaptive_swimming.catalog.reference_workouts import (
    build_reference_workout,
)
from adaptive_swimming.domain.session_results import (
    GeneratedWorkout,
)
from adaptive_swimming.planning.time_feasibility import (
    TimeFeasibilityStatus,
    evaluate_time_feasibility,
)


def build_generated_workout(
    available_training_seconds: int | None,
) -> GeneratedWorkout:
    return GeneratedWorkout(
        generated_workout_id="GW_20260901_001_V1",
        workout_version=1,
        workout=build_reference_workout(),
        pool_length_meters=12.5,
        available_training_seconds=(available_training_seconds),
        generation_reason="BASELINE_SESSION",
    )


def test_available_training_time_round_trips() -> None:
    generated = build_generated_workout(2700)

    loaded = GeneratedWorkout.model_validate_json(generated.model_dump_json())

    assert loaded == generated
    assert loaded.available_training_seconds == 2700


def test_historical_workout_can_omit_available_time() -> None:
    generated = build_generated_workout(None)

    assert generated.available_training_seconds is None


def test_available_training_time_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        build_generated_workout(0)


def test_feasibility_is_not_provided_without_constraint() -> None:
    evaluation = evaluate_time_feasibility(build_generated_workout(None))

    assert evaluation.available_seconds is None
    assert evaluation.remaining_after_known_seconds is None
    assert evaluation.status == TimeFeasibilityStatus.NOT_PROVIDED


def test_pool_test_one_workout_has_unresolved_feasibility() -> None:
    evaluation = evaluate_time_feasibility(build_generated_workout(2700))

    assert evaluation.available_seconds == 2700
    assert evaluation.known_swim_seconds == 1324
    assert evaluation.configured_rest_seconds == 1050
    assert evaluation.known_required_seconds == 2374
    assert evaluation.remaining_after_known_seconds == 326
    assert evaluation.unresolved_distance_meters == 1200
    assert evaluation.status == TimeFeasibilityStatus.UNRESOLVED


def test_known_work_can_exceed_available_time() -> None:
    evaluation = evaluate_time_feasibility(build_generated_workout(2300))

    assert evaluation.remaining_after_known_seconds == -74
    assert evaluation.status == TimeFeasibilityStatus.EXCEEDS_AVAILABLE_KNOWN_TIME
