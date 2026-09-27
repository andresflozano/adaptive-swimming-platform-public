from __future__ import annotations

import pytest

from adaptive_swimming.domain.session_results import GeneratedWorkout
from adaptive_swimming.recording.timing_results import (
    convert_item_timing_to_repetition_results,
)
from adaptive_swimming.recording.workout_timing import (
    ItemTimingCapture,
    ItemTimingSummary,
    calculate_item_timing,
)
from tests.unit.test_configurable_workout_proposal import build_parent
from tests.unit.test_workout_timing import pool_test_four_capture


def generated_workout() -> GeneratedWorkout:
    return build_parent()


def pool_test_four_summary() -> ItemTimingSummary:
    return calculate_item_timing(pool_test_four_capture())


def test_converts_pool_test_four_timings() -> None:
    results = convert_item_timing_to_repetition_results(
        generated_workout=generated_workout(),
        summary=pool_test_four_summary(),
    )

    assert tuple(result.actual_seconds for result in results) == (60, 57, 60, 58)
    assert tuple(result.rest_after_seconds for result in results) == (30, 30, 30, None)
    assert all(result.completed for result in results)


def test_preserves_coordinates_and_formulas_in_notes() -> None:
    results = convert_item_timing_to_repetition_results(
        generated_workout=generated_workout(),
        summary=pool_test_four_summary(),
    )

    assert tuple(
        (
            result.block_sequence,
            result.set_group_sequence,
            result.item_sequence,
            result.repetition_number,
        )
        for result in results
    ) == (
        (4, 1, 1, 1),
        (4, 1, 1, 2),
        (4, 1, 1, 3),
        (4, 1, 1, 4),
    )
    assert results[0].notes == "Elapsed timing calculation: 1170 - 1110 - 0 = 60."


def test_rejects_unknown_block() -> None:
    summary = pool_test_four_summary().model_copy(update={"block_sequence": 99})
    with pytest.raises(ValueError, match="planned block"):
        convert_item_timing_to_repetition_results(
            generated_workout=generated_workout(),
            summary=summary,
        )


def test_rejects_unknown_group() -> None:
    summary = pool_test_four_summary().model_copy(update={"set_group_sequence": 99})
    with pytest.raises(ValueError, match="planned set group"):
        convert_item_timing_to_repetition_results(
            generated_workout=generated_workout(),
            summary=summary,
        )


def test_rejects_unknown_item() -> None:
    summary = pool_test_four_summary().model_copy(update={"item_sequence": 99})
    with pytest.raises(ValueError, match="planned item"):
        convert_item_timing_to_repetition_results(
            generated_workout=generated_workout(),
            summary=summary,
        )


def test_rejects_capture_above_planned_count() -> None:
    summary = pool_test_four_summary()
    extra = summary.repetitions[-1].model_copy(update={"repetition_number": 5})
    invalid = summary.model_copy(update={"repetitions": summary.repetitions + (extra,)})
    with pytest.raises(ValueError, match="exceeds"):
        convert_item_timing_to_repetition_results(
            generated_workout=generated_workout(),
            summary=invalid,
        )


def test_rejects_incomplete_capture_by_default() -> None:
    summary = pool_test_four_summary().model_copy(
        update={"repetitions": pool_test_four_summary().repetitions[:3]}
    )
    with pytest.raises(ValueError, match="every planned repetition"):
        convert_item_timing_to_repetition_results(
            generated_workout=generated_workout(),
            summary=summary,
        )


def test_allows_explicit_partial_capture() -> None:
    summary = pool_test_four_summary().model_copy(
        update={"repetitions": pool_test_four_summary().repetitions[:3]}
    )
    results = convert_item_timing_to_repetition_results(
        generated_workout=generated_workout(),
        summary=summary,
        require_complete_capture=False,
    )
    assert tuple(result.repetition_number for result in results) == (1, 2, 3)
    assert results[-1].rest_after_seconds is None


def test_rejects_target_mismatch() -> None:
    summary = pool_test_four_summary().model_copy(update={"target_seconds": 64})
    with pytest.raises(ValueError, match="target must match"):
        convert_item_timing_to_repetition_results(
            generated_workout=generated_workout(),
            summary=summary,
        )


def test_rejects_target_for_untargeted_item() -> None:
    capture_payload = pool_test_four_capture().model_dump()
    capture_payload["block_sequence"] = 3
    capture_payload["readings"] = capture_payload["readings"][:3]
    capture_payload["target_seconds"] = 65
    summary = calculate_item_timing(ItemTimingCapture.model_validate(capture_payload))

    with pytest.raises(ValueError, match="target must match"):
        convert_item_timing_to_repetition_results(
            generated_workout=generated_workout(),
            summary=summary,
        )
