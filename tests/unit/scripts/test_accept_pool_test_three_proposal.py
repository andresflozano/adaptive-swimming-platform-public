from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import scripts.accept_pool_test_three_proposal as workflow
from tests.unit.test_pool_test_three_proposal import build_proposal

from adaptive_swimming.domain.session_results import (
    CompletionStatus,
    GeneratedWorkout,
    WorkoutSessionResult,
)
from adaptive_swimming.persistence.proposal_records import (
    load_proposal,
    load_proposal_acceptance,
    save_proposal,
)
from adaptive_swimming.persistence.session_records import (
    load_generated_workout,
    load_session_result,
)

PROPOSAL_ID = "NWP_20260905_001_V1"
ACCEPTANCE_ID = "NWA_20260905_001_V1"
GENERATED_WORKOUT_ID = "GW_20260905_001_V1"
RESULT_ID = "SR_20260905_001_V1"


def test_direct_file_cli_help_succeeds() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/accept_pool_test_three_proposal.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "--proposal" in completed.stdout
    assert "ModuleNotFoundError" not in completed.stderr


def persist_input_proposal(tmp_path: Path) -> Path:
    return save_proposal(build_proposal(), tmp_path / "proposals")


def accept_from_synthetic_proposal(
    tmp_path: Path,
) -> tuple[Path, Path, Path]:
    proposal_path = persist_input_proposal(tmp_path)
    return workflow.accept_pool_test_three_proposal(
        proposal_path_value=proposal_path,
        acceptance_directory=tmp_path / "acceptances",
        generated_directory=tmp_path / "generated_workouts",
        result_directory=tmp_path / "session_results",
    )


def test_acceptance_creates_expected_three_record_set(tmp_path: Path) -> None:
    acceptance_path, generated_path, result_path = accept_from_synthetic_proposal(tmp_path)
    acceptance = load_proposal_acceptance(acceptance_path)
    generated = load_generated_workout(generated_path)
    result = load_session_result(result_path)

    assert acceptance.acceptance_id == ACCEPTANCE_ID
    assert acceptance.proposal_id == PROPOSAL_ID
    assert acceptance.accepted_generated_workout_id == GENERATED_WORKOUT_ID
    assert acceptance.accepted is True
    assert acceptance.notes is not None
    assert "Pool Test 3" in acceptance.notes
    assert generated.generated_workout_id == GENERATED_WORKOUT_ID
    assert result.session_result_id == RESULT_ID
    assert result.generated_workout_id == GENERATED_WORKOUT_ID
    assert result.completion_status == CompletionStatus.NOT_STARTED


def test_persisted_workout_matches_proposal_snapshot(tmp_path: Path) -> None:
    proposal_path = persist_input_proposal(tmp_path)
    proposal = load_proposal(proposal_path)
    paths = workflow.accept_pool_test_three_proposal(
        proposal_path_value=proposal_path,
        acceptance_directory=tmp_path / "acceptances",
        generated_directory=tmp_path / "generated_workouts",
        result_directory=tmp_path / "session_results",
    )

    assert load_generated_workout(paths[1]) == proposal.proposed_generated_workout


def test_not_started_result_has_no_execution_data(tmp_path: Path) -> None:
    result = load_session_result(accept_from_synthetic_proposal(tmp_path)[2])

    assert result.completed_distance_meters == 0
    assert result.actual_total_seconds is None
    assert result.perceived_exertion is None
    assert result.equipment_used == ()
    assert result.block_results == ()
    assert result.safety_issue_reported is False


@pytest.mark.parametrize("existing_index", (0, 1, 2))
def test_existing_destination_prevents_all_writes(
    tmp_path: Path,
    existing_index: int,
) -> None:
    proposal_path = persist_input_proposal(tmp_path)
    destinations = (
        tmp_path / "acceptances" / f"{ACCEPTANCE_ID}.json",
        tmp_path / "generated_workouts" / f"{GENERATED_WORKOUT_ID}.json",
        tmp_path / "session_results" / f"{RESULT_ID}.json",
    )
    existing = destinations[existing_index]
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError, match="partial or duplicate"):
        workflow.accept_pool_test_three_proposal(
            proposal_path_value=proposal_path,
            acceptance_directory=tmp_path / "acceptances",
            generated_directory=tmp_path / "generated_workouts",
            result_directory=tmp_path / "session_results",
        )

    assert existing.read_text(encoding="utf-8") == "existing"
    assert [path.exists() for path in destinations].count(True) == 1


def test_wrong_proposal_id_is_rejected_before_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text("placeholder", encoding="utf-8")
    invalid = build_proposal().model_copy(update={"proposal_id": "NWP_20260905_002_V1"})
    monkeypatch.setattr(workflow, "load_proposal", lambda _path: invalid)

    with pytest.raises(ValueError, match="Unexpected Pool Test 3 proposal ID"):
        workflow.accept_pool_test_three_proposal(
            proposal_path_value=proposal_path,
            acceptance_directory=tmp_path / "acceptances",
            generated_directory=tmp_path / "generated_workouts",
            result_directory=tmp_path / "session_results",
        )

    assert not (tmp_path / "acceptances").exists()
    assert not (tmp_path / "generated_workouts").exists()
    assert not (tmp_path / "session_results").exists()


def test_second_write_failure_rolls_back_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proposal_path = persist_input_proposal(tmp_path)

    def fail_generated(
        _generated: GeneratedWorkout,
        _directory: Path,
    ) -> Path:
        raise RuntimeError("Simulated generated-workout write failure")

    monkeypatch.setattr(workflow, "save_generated_workout", fail_generated)

    with pytest.raises(RuntimeError, match="generated-workout"):
        workflow.accept_pool_test_three_proposal(
            proposal_path_value=proposal_path,
            acceptance_directory=tmp_path / "acceptances",
            generated_directory=tmp_path / "generated_workouts",
            result_directory=tmp_path / "session_results",
        )

    assert not tuple((tmp_path / "acceptances").glob("*.json"))
    assert not tuple((tmp_path / "generated_workouts").glob("*.json"))
    assert not tuple((tmp_path / "session_results").glob("*.json"))


def test_third_write_failure_rolls_back_first_two(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proposal_path = persist_input_proposal(tmp_path)

    def fail_result(
        _generated: GeneratedWorkout,
        _result: WorkoutSessionResult,
        _directory: Path,
    ) -> Path:
        raise RuntimeError("Simulated result write failure")

    monkeypatch.setattr(workflow, "save_session_result", fail_result)

    with pytest.raises(RuntimeError, match="result write"):
        workflow.accept_pool_test_three_proposal(
            proposal_path_value=proposal_path,
            acceptance_directory=tmp_path / "acceptances",
            generated_directory=tmp_path / "generated_workouts",
            result_directory=tmp_path / "session_results",
        )

    assert not tuple((tmp_path / "acceptances").glob("*.json"))
    assert not tuple((tmp_path / "generated_workouts").glob("*.json"))
    assert not tuple((tmp_path / "session_results").glob("*.json"))


def test_post_write_validation_failure_rolls_back_all_three(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proposal_path = persist_input_proposal(tmp_path)

    def fail_validation(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Simulated post-write validation failure")

    monkeypatch.setattr(
        workflow,
        "validate_persisted_acceptance_set",
        fail_validation,
    )

    with pytest.raises(RuntimeError, match="post-write"):
        workflow.accept_pool_test_three_proposal(
            proposal_path_value=proposal_path,
            acceptance_directory=tmp_path / "acceptances",
            generated_directory=tmp_path / "generated_workouts",
            result_directory=tmp_path / "session_results",
        )

    assert not tuple((tmp_path / "acceptances").glob("*.json"))
    assert not tuple((tmp_path / "generated_workouts").glob("*.json"))
    assert not tuple((tmp_path / "session_results").glob("*.json"))


def test_proposal_file_remains_byte_for_byte_unchanged(tmp_path: Path) -> None:
    proposal_path = persist_input_proposal(tmp_path)
    before = proposal_path.read_bytes()

    workflow.accept_pool_test_three_proposal(
        proposal_path_value=proposal_path,
        acceptance_directory=tmp_path / "acceptances",
        generated_directory=tmp_path / "generated_workouts",
        result_directory=tmp_path / "session_results",
    )

    assert proposal_path.read_bytes() == before


def test_missing_proposal_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Proposal file does not exist"):
        workflow.accept_pool_test_three_proposal(
            proposal_path_value=tmp_path / "missing.json",
            acceptance_directory=tmp_path / "acceptances",
            generated_directory=tmp_path / "generated_workouts",
            result_directory=tmp_path / "session_results",
        )


def test_success_leaves_no_temporary_files(tmp_path: Path) -> None:
    accept_from_synthetic_proposal(tmp_path)
    assert not tuple(tmp_path.rglob("*.tmp"))
