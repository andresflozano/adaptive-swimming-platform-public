from pathlib import Path

import pytest

from adaptive_swimming.catalog.reference_workouts import (
    build_reference_workout,
)
from adaptive_swimming.domain.session_results import (
    CompletionStatus,
    GeneratedWorkout,
    WorkoutSessionResult,
)
from adaptive_swimming.persistence.proposal_records import (
    load_proposal,
    load_proposal_acceptance,
    proposal_acceptance_path,
    proposal_path,
    save_proposal,
    save_proposal_acceptance,
)
from adaptive_swimming.planning.proposal_acceptance import (
    build_proposal_acceptance,
)
from adaptive_swimming.planning.workout_proposal import (
    NextWorkoutProposal,
    build_pool_test_two_proposal,
)


def build_proposal() -> NextWorkoutProposal:
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
    )
    return build_pool_test_two_proposal(parent, result)


def test_proposal_path_uses_validated_id(tmp_path: Path) -> None:
    assert proposal_path("NWP_20260903_001_V1", tmp_path) == tmp_path / "NWP_20260903_001_V1.json"


def test_acceptance_path_uses_validated_id(tmp_path: Path) -> None:
    assert (
        proposal_acceptance_path("NWA_20260903_001_V1", tmp_path)
        == tmp_path / "NWA_20260903_001_V1.json"
    )


def test_proposal_path_rejects_invalid_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Invalid proposal identifier"):
        proposal_path("../outside", tmp_path)


def test_acceptance_path_rejects_invalid_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Invalid proposal acceptance identifier"):
        proposal_acceptance_path("../outside", tmp_path)


def test_proposal_round_trips(tmp_path: Path) -> None:
    proposal = build_proposal()
    path = save_proposal(proposal, tmp_path)
    assert load_proposal(path) == proposal


def test_acceptance_round_trips(tmp_path: Path) -> None:
    acceptance = build_proposal_acceptance(build_proposal())
    path = save_proposal_acceptance(acceptance, tmp_path)
    assert load_proposal_acceptance(path) == acceptance


def test_proposal_refuses_overwrite(tmp_path: Path) -> None:
    proposal = build_proposal()
    save_proposal(proposal, tmp_path)
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        save_proposal(proposal, tmp_path)


def test_acceptance_refuses_overwrite(tmp_path: Path) -> None:
    acceptance = build_proposal_acceptance(build_proposal())
    save_proposal_acceptance(acceptance, tmp_path)
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        save_proposal_acceptance(acceptance, tmp_path)


def test_successful_writes_leave_no_temporary_files(tmp_path: Path) -> None:
    proposal = build_proposal()
    save_proposal(proposal, tmp_path / "proposals")
    save_proposal_acceptance(build_proposal_acceptance(proposal), tmp_path / "acceptances")
    assert not tuple(tmp_path.rglob("*.tmp"))
