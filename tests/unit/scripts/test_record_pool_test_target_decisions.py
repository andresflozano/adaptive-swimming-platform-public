from __future__ import annotations

from pathlib import Path

import pytest
import scripts.record_pool_test_target_decisions as workflow

from adaptive_swimming.catalog.reference_workouts import build_reference_workout
from adaptive_swimming.domain.session_results import (
    BlockResult,
    CompletionStatus,
    GeneratedWorkout,
    RepetitionResult,
    WorkoutSessionResult,
)
from adaptive_swimming.persistence.session_records import (
    save_generated_workout,
    save_session_result,
)
from adaptive_swimming.persistence.target_review_records import (
    load_target_review_decision,
)
from adaptive_swimming.planning.target_review_decisions import (
    TargetReviewDecision,
    TargetReviewDecisionType,
)
from adaptive_swimming.planning.workout_proposal import build_pool_test_two_workout


def repetitions(
    *,
    block_sequence: int,
    values: tuple[int, ...],
) -> tuple[RepetitionResult, ...]:
    return tuple(
        RepetitionResult(
            block_sequence=block_sequence,
            set_group_sequence=1,
            item_sequence=1,
            repetition_number=index,
            completed=True,
            actual_seconds=value,
        )
        for index, value in enumerate(values, start=1)
    )


def write_input_records(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    input_root = tmp_path / "inputs"
    generated_directory = input_root / "generated_workouts"
    result_directory = input_root / "session_results"

    workout_one = GeneratedWorkout(
        generated_workout_id="GW_20260901_001_V1",
        workout_version=1,
        workout=build_reference_workout(),
        pool_length_meters=12.5,
        generation_reason="BASELINE_SESSION",
    )
    result_one = WorkoutSessionResult(
        session_result_id="SR_20260901_001_V2",
        generated_workout_id=workout_one.generated_workout_id,
        result_version=2,
        completion_status=CompletionStatus.STOPPED_EARLY,
        completed_distance_meters=400,
        actual_total_seconds=2700,
        block_results=(
            BlockResult(
                block_sequence=2,
                completed_distance_meters=200,
                completed_as_written=True,
                repetition_results=repetitions(
                    block_sequence=2,
                    values=(155, 155),
                ),
            ),
            BlockResult(
                block_sequence=4,
                completed_distance_meters=200,
                completed_as_written=True,
                repetition_results=repetitions(
                    block_sequence=4,
                    values=(62, 65, 65, 75),
                ),
            ),
        ),
    )

    workout_two = GeneratedWorkout(
        generated_workout_id="GW_20260903_001_V1",
        workout_version=1,
        workout=build_pool_test_two_workout(),
        pool_length_meters=12.5,
        available_training_seconds=3600,
        generation_reason="POOL_TEST_2_TIME_CONSTRAINED_PROPOSAL",
    )
    result_two = WorkoutSessionResult(
        session_result_id="SR_20260903_001_V2",
        generated_workout_id=workout_two.generated_workout_id,
        result_version=2,
        completion_status=CompletionStatus.STOPPED_EARLY,
        completed_distance_meters=400,
        actual_total_seconds=3093,
        block_results=(
            BlockResult(
                block_sequence=2,
                completed_distance_meters=200,
                completed_as_written=True,
                repetition_results=repetitions(
                    block_sequence=2,
                    values=(157, 157),
                ),
            ),
            BlockResult(
                block_sequence=4,
                completed_distance_meters=200,
                completed_as_written=True,
                repetition_results=repetitions(
                    block_sequence=4,
                    values=(65, 64, 62, 64),
                ),
            ),
        ),
    )

    return (
        save_generated_workout(workout_one, generated_directory),
        save_session_result(workout_one, result_one, result_directory),
        save_generated_workout(workout_two, generated_directory),
        save_session_result(workout_two, result_two, result_directory),
    )


def run_workflow(tmp_path: Path) -> tuple[Path, Path]:
    paths = write_input_records(tmp_path)
    return workflow.record_pool_test_target_decisions(
        pool_test_one_workout_path=paths[0],
        pool_test_one_result_path=paths[1],
        pool_test_two_workout_path=paths[2],
        pool_test_two_result_path=paths[3],
        decision_directory=tmp_path / "output",
    )


def test_workflow_persists_expected_decisions(tmp_path: Path) -> None:
    accepted_path, deferred_path = run_workflow(tmp_path)
    accepted = load_target_review_decision(accepted_path)
    deferred = load_target_review_decision(deferred_path)

    assert accepted.review_decision_id == "TRD_20260905_001_V1"
    assert accepted.decision == TargetReviewDecisionType.ACCEPTED_FOR_FUTURE_WORKOUT
    assert accepted.reviewed_target_seconds == 65
    assert deferred.review_decision_id == "TRD_20260905_002_V1"
    assert deferred.decision == TargetReviewDecisionType.DEFERRED
    assert deferred.reviewed_target_seconds == 156


def test_decisions_preserve_both_source_result_ids(tmp_path: Path) -> None:
    paths = run_workflow(tmp_path)
    expected = (
        "SR_20260901_001_V2",
        "SR_20260903_001_V2",
    )
    assert load_target_review_decision(paths[0]).proposal.source_session_result_ids == expected
    assert load_target_review_decision(paths[1]).proposal.source_session_result_ids == expected


@pytest.mark.parametrize("existing_index", (0, 1))
def test_existing_destination_prevents_all_writes(
    tmp_path: Path,
    existing_index: int,
) -> None:
    input_paths = write_input_records(tmp_path)
    output = tmp_path / "output"
    destinations = (
        output / "TRD_20260905_001_V1.json",
        output / "TRD_20260905_002_V1.json",
    )
    existing = destinations[existing_index]
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError, match="partial or duplicate"):
        workflow.record_pool_test_target_decisions(
            pool_test_one_workout_path=input_paths[0],
            pool_test_one_result_path=input_paths[1],
            pool_test_two_workout_path=input_paths[2],
            pool_test_two_result_path=input_paths[3],
            decision_directory=output,
        )

    assert existing.read_text(encoding="utf-8") == "existing"
    assert [path.exists() for path in destinations].count(True) == 1


def test_second_write_failure_rolls_back_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_paths = write_input_records(tmp_path)
    output = tmp_path / "output"
    original = workflow.save_target_review_decision
    calls = 0

    def fail_second(
        decision: TargetReviewDecision,
        directory: Path,
    ) -> Path:
        nonlocal calls
        calls += 1

        if calls == 2:
            raise RuntimeError("Simulated second-write failure")

        return original(
            decision,
            directory,
        )

    monkeypatch.setattr(workflow, "save_target_review_decision", fail_second)
    with pytest.raises(RuntimeError, match="second-write"):
        workflow.record_pool_test_target_decisions(
            pool_test_one_workout_path=input_paths[0],
            pool_test_one_result_path=input_paths[1],
            pool_test_two_workout_path=input_paths[2],
            pool_test_two_result_path=input_paths[3],
            decision_directory=output,
        )
    assert not tuple(output.glob("*.json"))


def test_post_write_validation_failure_rolls_back_both(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_paths = write_input_records(tmp_path)
    output = tmp_path / "output"

    def fail_validation(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Simulated post-write validation failure")

    monkeypatch.setattr(workflow, "validate_persisted_decisions", fail_validation)
    with pytest.raises(RuntimeError, match="post-write"):
        workflow.record_pool_test_target_decisions(
            pool_test_one_workout_path=input_paths[0],
            pool_test_one_result_path=input_paths[1],
            pool_test_two_workout_path=input_paths[2],
            pool_test_two_result_path=input_paths[3],
            decision_directory=output,
        )
    assert not tuple(output.glob("*.json"))


def test_input_records_remain_unchanged(tmp_path: Path) -> None:
    input_paths = write_input_records(tmp_path)
    before = tuple(path.read_bytes() for path in input_paths)
    workflow.record_pool_test_target_decisions(
        pool_test_one_workout_path=input_paths[0],
        pool_test_one_result_path=input_paths[1],
        pool_test_two_workout_path=input_paths[2],
        pool_test_two_result_path=input_paths[3],
        decision_directory=tmp_path / "output",
    )
    assert tuple(path.read_bytes() for path in input_paths) == before


def test_success_leaves_no_temporary_files(tmp_path: Path) -> None:
    run_workflow(tmp_path)
    assert not tuple(tmp_path.rglob("*.tmp"))
