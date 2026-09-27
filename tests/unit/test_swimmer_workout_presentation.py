import pytest

from adaptive_swimming.catalog.reference_workouts import (
    build_reference_workout,
)
from adaptive_swimming.domain.session_results import (
    GeneratedWorkout,
)
from adaptive_swimming.planning.workout_proposal import (
    build_pool_test_two_workout,
)
from adaptive_swimming.presentation.swimmer_workout import (
    build_generated_workout_presentation,
    build_swimmer_presentation,
    format_seconds,
    render_plain_text,
)


def test_pool_test_two_pace_instructions_are_visible() -> None:
    presentation = build_swimmer_presentation(build_pool_test_two_workout())

    block_three = "\n".join(presentation.pages[3].lines)
    block_four = "\n".join(presentation.pages[4].lines)

    assert (
        "3 x 100 m | Freestyle | Intensity: Aerobic | Record each repetition time." in block_three
    )
    assert "4 x 50 m | Freestyle | Equipment: Fins | Record each repetition time." in block_four


def test_swimmer_instruction_is_not_in_unrelated_blocks() -> None:
    presentation = build_swimmer_presentation(build_pool_test_two_workout())

    unrelated_output = "\n".join(
        line
        for page in (
            presentation.pages[1],
            presentation.pages[2],
            presentation.pages[5],
            presentation.pages[6],
        )
        for line in page.lines
    )

    assert "Record each repetition time." not in unrelated_output


def test_generated_presentation_shows_available_time() -> None:
    generated = GeneratedWorkout(
        generated_workout_id="GW_20260901_001_V1",
        workout_version=1,
        workout=build_reference_workout(),
        pool_length_meters=12.5,
        available_training_seconds=2700,
        generation_reason="BASELINE_SESSION",
    )

    presentation = build_generated_workout_presentation(generated)
    summary = "\n".join(presentation.pages[0].lines)

    assert "Available time: 45:00" in summary
    assert "Known required: 39:34" in summary
    assert "Remaining after known: 5:26" in summary
    assert "Time feasibility: UNRESOLVED" in summary
    assert "Total duration" not in summary


def test_historical_generated_workout_omits_time_lines() -> None:
    generated = GeneratedWorkout(
        generated_workout_id="GW_20260901_001_V1",
        workout_version=1,
        workout=build_reference_workout(),
        pool_length_meters=12.5,
        generation_reason="BASELINE_SESSION",
    )

    presentation = build_generated_workout_presentation(generated)
    summary = "\n".join(presentation.pages[0].lines)

    assert "Available time:" not in summary
    assert "Time feasibility:" not in summary


def test_format_seconds_uses_minutes_and_seconds() -> None:
    assert format_seconds(0) == "0:00"
    assert format_seconds(38) == "0:38"
    assert format_seconds(102) == "1:42"
    assert format_seconds(1324) == "22:04"


def test_format_seconds_rejects_negative_duration() -> None:
    with pytest.raises(
        ValueError,
        match="Duration cannot be negative",
    ):
        format_seconds(-1)


def test_reference_workout_builds_summary_and_block_pages() -> None:
    presentation = build_swimmer_presentation(build_reference_workout())

    assert len(presentation.pages) == 9
    assert presentation.pages[0].block_sequence is None
    assert [page.block_sequence for page in presentation.pages[1:]] == list(range(1, 9))


def test_summary_reports_partial_timing_without_total_duration() -> None:
    presentation = build_swimmer_presentation(build_reference_workout())
    summary = "\n".join(presentation.pages[0].lines)

    assert "Distance: 2,600 m" in summary
    assert "Known swim: 22:04 across 1,400 m" in summary
    assert "Configured rest: 17:30" in summary
    assert "Untimed distance: 1,200 m" in summary
    assert "Timing: PARTIAL" in summary
    assert "Total duration" not in summary


def test_target_and_rest_are_visible_to_swimmer() -> None:
    presentation = build_swimmer_presentation(build_reference_workout())
    block_three = "\n".join(presentation.pages[3].lines)

    assert "5 x 100 m" in block_three
    assert "Target: 1:42" in block_three
    assert "Rest: 0:45 between repetitions" in block_three
    assert "none after final" not in block_three
    assert "including after final" not in block_three


def test_warm_up_includes_known_intensity() -> None:
    presentation = build_swimmer_presentation(build_reference_workout())
    warm_up = "\n".join(presentation.pages[1].lines)

    assert "200 m | Freestyle | Intensity: Recovery" in warm_up


def test_summary_hides_internal_workout_id() -> None:
    workout = build_reference_workout()
    presentation = build_swimmer_presentation(workout)
    rendered = render_plain_text(presentation)

    assert presentation.workout_id == workout.session_id
    assert workout.session_id not in rendered


def test_ordered_technical_sequence_is_not_collapsed() -> None:
    presentation = build_swimmer_presentation(build_reference_workout())
    block_eight = "\n".join(presentation.pages[8].lines)

    assert block_eight.count("100 m") == 5
    assert block_eight.count("Asymmetric") == 2
    assert block_eight.count("Unilateral") == 2
    assert "Equipment: Fins, Paddles" in block_eight
    assert "Rest: 0:30 between items" in block_eight


def test_plain_text_renderer_preserves_all_pages() -> None:
    presentation = build_swimmer_presentation(build_reference_workout())
    rendered = render_plain_text(presentation)

    assert rendered.count("Page ") == 9
    assert "BLOCK 1: Warm Up" in rendered
    assert "BLOCK 8: Technique" in rendered
    assert "Total duration" not in rendered
