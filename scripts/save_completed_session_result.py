from __future__ import annotations

import argparse
from pathlib import Path

from adaptive_swimming.persistence.session_records import (
    SESSION_RESULTS_DIRECTORY,
    load_generated_workout,
    load_session_result,
    save_session_result,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and persist a completed workout-session result "
            "without overwriting an existing record."
        )
    )
    parser.add_argument(
        "--generated-workout",
        required=True,
        type=Path,
        help="Path to the persisted generated-workout JSON.",
    )
    parser.add_argument(
        "--result-draft",
        required=True,
        type=Path,
        help="Path to the completed session-result draft JSON.",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=SESSION_RESULTS_DIRECTORY,
        help="Directory for the validated session-result record.",
    )
    return parser.parse_args()


def save_completed_result_from_draft(
    *,
    generated_workout_path: Path,
    result_draft_path: Path,
    output_directory: Path = SESSION_RESULTS_DIRECTORY,
) -> Path:
    if not generated_workout_path.is_file():
        raise FileNotFoundError(f"Generated-workout file does not exist: {generated_workout_path}")

    if not result_draft_path.is_file():
        raise FileNotFoundError(f"Session-result draft does not exist: {result_draft_path}")

    generated_workout = load_generated_workout(generated_workout_path)
    session_result = load_session_result(result_draft_path)

    return save_session_result(
        generated_workout,
        session_result,
        output_directory,
    )


def main() -> None:
    arguments = parse_arguments()

    result_path = save_completed_result_from_draft(
        generated_workout_path=arguments.generated_workout,
        result_draft_path=arguments.result_draft,
        output_directory=arguments.output_directory,
    )

    saved_result = load_session_result(result_path)

    print(f"Saved session result: {result_path}")
    print(f"Result ID: {saved_result.session_result_id}")
    print(f"Completion status: {saved_result.completion_status.value}")
    print(f"Completed distance: {saved_result.completed_distance_meters} m")
    print(f"Actual elapsed time: {saved_result.actual_total_seconds} seconds")


if __name__ == "__main__":
    main()
