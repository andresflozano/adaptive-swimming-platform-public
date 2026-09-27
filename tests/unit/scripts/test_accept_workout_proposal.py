import subprocess
import sys
from pathlib import Path

import pytest
import scripts.accept_workout_proposal as acceptance_script

from adaptive_swimming.catalog.reference_workouts import build_reference_workout
from adaptive_swimming.domain.session_results import (
    CompletionStatus,
    GeneratedWorkout,
    WorkoutSessionResult,
    validate_session_result,
)
from adaptive_swimming.persistence.proposal_records import (
    load_proposal,
    load_proposal_acceptance,
    save_proposal,
)
from adaptive_swimming.persistence.session_records import (
    load_generated_workout,
    load_session_result,
    save_generated_workout,
    save_session_result,
)
from adaptive_swimming.planning.proposal_acceptance import (
    build_not_started_result,
    build_proposal_acceptance,
)
from adaptive_swimming.planning.workout_proposal import (
    NextWorkoutProposal,
    build_pool_test_two_proposal,
)


def write_parent_inputs(tmp_path: Path) -> tuple[Path, Path]:
    parent = GeneratedWorkout(
        generated_workout_id="GW_20260901_001_V1",
        workout_version=1,
        workout=build_reference_workout(),
        pool_length_meters=12.5,
        generation_reason="BASELINE_SESSION",
    )
    result = WorkoutSessionResult(
        session_result_id="SR_20260901_001_V2",
        generated_workout_id=parent.generated_workout_id,
        result_version=2,
        completion_status=CompletionStatus.STOPPED_EARLY,
        completed_distance_meters=1100,
        actual_total_seconds=2700,
        perceived_exertion=5,
    )
    parent_path = save_generated_workout(parent, tmp_path / "inputs" / "generated")
    result_path = save_session_result(parent, result, tmp_path / "inputs" / "results")
    return parent_path, result_path


def persist_proposal(tmp_path: Path) -> Path:
    parent_path, result_path = write_parent_inputs(tmp_path)
    parent = load_generated_workout(parent_path)
    result = load_session_result(result_path)
    proposal = build_pool_test_two_proposal(parent, result)

    return save_proposal(
        proposal,
        tmp_path / "generic-input" / "proposals",
    )


def generic_output_directories(tmp_path: Path) -> dict[str, Path]:
    return {
        "acceptance_directory": tmp_path / "generic-output" / "acceptances",
        "generated_directory": tmp_path / "generic-output" / "generated",
        "result_directory": tmp_path / "generic-output" / "results",
    }


def output_directories(tmp_path: Path) -> dict[str, Path]:
    return {
        "proposal_directory": tmp_path / "output" / "proposals",
        "acceptance_directory": tmp_path / "output" / "acceptances",
        "generated_directory": tmp_path / "output" / "generated",
        "result_directory": tmp_path / "output" / "results",
    }


def accept(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    parent_path, result_path = write_parent_inputs(tmp_path)
    return acceptance_script.accept_pool_test_two_proposal(
        parent_generated_workout_path=parent_path,
        previous_result_path=result_path,
        **output_directories(tmp_path),
    )


def test_direct_file_cli_help_succeeds() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/accept_workout_proposal.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "--proposal" in completed.stdout
    assert "ModuleNotFoundError" not in completed.stderr


def test_module_cli_help_succeeds() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.accept_workout_proposal", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "--proposal" in completed.stdout


def test_generic_acceptance_persists_three_linked_records(tmp_path: Path) -> None:
    proposal_path = persist_proposal(tmp_path)
    proposal = load_proposal(proposal_path)

    paths = acceptance_script.accept_workout_proposal(
        proposal_path_value=proposal_path,
        **generic_output_directories(tmp_path),
    )

    acceptance = load_proposal_acceptance(paths[0])
    generated = load_generated_workout(paths[1])
    result = load_session_result(paths[2])

    assert len(paths) == 3
    assert acceptance == build_proposal_acceptance(proposal)
    assert generated == proposal.proposed_generated_workout
    assert result == build_not_started_result(proposal)


def test_generic_acceptance_preserves_source_proposal(tmp_path: Path) -> None:
    proposal_path = persist_proposal(tmp_path)
    before = proposal_path.read_bytes()

    acceptance_script.accept_workout_proposal(
        proposal_path_value=proposal_path,
        **generic_output_directories(tmp_path),
    )

    assert proposal_path.read_bytes() == before


def test_generic_acceptance_rejects_missing_proposal(tmp_path: Path) -> None:
    directories = generic_output_directories(tmp_path)

    with pytest.raises(FileNotFoundError, match="Proposal file does not exist"):
        acceptance_script.accept_workout_proposal(
            proposal_path_value=tmp_path / "missing.json",
            **directories,
        )

    assert not (tmp_path / "generic-output").exists()


@pytest.mark.parametrize("existing_index", range(3))
def test_generic_existing_destination_prevents_all_writes(
    tmp_path: Path,
    existing_index: int,
) -> None:
    proposal_path = persist_proposal(tmp_path)
    proposal = load_proposal(proposal_path)
    acceptance = build_proposal_acceptance(proposal)
    result = build_not_started_result(proposal)
    directories = generic_output_directories(tmp_path)

    expected = (
        directories["acceptance_directory"] / f"{acceptance.acceptance_id}.json",
        directories["generated_directory"]
        / f"{proposal.proposed_generated_workout.generated_workout_id}.json",
        directories["result_directory"] / f"{result.session_result_id}.json",
    )

    existing = expected[existing_index]
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError, match="partial or duplicate"):
        acceptance_script.accept_workout_proposal(
            proposal_path_value=proposal_path,
            **directories,
        )

    assert existing.read_text(encoding="utf-8") == "existing"
    assert [path.exists() for path in expected].count(True) == 1


def test_generic_acceptance_supports_non_pool_test_identity(tmp_path: Path) -> None:
    original_path = persist_proposal(tmp_path)
    original = load_proposal(original_path)
    payload = original.model_dump()

    payload["proposal_id"] = "NWP_20261001_007_V1"
    payload["proposed_generated_workout"]["generated_workout_id"] = "GW_20261001_007_V1"

    synthetic = NextWorkoutProposal.model_validate(payload)
    proposal_path = save_proposal(
        synthetic,
        tmp_path / "synthetic" / "proposals",
    )

    paths = acceptance_script.accept_workout_proposal(
        proposal_path_value=proposal_path,
        **generic_output_directories(tmp_path),
    )

    acceptance = load_proposal_acceptance(paths[0])
    generated = load_generated_workout(paths[1])
    result = load_session_result(paths[2])

    assert acceptance.acceptance_id == "NWA_20261001_007_V1"
    assert acceptance.proposal_id == "NWP_20261001_007_V1"
    assert generated.generated_workout_id == "GW_20261001_007_V1"
    assert result.session_result_id == "SR_20261001_007_V1"


@pytest.mark.parametrize(
    ("function_name", "error_text"),
    (
        ("save_proposal_acceptance", "acceptance write"),
        ("save_generated_workout", "generated-workout write"),
        ("save_session_result", "session-result write"),
    ),
)
def test_generic_write_failure_rolls_back_created_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    function_name: str,
    error_text: str,
) -> None:
    proposal_path = persist_proposal(tmp_path)
    directories = generic_output_directories(tmp_path)

    def fail_write(*_args: object, **_kwargs: object) -> Path:
        raise RuntimeError(error_text)

    monkeypatch.setattr(acceptance_script, function_name, fail_write)

    with pytest.raises(RuntimeError, match=error_text):
        acceptance_script.accept_workout_proposal(
            proposal_path_value=proposal_path,
            **directories,
        )

    output_root = tmp_path / "generic-output"
    if output_root.exists():
        assert not tuple(output_root.rglob("*.json"))


def test_generic_post_write_validation_failure_rolls_back_all_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proposal_path = persist_proposal(tmp_path)
    directories = generic_output_directories(tmp_path)

    def fail_validation(**_kwargs: object) -> None:
        raise RuntimeError("Simulated generic post-write validation failure")

    monkeypatch.setattr(
        acceptance_script,
        "validate_persisted_acceptance_set",
        fail_validation,
    )

    with pytest.raises(RuntimeError, match="generic post-write"):
        acceptance_script.accept_workout_proposal(
            proposal_path_value=proposal_path,
            **directories,
        )

    assert not tuple((tmp_path / "generic-output").rglob("*.json"))


def test_generic_acceptance_leaves_no_temporary_files(tmp_path: Path) -> None:
    proposal_path = persist_proposal(tmp_path)

    acceptance_script.accept_workout_proposal(
        proposal_path_value=proposal_path,
        **generic_output_directories(tmp_path),
    )

    assert not tuple(tmp_path.rglob("*.tmp"))


def test_acceptance_workflow_persists_four_linked_records(tmp_path: Path) -> None:
    paths = accept(tmp_path)
    assert all(path.is_file() for path in paths)
    proposal = load_proposal(paths[0])
    acceptance = load_proposal_acceptance(paths[1])
    generated = load_generated_workout(paths[2])
    result = load_session_result(paths[3])
    assert proposal.proposed_generated_workout == generated
    assert acceptance.proposal_id == proposal.proposal_id
    assert acceptance.accepted_generated_workout_id == generated.generated_workout_id
    validate_session_result(generated, result)
    assert result.completion_status == CompletionStatus.NOT_STARTED


@pytest.mark.parametrize("existing_index", range(4))
def test_existing_destination_prevents_all_writes(
    tmp_path: Path,
    existing_index: int,
) -> None:
    parent_path, result_path = write_parent_inputs(tmp_path)
    directories = output_directories(tmp_path)
    expected = (
        directories["proposal_directory"] / "NWP_20260903_001_V1.json",
        directories["acceptance_directory"] / "NWA_20260903_001_V1.json",
        directories["generated_directory"] / "GW_20260903_001_V1.json",
        directories["result_directory"] / "SR_20260903_001_V1.json",
    )
    existing = expected[existing_index]
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError, match="partial or duplicate"):
        acceptance_script.accept_pool_test_two_proposal(
            parent_generated_workout_path=parent_path,
            previous_result_path=result_path,
            **directories,
        )
    assert existing.read_text(encoding="utf-8") == "existing"
    assert [path.exists() for path in expected].count(True) == 1


@pytest.mark.parametrize(
    ("function_name", "expected_created_before_failure"),
    (
        ("save_proposal_acceptance", 1),
        ("save_generated_workout", 2),
        ("save_session_result", 3),
    ),
)
def test_write_failure_rolls_back_created_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    function_name: str,
    expected_created_before_failure: int,
) -> None:
    parent_path, result_path = write_parent_inputs(tmp_path)
    directories = output_directories(tmp_path)

    def fail_write(*_args: object, **_kwargs: object) -> Path:
        raise RuntimeError(
            f"Simulated {function_name} failure after {expected_created_before_failure} writes"
        )

    monkeypatch.setattr(acceptance_script, function_name, fail_write)
    with pytest.raises(RuntimeError, match="Simulated"):
        acceptance_script.accept_pool_test_two_proposal(
            parent_generated_workout_path=parent_path,
            previous_result_path=result_path,
            **directories,
        )
    assert not tuple((tmp_path / "output").rglob("*.json"))


def test_post_write_validation_failure_rolls_back_all_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent_path, result_path = write_parent_inputs(tmp_path)
    directories = output_directories(tmp_path)

    def fail_validation(**_kwargs: object) -> None:
        raise RuntimeError("Simulated post-write validation failure")

    monkeypatch.setattr(acceptance_script, "validate_persisted_acceptance_set", fail_validation)
    with pytest.raises(RuntimeError, match="post-write validation"):
        acceptance_script.accept_pool_test_two_proposal(
            parent_generated_workout_path=parent_path,
            previous_result_path=result_path,
            **directories,
        )
    assert not tuple((tmp_path / "output").rglob("*.json"))


def test_parent_inputs_remain_unchanged(tmp_path: Path) -> None:
    parent_path, result_path = write_parent_inputs(tmp_path)
    parent_before = parent_path.read_bytes()
    result_before = result_path.read_bytes()
    acceptance_script.accept_pool_test_two_proposal(
        parent_generated_workout_path=parent_path,
        previous_result_path=result_path,
        **output_directories(tmp_path),
    )
    assert parent_path.read_bytes() == parent_before
    assert result_path.read_bytes() == result_before


def test_success_leaves_no_temporary_files(tmp_path: Path) -> None:
    accept(tmp_path)
    assert not tuple(tmp_path.rglob("*.tmp"))


def test_missing_parent_is_rejected(tmp_path: Path) -> None:
    _, result_path = write_parent_inputs(tmp_path)
    with pytest.raises(FileNotFoundError, match="Parent generated workout"):
        acceptance_script.accept_pool_test_two_proposal(
            parent_generated_workout_path=tmp_path / "missing-parent.json",
            previous_result_path=result_path,
            **output_directories(tmp_path),
        )


def test_missing_previous_result_is_rejected(tmp_path: Path) -> None:
    parent_path, _ = write_parent_inputs(tmp_path)
    with pytest.raises(FileNotFoundError, match="Previous session result"):
        acceptance_script.accept_pool_test_two_proposal(
            parent_generated_workout_path=parent_path,
            previous_result_path=tmp_path / "missing-result.json",
            **output_directories(tmp_path),
        )
