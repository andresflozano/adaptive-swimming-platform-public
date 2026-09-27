import pytest
from pydantic import ValidationError

from adaptive_swimming.catalog.reference_workouts import build_reference_workout
from adaptive_swimming.domain.session_results import (
    CompletionStatus,
    GeneratedWorkout,
    WorkoutSessionResult,
)
from adaptive_swimming.domain.workout import EquipmentCode
from adaptive_swimming.planning.proposal_acceptance import (
    ProposalAcceptance,
    build_not_started_result,
    build_proposal_acceptance,
)
from adaptive_swimming.planning.workout_proposal import (
    NextWorkoutProposal,
    ProposalStatus,
    build_pool_test_two_proposal,
)


def build_parent() -> GeneratedWorkout:
    return GeneratedWorkout(
        generated_workout_id="GW_20260901_001_V1",
        workout_version=1,
        workout=build_reference_workout(),
        pool_length_meters=12.5,
        equipment_available=(
            EquipmentCode.FINS,
            EquipmentCode.PADDLES,
            EquipmentCode.KICKBOARD,
        ),
        generation_reason="BASELINE_SESSION",
    )


def build_previous_result() -> WorkoutSessionResult:
    return WorkoutSessionResult(
        session_result_id="SR_20260901_001_V2",
        generated_workout_id="GW_20260901_001_V1",
        result_version=2,
        completion_status=CompletionStatus.STOPPED_EARLY,
        completed_distance_meters=1100,
        actual_total_seconds=2700,
        perceived_exertion=5,
        equipment_used=(EquipmentCode.PADDLES, EquipmentCode.FINS),
        safety_issue_reported=False,
    )


def build_proposal() -> NextWorkoutProposal:
    return build_pool_test_two_proposal(build_parent(), build_previous_result())


def test_acceptance_references_proposal() -> None:
    proposal = build_proposal()
    acceptance = build_proposal_acceptance(proposal)
    assert acceptance.proposal_id == proposal.proposal_id


def test_acceptance_references_proposed_workout() -> None:
    proposal = build_proposal()
    acceptance = build_proposal_acceptance(proposal)
    assert (
        acceptance.accepted_generated_workout_id
        == proposal.proposed_generated_workout.generated_workout_id
    )


def test_acceptance_id_and_version_are_derived() -> None:
    acceptance = build_proposal_acceptance(build_proposal())
    assert acceptance.acceptance_id == "NWA_20260903_001_V1"
    assert acceptance.acceptance_version == 1


def test_acceptance_rejects_mismatched_version() -> None:
    with pytest.raises(ValidationError, match="ID version must match"):
        ProposalAcceptance(
            acceptance_id="NWA_20260903_001_V2",
            acceptance_version=1,
            proposal_id="NWP_20260903_001_V1",
            accepted_generated_workout_id="GW_20260903_001_V1",
        )


def test_acceptance_rejects_false_accepted_flag() -> None:
    with pytest.raises(ValidationError, match="must be accepted"):
        ProposalAcceptance(
            acceptance_id="NWA_20260903_001_V1",
            acceptance_version=1,
            proposal_id="NWP_20260903_001_V1",
            accepted_generated_workout_id="GW_20260903_001_V1",
            accepted=False,
        )


def test_blank_result_uses_proposed_workout_id() -> None:
    proposal = build_proposal()
    result = build_not_started_result(proposal)
    assert result.session_result_id == "SR_20260903_001_V1"
    assert result.generated_workout_id == proposal.proposed_generated_workout.generated_workout_id


def test_blank_result_is_not_started_and_empty() -> None:
    result = build_not_started_result(build_proposal())
    assert result.completion_status == CompletionStatus.NOT_STARTED
    assert result.completed_distance_meters == 0
    assert result.actual_total_seconds is None


def test_building_acceptance_does_not_mutate_proposal() -> None:
    proposal = build_proposal()
    before = proposal.model_dump_json()
    build_proposal_acceptance(proposal)
    build_not_started_result(proposal)
    assert proposal.model_dump_json() == before
    assert proposal.status == ProposalStatus.PROPOSED


def test_acceptance_round_trips_through_json() -> None:
    acceptance = build_proposal_acceptance(build_proposal())
    loaded = ProposalAcceptance.model_validate_json(acceptance.model_dump_json())
    assert loaded == acceptance
