from __future__ import annotations

import pytest
from pydantic import ValidationError

from adaptive_swimming.recording.workout_timing import (
    ElapsedRepetitionReading,
    ItemTimingCapture,
    calculate_item_timing,
)


def pool_test_four_capture() -> ItemTimingCapture:
    return ItemTimingCapture(
        block_sequence=4,
        set_group_sequence=1,
        item_sequence=1,
        block_start_elapsed_seconds=1110,
        readings=(
            ElapsedRepetitionReading(
                repetition_number=1,
                finish_elapsed_seconds=1170,
            ),
            ElapsedRepetitionReading(
                repetition_number=2,
                finish_elapsed_seconds=1257,
                rest_before_seconds=30,
            ),
            ElapsedRepetitionReading(
                repetition_number=3,
                finish_elapsed_seconds=1347,
                rest_before_seconds=30,
            ),
            ElapsedRepetitionReading(
                repetition_number=4,
                finish_elapsed_seconds=1435,
                rest_before_seconds=30,
            ),
        ),
        target_seconds=65,
    )


def test_calculates_pool_test_four_repetition_durations() -> None:
    summary = calculate_item_timing(pool_test_four_capture())

    assert tuple(repetition.actual_seconds for repetition in summary.repetitions) == (
        60,
        57,
        60,
        58,
    )
    assert summary.active_seconds == 235
    assert summary.rest_seconds == 90
    assert summary.captured_elapsed_seconds == 325


def test_preserves_raw_readings_and_calculation_formulas() -> None:
    summary = calculate_item_timing(pool_test_four_capture())

    assert summary.repetitions[0].previous_elapsed_seconds == 1110
    assert summary.repetitions[0].finish_elapsed_seconds == 1170
    assert summary.repetitions[0].formula == "1170 - 1110 - 0 = 60"
    assert summary.repetitions[1].formula == "1257 - 1170 - 30 = 57"


def test_calculates_descriptive_summary() -> None:
    summary = calculate_item_timing(pool_test_four_capture())

    assert summary.fastest_seconds == 57
    assert summary.slowest_seconds == 60
    assert summary.mean_seconds == 58.75
    assert summary.median_seconds == 59.0
    assert summary.range_seconds == 3


def test_calculates_target_results() -> None:
    summary = calculate_item_timing(pool_test_four_capture())

    assert summary.target_seconds == 65
    assert summary.targets_met_count == 4
    assert tuple(repetition.target_met for repetition in summary.repetitions) == (
        True,
        True,
        True,
        True,
    )


def test_capture_without_target_has_no_target_results() -> None:
    payload = pool_test_four_capture().model_dump()
    payload["target_seconds"] = None
    summary = calculate_item_timing(ItemTimingCapture.model_validate(payload))

    assert summary.target_seconds is None
    assert summary.targets_met_count is None
    assert all(repetition.target_met is None for repetition in summary.repetitions)


def test_readings_must_increase_strictly() -> None:
    with pytest.raises(ValidationError, match="increase strictly"):
        ItemTimingCapture(
            block_sequence=4,
            set_group_sequence=1,
            item_sequence=1,
            block_start_elapsed_seconds=100,
            readings=(
                ElapsedRepetitionReading(
                    repetition_number=1,
                    finish_elapsed_seconds=160,
                ),
                ElapsedRepetitionReading(
                    repetition_number=2,
                    finish_elapsed_seconds=160,
                    rest_before_seconds=30,
                ),
            ),
        )


def test_calculated_duration_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="duration must be positive"):
        ItemTimingCapture(
            block_sequence=4,
            set_group_sequence=1,
            item_sequence=1,
            block_start_elapsed_seconds=100,
            readings=(
                ElapsedRepetitionReading(
                    repetition_number=1,
                    finish_elapsed_seconds=160,
                ),
                ElapsedRepetitionReading(
                    repetition_number=2,
                    finish_elapsed_seconds=180,
                    rest_before_seconds=30,
                ),
            ),
        )


def test_repetition_numbers_must_be_consecutive() -> None:
    with pytest.raises(ValidationError, match="consecutive"):
        ItemTimingCapture(
            block_sequence=4,
            set_group_sequence=1,
            item_sequence=1,
            block_start_elapsed_seconds=100,
            readings=(
                ElapsedRepetitionReading(
                    repetition_number=1,
                    finish_elapsed_seconds=160,
                ),
                ElapsedRepetitionReading(
                    repetition_number=3,
                    finish_elapsed_seconds=250,
                    rest_before_seconds=30,
                ),
            ),
        )


def test_first_repetition_cannot_have_rest_before() -> None:
    with pytest.raises(ValidationError, match="first repetition"):
        ItemTimingCapture(
            block_sequence=4,
            set_group_sequence=1,
            item_sequence=1,
            block_start_elapsed_seconds=100,
            readings=(
                ElapsedRepetitionReading(
                    repetition_number=1,
                    finish_elapsed_seconds=190,
                    rest_before_seconds=30,
                ),
            ),
        )


def test_negative_rest_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ElapsedRepetitionReading(
            repetition_number=2,
            finish_elapsed_seconds=250,
            rest_before_seconds=-1,
        )


def test_non_positive_target_is_rejected() -> None:
    with pytest.raises(ValidationError):
        payload = pool_test_four_capture().model_dump()
        payload["target_seconds"] = 0
        ItemTimingCapture.model_validate(payload)


def test_capture_round_trips_and_is_immutable() -> None:
    capture = pool_test_four_capture()

    assert ItemTimingCapture.model_validate_json(capture.model_dump_json()) == capture
    with pytest.raises(ValidationError):
        capture.block_sequence = 5
