from __future__ import annotations

from pydantic import Field

from adaptive_swimming.domain.session_results import (
    GeneratedWorkout,
)
from adaptive_swimming.domain.workout import (
    IntensityCode,
    RestApplication,
    SetGroup,
    SetItem,
    StrictDomainModel,
    WorkoutBlock,
    WorkoutSession,
)
from adaptive_swimming.planning.time_feasibility import (
    evaluate_time_feasibility,
)


class SwimmerWorkoutPage(StrictDomainModel):
    page_number: int = Field(ge=1)
    page_count: int = Field(ge=1)
    block_sequence: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=1)
    lines: tuple[str, ...] = Field(min_length=1)
    footer: str | None = None


class SwimmerWorkoutPresentation(StrictDomainModel):
    workout_id: str
    pages: tuple[SwimmerWorkoutPage, ...] = Field(min_length=1)


def build_generated_workout_presentation(
    generated_workout: GeneratedWorkout,
) -> SwimmerWorkoutPresentation:
    presentation = build_swimmer_presentation(generated_workout.workout)
    feasibility = evaluate_time_feasibility(generated_workout)

    summary_page = presentation.pages[0]
    additional_lines: list[str] = []

    if feasibility.available_seconds is not None:
        remaining = feasibility.remaining_after_known_seconds

        additional_lines.extend(
            (
                (f"Available time: {format_seconds(feasibility.available_seconds)}"),
                (f"Known required: {format_seconds(feasibility.known_required_seconds)}"),
            )
        )

        if remaining is None:
            raise ValueError(
                "Remaining time must be available when available training time is provided."
            )

        if remaining >= 0:
            additional_lines.append(f"Remaining after known: {format_seconds(remaining)}")
        else:
            additional_lines.append(
                f"Known work exceeds available time by: {format_seconds(abs(remaining))}"
            )

        additional_lines.append(f"Time feasibility: {feasibility.status.value}")

    updated_summary = summary_page.model_copy(
        update={
            "lines": (
                *summary_page.lines,
                *additional_lines,
            )
        }
    )

    return presentation.model_copy(
        update={
            "pages": (
                updated_summary,
                *presentation.pages[1:],
            )
        }
    )


def format_seconds(total_seconds: int) -> str:
    if total_seconds < 0:
        raise ValueError("Duration cannot be negative.")

    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


def format_rest(set_group: SetGroup) -> str | None:
    if set_group.rest is None:
        return None

    if set_group.rest.application == RestApplication.BETWEEN_REPETITIONS:
        application = "between repetitions"
    elif set_group.rest.application == RestApplication.BETWEEN_ITEMS:
        application = "between items"
    else:
        application = "between cycles"

    suffix = ", including after final" if set_group.rest.include_after_final else ""

    return f"Rest: {format_seconds(set_group.rest.seconds)} {application}{suffix}"


def format_item(item: SetItem) -> str:
    distance = f"{item.distance_meters} m"

    if item.repetitions > 1:
        instruction = f"{item.repetitions} x {distance}"
    else:
        instruction = distance

    instruction += f" | {item.exercise.value.replace('_', ' ').title()}"

    if item.intensity != IntensityCode.UNRESOLVED:
        intensity = item.intensity.value.replace("_", " ").title()
        instruction += f" | Intensity: {intensity}"

    if item.equipment:
        equipment = ", ".join(
            item_code.value.replace("_", " ").title() for item_code in item.equipment
        )
        instruction += f" | Equipment: {equipment}"

    if item.target is not None and item.target.target_seconds is not None:
        instruction += f" | Target: {format_seconds(item.target.target_seconds)}"

    if item.swimmer_instruction is not None:
        instruction += f" | {item.swimmer_instruction}"

    return instruction


def format_set_group(
    set_group: SetGroup,
) -> tuple[str, ...]:
    lines: list[str] = []

    if set_group.repeat_cycles > 1:
        lines.append(f"Repeat group {set_group.repeat_cycles} times")

    lines.extend(format_item(item) for item in set_group.items)

    rest_line = format_rest(set_group)

    if rest_line is not None:
        lines.append(rest_line)

    return tuple(lines)


def format_block(
    block: WorkoutBlock,
) -> tuple[str, ...]:
    lines: list[str] = []

    for set_group in block.set_groups:
        lines.extend(format_set_group(set_group))

    return tuple(lines)


def build_swimmer_presentation(
    workout: WorkoutSession,
) -> SwimmerWorkoutPresentation:
    duration = workout.swim_duration_summary()

    summary_lines = (
        f"Distance: {workout.total_distance_meters():,} m",
        (
            f"Known swim: {format_seconds(duration.known_seconds)} "
            f"across {duration.known_distance_meters:,} m"
        ),
        (f"Configured rest: {format_seconds(workout.total_rest_seconds())}"),
        (f"Untimed distance: {duration.unresolved_distance_meters:,} m"),
        ("Timing: COMPLETE" if duration.is_complete else "Timing: PARTIAL"),
    )

    page_count = len(workout.blocks) + 1
    pages: list[SwimmerWorkoutPage] = [
        SwimmerWorkoutPage(
            page_number=1,
            page_count=page_count,
            title="SWIM WORKOUT",
            lines=summary_lines,
        )
    ]

    for page_number, block in enumerate(
        workout.blocks,
        start=2,
    ):
        title = f"BLOCK {block.sequence}: {block.role.value.replace('_', ' ').title()}"

        pages.append(
            SwimmerWorkoutPage(
                page_number=page_number,
                page_count=page_count,
                block_sequence=block.sequence,
                title=title,
                lines=format_block(block),
                footer=(f"Block {block.sequence} of {len(workout.blocks)}"),
            )
        )

    return SwimmerWorkoutPresentation(
        workout_id=workout.session_id,
        pages=tuple(pages),
    )


def render_plain_text(
    presentation: SwimmerWorkoutPresentation,
) -> str:
    rendered_pages: list[str] = []

    for page in presentation.pages:
        page_lines = [
            page.title,
            "",
            *page.lines,
        ]

        if page.footer is not None:
            page_lines.extend(
                [
                    "",
                    page.footer,
                ]
            )

        page_lines.append(f"Page {page.page_number}/{page.page_count}")
        rendered_pages.append("\n".join(page_lines))

    return "\n\n---\n\n".join(rendered_pages) + "\n"
