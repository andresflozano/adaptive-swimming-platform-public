from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import scripts.create_workout_proposal as workflow
from tests.unit.scripts.test_preview_workout_proposal import write_inputs

from adaptive_swimming.persistence.proposal_records import load_proposal
from adaptive_swimming.planning.configurable_workout_proposal import (
    TargetApplicationSelection,
)


def selection() -> TargetApplicationSelection:
    return TargetApplicationSelection(
        block_sequence=4,
        set_group_sequence=1,
        item_sequence=1,
    )


def create(tmp_path: Path) -> tuple[Path, tuple[Path, Path, Path]]:
    inputs = write_inputs(tmp_path / "inputs")
    created = workflow.create_workout_proposal(
        parent_generated_workout_path=inputs[0],
        previous_result_path=inputs[1],
        review_set_path=inputs[2],
        review_decision_id="RTRD_20260906_001_V1",
        selection=selection(),
        proposal_id="NWP_20261001_007_V1",
        proposal_version=1,
        generated_workout_id="GW_20261001_007_V1",
        generated_workout_version=1,
        workout_session_id="WT_ENGINE_CONFIGURABLE_007_V1",
        generation_reason="CONFIGURABLE_REVIEWED_TARGET_PROPOSAL",
        proposal_directory=tmp_path / "output" / "proposals",
    )
    return created, inputs


def test_direct_file_help_succeeds() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/create_workout_proposal.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "--review-set" in completed.stdout
    assert "--proposal-id" in completed.stdout
    assert "ModuleNotFoundError" not in completed.stderr


def test_module_help_succeeds() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.create_workout_proposal", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "--generated-workout-id" in completed.stdout


def test_create_persists_only_reviewed_proposal(tmp_path: Path) -> None:
    path, _ = create(tmp_path)
    proposal = load_proposal(path)
    item = proposal.proposed_generated_workout.workout.blocks[3].set_groups[0].items[0]

    serialized = proposal.model_dump_json()

    assert "Previewed decision" not in serialized
    assert "Preview only" not in serialized
    assert "Applied reviewed decision RTRD_20260906_001_V1" in serialized
    assert "Proposal persistence does not imply acceptance or execution." in proposal.limitations
    assert (
        "The reviewed target remains provisional until evaluated "
        "in a completed session." in proposal.limitations
    )
    assert "Time feasibility status at proposal creation: UNRESOLVED." in proposal.limitations

    assert path.name == "NWP_20261001_007_V1.json"
    assert proposal.proposal_id == "NWP_20261001_007_V1"
    assert proposal.proposed_generated_workout.generated_workout_id == ("GW_20261001_007_V1")
    assert item.target is not None
    assert item.target.target_seconds == 65
    assert tuple((tmp_path / "output").rglob("*.json")) == (path,)


def test_create_preserves_all_input_bytes(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    inputs = write_inputs(input_root)
    before = {path: path.read_bytes() for path in inputs}

    workflow.create_workout_proposal(
        parent_generated_workout_path=inputs[0],
        previous_result_path=inputs[1],
        review_set_path=inputs[2],
        review_decision_id="RTRD_20260906_001_V1",
        selection=selection(),
        proposal_id="NWP_20261001_007_V1",
        proposal_version=1,
        generated_workout_id="GW_20261001_007_V1",
        generated_workout_version=1,
        workout_session_id="WT_ENGINE_CONFIGURABLE_007_V1",
        generation_reason="CONFIGURABLE_REVIEWED_TARGET_PROPOSAL",
        proposal_directory=tmp_path / "output" / "proposals",
    )

    assert {path: path.read_bytes() for path in inputs} == before


def test_existing_destination_prevents_overwrite(tmp_path: Path) -> None:
    path, inputs = create(tmp_path)
    before = path.read_bytes()

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        workflow.create_workout_proposal(
            parent_generated_workout_path=inputs[0],
            previous_result_path=inputs[1],
            review_set_path=inputs[2],
            review_decision_id="RTRD_20260906_001_V1",
            selection=selection(),
            proposal_id="NWP_20261001_007_V1",
            proposal_version=1,
            generated_workout_id="GW_20261001_007_V1",
            generated_workout_version=1,
            workout_session_id="WT_ENGINE_CONFIGURABLE_007_V1",
            generation_reason="CONFIGURABLE_REVIEWED_TARGET_PROPOSAL",
            proposal_directory=tmp_path / "output" / "proposals",
        )

    assert path.read_bytes() == before


def test_post_write_validation_failure_rolls_back_proposal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = write_inputs(tmp_path / "inputs")

    def fail_validation(_path: Path, _source: object) -> None:
        raise RuntimeError("Simulated persisted-proposal validation failure")

    monkeypatch.setattr(workflow, "validate_persisted_proposal", fail_validation)

    with pytest.raises(RuntimeError, match="persisted-proposal"):
        workflow.create_workout_proposal(
            parent_generated_workout_path=inputs[0],
            previous_result_path=inputs[1],
            review_set_path=inputs[2],
            review_decision_id="RTRD_20260906_001_V1",
            selection=selection(),
            proposal_id="NWP_20261001_007_V1",
            proposal_version=1,
            generated_workout_id="GW_20261001_007_V1",
            generated_workout_version=1,
            workout_session_id="WT_ENGINE_CONFIGURABLE_007_V1",
            generation_reason="CONFIGURABLE_REVIEWED_TARGET_PROPOSAL",
            proposal_directory=tmp_path / "output" / "proposals",
        )

    assert not tuple((tmp_path / "output").rglob("*.json"))


def test_missing_input_does_not_create_output(tmp_path: Path) -> None:
    _, result_path, review_path = write_inputs(tmp_path / "inputs")

    with pytest.raises(FileNotFoundError, match="Parent generated workout"):
        workflow.create_workout_proposal(
            parent_generated_workout_path=tmp_path / "missing.json",
            previous_result_path=result_path,
            review_set_path=review_path,
            review_decision_id="RTRD_20260906_001_V1",
            selection=selection(),
            proposal_id="NWP_20261001_007_V1",
            proposal_version=1,
            generated_workout_id="GW_20261001_007_V1",
            generated_workout_version=1,
            workout_session_id="WT_ENGINE_CONFIGURABLE_007_V1",
            generation_reason="CONFIGURABLE_REVIEWED_TARGET_PROPOSAL",
            proposal_directory=tmp_path / "output" / "proposals",
        )

    assert not (tmp_path / "output").exists()


def test_success_leaves_no_temporary_files(tmp_path: Path) -> None:
    create(tmp_path)
    assert not tuple(tmp_path.rglob("*.tmp"))
