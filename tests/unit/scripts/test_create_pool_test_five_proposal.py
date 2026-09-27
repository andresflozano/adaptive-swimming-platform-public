from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import scripts.create_pool_test_five_proposal as workflow
from tests.unit.scripts.test_review_recalibrated_targets import (
    review_set_for_persistence,
)
from tests.unit.test_configurable_workout_proposal import build_parent
from tests.unit.test_pool_test_five_proposal import build_completed_result

from adaptive_swimming.persistence.proposal_records import load_proposal
from adaptive_swimming.persistence.recalibrated_target_review_records import (
    save_recalibrated_review_set,
)
from adaptive_swimming.persistence.session_records import (
    save_generated_workout,
    save_session_result,
)

PROPOSAL_ID = "NWP_20260913_001_V1"
GENERATED_ID = "GW_20260913_001_V1"
DECISION_ID = "RTRD_20260906_001_V1"


def write_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    parent = build_parent()
    result = build_completed_result(parent)
    review_set = review_set_for_persistence()

    parent_path = save_generated_workout(parent, tmp_path / "generated")
    result_path = save_session_result(parent, result, tmp_path / "results")
    review_path = save_recalibrated_review_set(review_set, tmp_path / "reviews")
    return parent_path, result_path, review_path


def create(tmp_path: Path) -> tuple[Path, tuple[Path, Path, Path]]:
    inputs = write_inputs(tmp_path / "inputs")
    path = workflow.create_pool_test_five_proposal(
        parent_generated_workout_path=inputs[0],
        previous_result_path=inputs[1],
        review_set_path=inputs[2],
        review_decision_id=DECISION_ID,
        proposal_id=PROPOSAL_ID,
        generated_workout_id=GENERATED_ID,
        proposal_directory=tmp_path / "output" / "proposals",
    )
    return path, inputs


def test_direct_file_help_succeeds() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/create_pool_test_five_proposal.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "--review-decision-id" in completed.stdout


def test_module_help_succeeds() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.create_pool_test_five_proposal", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "--generated-workout-id" in completed.stdout


def test_persists_only_pool_test_five_proposal(tmp_path: Path) -> None:
    path, _ = create(tmp_path)
    proposal = load_proposal(path)

    assert path.name == f"{PROPOSAL_ID}.json"
    assert proposal.proposal_id == PROPOSAL_ID
    assert proposal.parent_generated_workout_id == "GW_20260905_001_V1"
    assert proposal.previous_session_result_id == "SR_20260905_001_V2"
    assert proposal.proposed_generated_workout.generated_workout_id == GENERATED_ID
    assert tuple((tmp_path / "output").rglob("*.json")) == (path,)


def test_persisted_structure_and_target_are_exact(tmp_path: Path) -> None:
    path, _ = create(tmp_path)
    proposal = load_proposal(path)
    generated = proposal.proposed_generated_workout
    targeted = tuple(
        item
        for block in generated.workout.blocks
        for group in block.set_groups
        for item in group.items
        if item.target is not None
    )

    assert tuple(block.total_distance_meters() for block in generated.workout.blocks) == (
        300,
        200,
        400,
        200,
        100,
        300,
    )
    assert generated.planned_distance_meters == 1500
    assert generated.configured_rest_seconds == 360
    assert proposal.time_feasibility.status.value == "UNRESOLVED"
    assert len(targeted) == 1
    assert targeted[0].target is not None
    assert targeted[0].target.target_seconds == 65


def test_preserves_all_input_bytes(tmp_path: Path) -> None:
    inputs = write_inputs(tmp_path / "inputs")
    before = {path: path.read_bytes() for path in inputs}

    workflow.create_pool_test_five_proposal(
        parent_generated_workout_path=inputs[0],
        previous_result_path=inputs[1],
        review_set_path=inputs[2],
        review_decision_id=DECISION_ID,
        proposal_id=PROPOSAL_ID,
        generated_workout_id=GENERATED_ID,
        proposal_directory=tmp_path / "output" / "proposals",
    )

    assert {path: path.read_bytes() for path in inputs} == before


def test_existing_destination_refuses_overwrite(tmp_path: Path) -> None:
    path, inputs = create(tmp_path)
    before = path.read_bytes()

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        workflow.create_pool_test_five_proposal(
            parent_generated_workout_path=inputs[0],
            previous_result_path=inputs[1],
            review_set_path=inputs[2],
            review_decision_id=DECISION_ID,
            proposal_id=PROPOSAL_ID,
            generated_workout_id=GENERATED_ID,
            proposal_directory=tmp_path / "output" / "proposals",
        )

    assert path.read_bytes() == before


def test_missing_input_prevents_output(tmp_path: Path) -> None:
    _, result_path, review_path = write_inputs(tmp_path / "inputs")

    with pytest.raises(FileNotFoundError, match="Parent generated workout"):
        workflow.create_pool_test_five_proposal(
            parent_generated_workout_path=tmp_path / "missing.json",
            previous_result_path=result_path,
            review_set_path=review_path,
            review_decision_id=DECISION_ID,
            proposal_id=PROPOSAL_ID,
            generated_workout_id=GENERATED_ID,
            proposal_directory=tmp_path / "output" / "proposals",
        )

    assert not (tmp_path / "output").exists()


def test_invalid_review_decision_prevents_write(tmp_path: Path) -> None:
    inputs = write_inputs(tmp_path / "inputs")
    output = tmp_path / "output" / "proposals"

    with pytest.raises(ValueError, match="exactly one"):
        workflow.create_pool_test_five_proposal(
            parent_generated_workout_path=inputs[0],
            previous_result_path=inputs[1],
            review_set_path=inputs[2],
            review_decision_id="RTRD_20260913_999_V1",
            proposal_id=PROPOSAL_ID,
            generated_workout_id=GENERATED_ID,
            proposal_directory=output,
        )

    assert not tuple(output.glob("*.json"))


def test_post_write_validation_failure_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = write_inputs(tmp_path / "inputs")
    output = tmp_path / "output" / "proposals"

    def fail_validation(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Simulated post-write validation failure")

    monkeypatch.setattr(
        workflow,
        "validate_persisted_pool_test_five_proposal",
        fail_validation,
    )

    with pytest.raises(RuntimeError, match="post-write"):
        workflow.create_pool_test_five_proposal(
            parent_generated_workout_path=inputs[0],
            previous_result_path=inputs[1],
            review_set_path=inputs[2],
            review_decision_id=DECISION_ID,
            proposal_id=PROPOSAL_ID,
            generated_workout_id=GENERATED_ID,
            proposal_directory=output,
        )

    assert not tuple(output.glob("*.json"))


def test_creates_no_acceptance_or_execution_records(tmp_path: Path) -> None:
    create(tmp_path)

    assert not (tmp_path / "output" / "proposal_acceptances").exists()
    assert not (tmp_path / "output" / "generated_workouts").exists()
    assert not (tmp_path / "output" / "session_results").exists()


def test_success_leaves_no_temporary_files(tmp_path: Path) -> None:
    create(tmp_path)
    assert not tuple(tmp_path.rglob("*.tmp"))
