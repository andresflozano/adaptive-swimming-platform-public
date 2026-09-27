from __future__ import annotations

from pathlib import Path

from adaptive_swimming.catalog.reference_workouts import (
    SESSION_ID,
    build_reference_workout,
)
from adaptive_swimming.domain.workout import WorkoutSession

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIRECTORY = PROJECT_ROOT / "data" / "golden"
OUTPUT_PATH = GOLDEN_DIRECTORY / f"{SESSION_ID}.json"


def export_golden_workout(
    output_path: Path = OUTPUT_PATH,
) -> WorkoutSession:
    workout = build_reference_workout()
    serialized_workout = workout.model_dump_json(indent=2)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    output_path.write_text(
        serialized_workout + "\n",
        encoding="utf-8",
    )

    loaded_workout = WorkoutSession.model_validate_json(output_path.read_text(encoding="utf-8"))

    if loaded_workout != workout:
        raise ValueError("Serialized golden workout does not match the source model.")

    return loaded_workout


def main() -> None:
    workout = export_golden_workout()

    print(f"Golden workout: {OUTPUT_PATH}")
    print(f"Session ID: {workout.session_id}")
    print(f"Source ID: {workout.source_id}")
    print(f"Total distance: {workout.total_distance_meters()} meters")


if __name__ == "__main__":
    main()
