from __future__ import annotations

from pathlib import Path

import pytest
import scripts.create_pool_test_three_proposal as workflow
from tests.unit.test_pool_test_three_proposal import (
    build_decisions,
    build_parent,
    build_previous_result,
)

from adaptive_swimming.persistence.proposal_records import load_proposal
from adaptive_swimming.planning.workout_proposal import ProposalStatus

PROPOSAL_ID = "NWP_20260905_001_V1"
GENERATED_WORKOUT_ID = "GW_20260905_001_V1"


def configure_synthetic_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = build_parent()
    previous_result = build_previous_result()
    accepted, deferred = build_decisions()

    monkeypatch.setattr(
        workflow,
        "load_generated_workout",
        lambda _path: parent,
    )
    monkeypatch.setattr(
        workflow,
        "load_session_result",
        lambda _path: previous_result,
    )

    decisions = {
        "accepted.json": accepted,
        "deferred.json": deferred,
    }
    monkeypatch.setattr(
        workflow,
        "load_target_review_decision",
        lambda path: decisions[path.name],
    )


def run_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    configure_synthetic_inputs(monkeypatch)
    return workflow.create_pool_test_three_proposal(
        parent_generated_workout_path=tmp_path / "parent.json",
        previous_result_path=tmp_path / "result.json",
        accepted_fins_decision_path=tmp_path / "accepted.json",
        deferred_paddles_decision_path=tmp_path / "deferred.json",
        proposal_id=PROPOSAL_ID,
        generated_workout_id=GENERATED_WORKOUT_ID,
        proposal_directory=tmp_path / "proposals",
    )


def test_workflow_persists_proposed_pool_test_three(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = run_workflow(tmp_path, monkeypatch)
    proposal = load_proposal(path)

    assert path == tmp_path / "proposals" / f"{PROPOSAL_ID}.json"
    assert proposal.proposal_id == PROPOSAL_ID
    assert proposal.status == ProposalStatus.PROPOSED
    assert proposal.parent_generated_workout_id == "GW_20260903_001_V1"
    assert proposal.previous_session_result_id == "SR_20260903_001_V2"
    assert proposal.proposed_generated_workout.generated_workout_id == GENERATED_WORKOUT_ID


def test_persisted_proposal_has_only_expected_fins_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proposal = load_proposal(run_workflow(tmp_path, monkeypatch))
    workout = proposal.proposed_generated_workout.workout
    targeted = tuple(
        (block.sequence, group.sequence, item)
        for block in workout.blocks
        for group in block.set_groups
        for item in group.items
        if item.target is not None
    )

    assert len(targeted) == 1
    assert targeted[0][0:2] == (4, 1)
    assert targeted[0][2].target is not None
    assert targeted[0][2].target.target_seconds == 65
    assert workout.blocks[1].set_groups[0].items[0].target is None
    assert workout.blocks[2].set_groups[0].items[0].target is None


def test_persisted_proposal_preserves_structure_and_unresolved_feasibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proposal = load_proposal(run_workflow(tmp_path, monkeypatch))
    workout = proposal.proposed_generated_workout.workout

    assert len(workout.blocks) == 6
    assert workout.total_distance_meters() == 1500
    assert proposal.time_feasibility.status.value == "UNRESOLVED"


def test_existing_proposal_refuses_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_synthetic_inputs(monkeypatch)
    proposal_directory = tmp_path / "proposals"
    proposal_directory.mkdir()
    destination = proposal_directory / f"{PROPOSAL_ID}.json"
    destination.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        workflow.create_pool_test_three_proposal(
            parent_generated_workout_path=tmp_path / "parent.json",
            previous_result_path=tmp_path / "result.json",
            accepted_fins_decision_path=tmp_path / "accepted.json",
            deferred_paddles_decision_path=tmp_path / "deferred.json",
            proposal_id=PROPOSAL_ID,
            generated_workout_id=GENERATED_WORKOUT_ID,
            proposal_directory=proposal_directory,
        )

    assert destination.read_text(encoding="utf-8") == "existing"


def test_invalid_accepted_decision_prevents_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = build_parent()
    result = build_previous_result()
    accepted, deferred = build_decisions()
    invalid = accepted.model_copy(update={"decision": "DEFERRED"})

    monkeypatch.setattr(workflow, "load_generated_workout", lambda _path: parent)
    monkeypatch.setattr(workflow, "load_session_result", lambda _path: result)
    monkeypatch.setattr(
        workflow,
        "load_target_review_decision",
        lambda path: invalid if path.name == "accepted.json" else deferred,
    )

    output = tmp_path / "proposals"
    with pytest.raises(ValueError, match="must be accepted"):
        workflow.create_pool_test_three_proposal(
            parent_generated_workout_path=tmp_path / "parent.json",
            previous_result_path=tmp_path / "result.json",
            accepted_fins_decision_path=tmp_path / "accepted.json",
            deferred_paddles_decision_path=tmp_path / "deferred.json",
            proposal_id=PROPOSAL_ID,
            generated_workout_id=GENERATED_WORKOUT_ID,
            proposal_directory=output,
        )

    assert not tuple(output.glob("*.json"))


def test_post_write_validation_failure_rolls_back_proposal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_synthetic_inputs(monkeypatch)
    output = tmp_path / "proposals"

    def fail_validation(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Simulated post-write validation failure")

    monkeypatch.setattr(workflow, "validate_persisted_proposal", fail_validation)

    with pytest.raises(RuntimeError, match="post-write"):
        workflow.create_pool_test_three_proposal(
            parent_generated_workout_path=tmp_path / "parent.json",
            previous_result_path=tmp_path / "result.json",
            accepted_fins_decision_path=tmp_path / "accepted.json",
            deferred_paddles_decision_path=tmp_path / "deferred.json",
            proposal_id=PROPOSAL_ID,
            generated_workout_id=GENERATED_WORKOUT_ID,
            proposal_directory=output,
        )

    assert not tuple(output.glob("*.json"))


def test_workflow_creates_no_acceptance_or_execution_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_workflow(tmp_path, monkeypatch)

    assert not (tmp_path / "generated_workouts").exists()
    assert not (tmp_path / "session_results").exists()
    assert not (tmp_path / "proposal_acceptances").exists()


def test_success_leaves_no_temporary_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_workflow(tmp_path, monkeypatch)
    assert not tuple(tmp_path.rglob("*.tmp"))
