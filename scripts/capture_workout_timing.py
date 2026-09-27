from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator

from adaptive_swimming.domain.session_results import GeneratedWorkout
from adaptive_swimming.domain.workout import RestApplication, TargetType
from adaptive_swimming.persistence.session_records import load_generated_workout
from adaptive_swimming.recording.timing_results import (
    convert_item_timing_to_repetition_results,
)
from adaptive_swimming.recording.workout_timing import (
    ElapsedRepetitionReading,
    ItemTimingCapture,
    ItemTimingSummary,
    calculate_item_timing,
)


class CaptureReadingInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repetition_number: int = Field(ge=1)
    finish_elapsed: str | int
    rest_before: str | int = 0
    note: str | None = None

    @field_validator("finish_elapsed", "rest_before")
    @classmethod
    def validate_elapsed_value(cls, value: str | int) -> str | int:
        parse_elapsed_seconds(value)
        return value


class TimingCaptureInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    generated_workout_id: str
    block_sequence: int = Field(ge=1)
    set_group_sequence: int = Field(ge=1)
    item_sequence: int = Field(ge=1)
    block_start_elapsed: str | int
    target_seconds: int | None = Field(default=None, gt=0)
    readings: tuple[CaptureReadingInput, ...] = Field(min_length=1)

    @field_validator("block_start_elapsed")
    @classmethod
    def validate_block_start(cls, value: str | int) -> str | int:
        parse_elapsed_seconds(value)
        return value


def parse_elapsed_seconds(value: str | int) -> int:
    if isinstance(value, int):
        if value < 0:
            raise ValueError("Elapsed seconds cannot be negative.")
        return value

    token = value.strip()
    if not token:
        raise ValueError("Elapsed time cannot be blank.")
    if token.isdigit():
        return int(token)

    parts = token.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError("Elapsed time must be integer seconds or MM:SS.")

    minutes, seconds = (int(part) for part in parts)
    if seconds > 59:
        raise ValueError("MM:SS seconds component must be between 00 and 59.")
    return minutes * 60 + seconds


def resolve_planned_item(
    generated_workout: GeneratedWorkout,
    *,
    block_sequence: int,
    set_group_sequence: int,
    item_sequence: int,
) -> tuple[Any, Any]:
    blocks = tuple(
        block for block in generated_workout.workout.blocks if block.sequence == block_sequence
    )
    if len(blocks) != 1:
        raise ValueError(f"Expected exactly one planned block; found {len(blocks)}.")

    groups = tuple(group for group in blocks[0].set_groups if group.sequence == set_group_sequence)
    if len(groups) != 1:
        raise ValueError(f"Expected exactly one planned set group; found {len(groups)}.")

    items = tuple(item for item in groups[0].items if item.sequence == item_sequence)
    if len(items) != 1:
        raise ValueError(f"Expected exactly one planned item; found {len(items)}.")
    return groups[0], items[0]


def prescribed_rest_seconds(group: Any) -> int | None:
    if group.rest is None:
        return None
    if group.rest.application not in {
        RestApplication.BETWEEN_REPETITIONS,
        RestApplication.BETWEEN_ITEMS,
    }:
        return None
    return cast(int, group.rest.seconds)


def planned_target_seconds(item: Any) -> int | None:
    if item.target is not None and item.target.target_type == TargetType.REPETITION_COMPLETION_TIME:
        return cast(int | None, item.target.target_seconds)
    return None


def build_capture_template(
    generated_workout: GeneratedWorkout,
    *,
    block_sequence: int,
    set_group_sequence: int,
    item_sequence: int,
) -> dict[str, Any]:
    group, item = resolve_planned_item(
        generated_workout,
        block_sequence=block_sequence,
        set_group_sequence=set_group_sequence,
        item_sequence=item_sequence,
    )
    rest = prescribed_rest_seconds(group)
    return {
        "generated_workout_id": generated_workout.generated_workout_id,
        "block_sequence": block_sequence,
        "set_group_sequence": set_group_sequence,
        "item_sequence": item_sequence,
        "block_start_elapsed": "MM:SS",
        "target_seconds": planned_target_seconds(item),
        "readings": [
            {
                "repetition_number": repetition_number,
                "finish_elapsed": "MM:SS",
                "rest_before": 0 if repetition_number == 1 else (rest or 0),
                "note": None,
            }
            for repetition_number in range(1, item.repetitions + 1)
        ],
    }


def load_capture(path: Path) -> TimingCaptureInput:
    if not path.is_file():
        raise FileNotFoundError(f"Timing capture file does not exist: {path}")
    return TimingCaptureInput.model_validate_json(path.read_text(encoding="utf-8"))


def calculate_capture(
    *,
    generated_workout: GeneratedWorkout,
    capture_input: TimingCaptureInput,
) -> tuple[ItemTimingSummary, tuple[Any, ...]]:
    if capture_input.generated_workout_id != generated_workout.generated_workout_id:
        raise ValueError("Timing capture does not belong to the generated workout.")

    capture = ItemTimingCapture(
        block_sequence=capture_input.block_sequence,
        set_group_sequence=capture_input.set_group_sequence,
        item_sequence=capture_input.item_sequence,
        block_start_elapsed_seconds=parse_elapsed_seconds(capture_input.block_start_elapsed),
        target_seconds=capture_input.target_seconds,
        readings=tuple(
            ElapsedRepetitionReading(
                repetition_number=reading.repetition_number,
                finish_elapsed_seconds=parse_elapsed_seconds(reading.finish_elapsed),
                rest_before_seconds=parse_elapsed_seconds(reading.rest_before),
                note=reading.note,
            )
            for reading in capture_input.readings
        ),
    )
    summary = calculate_item_timing(capture)
    results = convert_item_timing_to_repetition_results(
        generated_workout=generated_workout,
        summary=summary,
    )
    return summary, results


def render_summary(summary: ItemTimingSummary) -> str:
    lines = [
        (
            "Coordinate: "
            f"{summary.block_sequence}, {summary.set_group_sequence}, "
            f"{summary.item_sequence}"
        ),
        f"Active seconds: {summary.active_seconds}",
        f"Rest seconds: {summary.rest_seconds}",
        f"Captured elapsed seconds: {summary.captured_elapsed_seconds}",
        f"Fastest seconds: {summary.fastest_seconds}",
        f"Slowest seconds: {summary.slowest_seconds}",
        f"Mean seconds: {summary.mean_seconds}",
        f"Median seconds: {summary.median_seconds}",
        f"Range seconds: {summary.range_seconds}",
    ]
    if summary.target_seconds is not None:
        lines.extend(
            (
                f"Target seconds: {summary.target_seconds}",
                f"Targets met: {summary.targets_met_count}/{len(summary.repetitions)}",
            )
        )
    lines.append("Writes performed: none")
    return "\n".join(lines)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or calculate a read-only workout timing capture."
    )
    parser.add_argument("--generated-workout", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--template", action="store_true")
    mode.add_argument("--capture", type=Path)
    parser.add_argument("--block-sequence", type=int)
    parser.add_argument("--set-group-sequence", type=int)
    parser.add_argument("--item-sequence", type=int)
    parser.add_argument("--output-format", choices=("summary", "json"), default="summary")
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    if not arguments.generated_workout.is_file():
        raise FileNotFoundError(
            f"Generated-workout file does not exist: {arguments.generated_workout}"
        )
    generated_workout = load_generated_workout(arguments.generated_workout)

    if arguments.template:
        coordinates = (
            arguments.block_sequence,
            arguments.set_group_sequence,
            arguments.item_sequence,
        )
        if any(value is None for value in coordinates):
            raise ValueError("Template mode requires all three coordinate arguments.")
        template = build_capture_template(
            generated_workout,
            block_sequence=arguments.block_sequence,
            set_group_sequence=arguments.set_group_sequence,
            item_sequence=arguments.item_sequence,
        )
        print(json.dumps(template, indent=2))
        return

    capture_input = load_capture(arguments.capture)
    summary, results = calculate_capture(
        generated_workout=generated_workout,
        capture_input=capture_input,
    )
    if arguments.output_format == "json":
        print(
            json.dumps(
                {
                    "timing_summary": summary.model_dump(mode="json"),
                    "repetition_results": [result.model_dump(mode="json") for result in results],
                    "writes_performed": False,
                },
                indent=2,
            )
        )
    else:
        print(render_summary(summary))


if __name__ == "__main__":
    main()
