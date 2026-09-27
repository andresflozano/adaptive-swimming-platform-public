from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

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
    GENERATED_WORKOUTS_DIRECTORY,
    SESSION_RESULTS_DIRECTORY,
    generated_workout_path,
    load_generated_workout,
    save_generated_workout,
    save_session_result,
    session_result_path,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Create linked local records for the baseline pool test.")
    )
    parser.add_argument(
        "--date",
        required=True,
        help="Pool-test date as YYYYMMDD.",
    )
    parser.add_argument(
        "--sequence",
        type=int,
        default=1,
        help="Daily test sequence, starting at 1.",
    )
    parser.add_argument(
        "--pool-length",
        type=float,
        required=True,
        help="Pool length in meters, including fractional lengths such as 12.5.",
    )
    parser.add_argument(
        "--available-minutes",
        type=int,
        required=True,
        help="Available training time in whole minutes.",
    )
    return parser.parse_args()


def validate_date_text(date_text: str) -> None:
    if len(date_text) != 8 or not date_text.isdigit():
        raise ValueError("Date must use YYYYMMDD format.")

    try:
        datetime.strptime(date_text, "%Y%m%d")
    except ValueError as error:
        raise ValueError("Date must be a valid calendar date in YYYYMMDD format.") from error


def create_baseline_pool_test_records(
    *,
    date_text: str,
    sequence: int,
    pool_length_meters: float,
    available_training_minutes: int,
    generated_directory: Path = GENERATED_WORKOUTS_DIRECTORY,
    result_directory: Path = SESSION_RESULTS_DIRECTORY,
) -> tuple[Path, Path]:
    validate_date_text(date_text)

    if available_training_minutes < 1:
        raise ValueError("Available training time must be at least one minute.")

    if sequence < 1:
        raise ValueError("Sequence must be at least one.")

    if pool_length_meters < 1:
        raise ValueError("Pool length must be at least one meter.")

    sequence_text = f"{sequence:03d}"
    generated_workout_id = f"GW_{date_text}_{sequence_text}_V1"
    session_result_id = f"SR_{date_text}_{sequence_text}_V1"

    generated_path = generated_workout_path(
        generated_workout_id,
        generated_directory,
    )
    result_path = session_result_path(
        session_result_id,
        result_directory,
    )

    existing_paths = tuple(path for path in (generated_path, result_path) if path.exists())

    if existing_paths:
        raise FileExistsError(
            f"Refusing to create a partial or duplicate baseline record pair: {existing_paths}"
        )

    generated_workout = GeneratedWorkout(
        generated_workout_id=generated_workout_id,
        workout_version=1,
        workout=build_reference_workout(),
        pool_length_meters=pool_length_meters,
        available_training_seconds=(available_training_minutes * 60),
        equipment_available=(
            EquipmentCode.FINS,
            EquipmentCode.PADDLES,
            EquipmentCode.KICKBOARD,
        ),
        generation_reason="BASELINE_SESSION",
    )

    session_result = WorkoutSessionResult(
        session_result_id=session_result_id,
        generated_workout_id=generated_workout_id,
        result_version=1,
        completion_status=CompletionStatus.NOT_STARTED,
        completed_distance_meters=0,
        equipment_used=(),
        block_results=(),
        safety_issue_reported=False,
        notes=None,
    )

    written_generated_path: Path | None = None

    try:
        written_generated_path = save_generated_workout(
            generated_workout,
            generated_directory,
        )
        written_result_path = save_session_result(
            generated_workout,
            session_result,
            result_directory,
        )
    except Exception:
        if written_generated_path is not None and written_generated_path.exists():
            written_generated_path.unlink()

        raise

    return written_generated_path, written_result_path


def main() -> None:
    arguments = parse_arguments()

    generated_path, result_path = create_baseline_pool_test_records(
        date_text=arguments.date,
        sequence=arguments.sequence,
        pool_length_meters=arguments.pool_length,
        available_training_minutes=(arguments.available_minutes),
    )

    generated_workout = load_generated_workout(generated_path)

    print(f"Generated workout: {generated_path}")
    print(f"Blank session result: {result_path}")
    print(f"Planned distance: {generated_workout.planned_distance_meters} m")
    print(f"Configured rest: {generated_workout.configured_rest_seconds} seconds")
    print(f"Known swim: {generated_workout.known_swim_seconds} seconds")
    print(f"Unresolved distance: {generated_workout.unresolved_distance_meters} m")
    print(f"Pool length: {generated_workout.pool_length_meters} m")
    print(f"Available training time: {generated_workout.available_training_seconds} seconds")


if __name__ == "__main__":
    main()
