from __future__ import annotations

import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TypeVar

from pydantic import BaseModel

from adaptive_swimming.domain.session_results import (
    GeneratedWorkout,
    WorkoutSessionResult,
    validate_session_result,
)

RecordModel = TypeVar(
    "RecordModel",
    bound=BaseModel,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOCAL_RECORDS_DIRECTORY = PROJECT_ROOT / "data" / "local_records"
GENERATED_WORKOUTS_DIRECTORY = LOCAL_RECORDS_DIRECTORY / "generated_workouts"
SESSION_RESULTS_DIRECTORY = LOCAL_RECORDS_DIRECTORY / "session_results"
PROPOSALS_DIRECTORY = (
    LOCAL_RECORDS_DIRECTORY / "proposals"
)
PROPOSAL_ACCEPTANCES_DIRECTORY = (
    LOCAL_RECORDS_DIRECTORY / "proposal_acceptances"
)
RECALIBRATED_TARGET_REVIEWS_DIRECTORY = (
    LOCAL_RECORDS_DIRECTORY / "recalibrated_target_reviews"
)
TARGET_REVIEW_DECISIONS_DIRECTORY = (
    LOCAL_RECORDS_DIRECTORY / "target_review_decisions"
)

GENERATED_WORKOUT_ID_PATTERN = re.compile(r"^GW_[0-9]{8}_[0-9]{3}_V[0-9]+$")
SESSION_RESULT_ID_PATTERN = re.compile(r"^SR_[0-9]{8}_[0-9]{3}_V[0-9]+$")


def validate_record_id(
    identifier: str,
    pattern: re.Pattern[str],
    record_type: str,
) -> None:
    if pattern.fullmatch(identifier) is None:
        raise ValueError(f"Invalid {record_type} identifier: {identifier}")


def generated_workout_path(
    generated_workout_id: str,
    directory: Path = GENERATED_WORKOUTS_DIRECTORY,
) -> Path:
    validate_record_id(
        generated_workout_id,
        GENERATED_WORKOUT_ID_PATTERN,
        "generated workout",
    )
    return directory / f"{generated_workout_id}.json"


def session_result_path(
    session_result_id: str,
    directory: Path = SESSION_RESULTS_DIRECTORY,
) -> Path:
    validate_record_id(
        session_result_id,
        SESSION_RESULT_ID_PATTERN,
        "session result",
    )
    return directory / f"{session_result_id}.json"


def write_new_json_record(
    record: BaseModel,
    destination: Path,
) -> Path:
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing record: {destination}")

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    serialized_record = record.model_dump_json(indent=2) + "\n"
    temporary_path: Path | None = None

    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(serialized_record)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        type(record).model_validate_json(temporary_path.read_text(encoding="utf-8"))

        try:
            os.link(temporary_path, destination)
        except FileExistsError as error:
            raise FileExistsError(
                f"Refusing to overwrite existing record: {destination}"
            ) from error

        return destination
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def load_generated_workout(
    path: Path,
) -> GeneratedWorkout:
    return GeneratedWorkout.model_validate_json(path.read_text(encoding="utf-8"))


def save_generated_workout(
    generated_workout: GeneratedWorkout,
    directory: Path = GENERATED_WORKOUTS_DIRECTORY,
) -> Path:
    destination = generated_workout_path(
        generated_workout.generated_workout_id,
        directory,
    )
    written_path = write_new_json_record(
        generated_workout,
        destination,
    )

    loaded = load_generated_workout(written_path)

    if loaded != generated_workout:
        raise ValueError("Persisted generated workout does not match the source record.")

    return written_path


def load_session_result(
    path: Path,
) -> WorkoutSessionResult:
    return WorkoutSessionResult.model_validate_json(path.read_text(encoding="utf-8"))


def save_session_result(
    generated_workout: GeneratedWorkout,
    session_result: WorkoutSessionResult,
    directory: Path = SESSION_RESULTS_DIRECTORY,
) -> Path:
    validate_session_result(
        generated_workout,
        session_result,
    )
    destination = session_result_path(
        session_result.session_result_id,
        directory,
    )
    written_path = write_new_json_record(
        session_result,
        destination,
    )

    loaded = load_session_result(written_path)
    validate_session_result(
        generated_workout,
        loaded,
    )

    if loaded != session_result:
        raise ValueError("Persisted session result does not match the source record.")

    return written_path
