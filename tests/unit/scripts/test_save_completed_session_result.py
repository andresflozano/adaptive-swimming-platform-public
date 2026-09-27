from pathlib import Path

import pytest
from scripts.save_completed_session_result import (
    save_completed_result_from_draft,
)

from adaptive_swimming.catalog.reference_workouts import (
    build_reference_workout,
)
from adaptive_swimming.domain.session_results import (
    CompletionStatus,
    GeneratedWorkout,
    WorkoutSessionResult,
)
from adaptive_swimming.persistence.session_records import (
    load_session_result,
    save_generated_workout,
)


def build_generated_workout() -> GeneratedWorkout:
    return GeneratedWorkout(
        generated_workout_id="GW_20260901_001_V1",
        workout_version=1,
        workout=build_reference_workout(),
        pool_length_meters=12.5,
        generation_reason="BASELINE_SESSION",
    )


def build_completed_result() -> WorkoutSessionResult:
    return WorkoutSessionResult(
        session_result_id="SR_20260901_001_V2",
        generated_workout_id="GW_20260901_001_V1",
        result_version=2,
        completion_status=CompletionStatus.STOPPED_EARLY,
        completed_distance_meters=1100,
        actual_total_seconds=2700,
        perceived_exertion=5,
        safety_issue_reported=False,
        notes="Synthetic completed-result test fixture.",
    )


def write_result_draft(
    path: Path,
    result: WorkoutSessionResult,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        result.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )


def test_completed_result_is_validated_and_persisted(
    tmp_path: Path,
) -> None:
    generated_directory = tmp_path / "generated"
    draft_directory = tmp_path / "drafts"
    result_directory = tmp_path / "results"

    generated = build_generated_workout()
    generated_path = save_generated_workout(
        generated,
        generated_directory,
    )

    result = build_completed_result()
    draft_path = draft_directory / "completed-result.json"
    write_result_draft(draft_path, result)

    saved_path = save_completed_result_from_draft(
        generated_workout_path=generated_path,
        result_draft_path=draft_path,
        output_directory=result_directory,
    )
    loaded = load_session_result(saved_path)

    assert saved_path == (result_directory / "SR_20260901_001_V2.json")
    assert loaded == result


def test_completed_result_refuses_overwrite(
    tmp_path: Path,
) -> None:
    generated = build_generated_workout()
    generated_path = save_generated_workout(
        generated,
        tmp_path / "generated",
    )

    result = build_completed_result()
    draft_path = tmp_path / "draft.json"
    result_directory = tmp_path / "results"
    write_result_draft(draft_path, result)

    save_completed_result_from_draft(
        generated_workout_path=generated_path,
        result_draft_path=draft_path,
        output_directory=result_directory,
    )

    with pytest.raises(
        FileExistsError,
        match="Refusing to overwrite",
    ):
        save_completed_result_from_draft(
            generated_workout_path=generated_path,
            result_draft_path=draft_path,
            output_directory=result_directory,
        )


def test_completed_result_rejects_wrong_workout_link(
    tmp_path: Path,
) -> None:
    generated = build_generated_workout()
    generated_path = save_generated_workout(
        generated,
        tmp_path / "generated",
    )

    invalid_result = build_completed_result().model_copy(
        update={
            "generated_workout_id": "GW_20260901_002_V1",
        }
    )
    draft_path = tmp_path / "invalid-draft.json"
    result_directory = tmp_path / "results"
    write_result_draft(
        draft_path,
        invalid_result,
    )

    with pytest.raises(
        ValueError,
        match="does not belong",
    ):
        save_completed_result_from_draft(
            generated_workout_path=generated_path,
            result_draft_path=draft_path,
            output_directory=result_directory,
        )

    assert not result_directory.exists()


def test_completed_result_requires_generated_workout_file(
    tmp_path: Path,
) -> None:
    result = build_completed_result()
    draft_path = tmp_path / "draft.json"
    write_result_draft(draft_path, result)

    with pytest.raises(
        FileNotFoundError,
        match="Generated-workout file does not exist",
    ):
        save_completed_result_from_draft(
            generated_workout_path=(tmp_path / "missing-generated.json"),
            result_draft_path=draft_path,
            output_directory=tmp_path / "results",
        )


def test_completed_result_requires_draft_file(
    tmp_path: Path,
) -> None:
    generated = build_generated_workout()
    generated_path = save_generated_workout(
        generated,
        tmp_path / "generated",
    )

    with pytest.raises(
        FileNotFoundError,
        match="Session-result draft does not exist",
    ):
        save_completed_result_from_draft(
            generated_workout_path=generated_path,
            result_draft_path=(tmp_path / "missing-draft.json"),
            output_directory=tmp_path / "results",
        )
