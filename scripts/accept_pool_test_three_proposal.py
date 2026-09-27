from __future__ import annotations

import argparse
from pathlib import Path

from adaptive_swimming.domain.session_results import WorkoutSessionResult
from adaptive_swimming.persistence.proposal_records import (
    load_proposal,
    load_proposal_acceptance,
    proposal_acceptance_path,
)
from adaptive_swimming.persistence.proposal_records import (
    save_proposal_acceptance as save_proposal_acceptance,
)
from adaptive_swimming.persistence.session_records import (
    GENERATED_WORKOUTS_DIRECTORY,
    PROPOSAL_ACCEPTANCES_DIRECTORY,
    SESSION_RESULTS_DIRECTORY,
    generated_workout_path,
    load_generated_workout,
    load_session_result,
    session_result_path,
)
from adaptive_swimming.persistence.session_records import (
    save_generated_workout as save_generated_workout,
)
from adaptive_swimming.persistence.session_records import (
    save_session_result as save_session_result,
)
from adaptive_swimming.planning.pool_test_three_validation import (
    validate_pool_test_three_proposal,
)
from adaptive_swimming.planning.proposal_acceptance import (
    ProposalAcceptance,
    build_not_started_result,
    build_proposal_acceptance,
)
from adaptive_swimming.planning.workout_proposal import NextWorkoutProposal

EXPECTED_PROPOSAL_ID = "NWP_20260905_001_V1"
EXPECTED_GENERATED_WORKOUT_ID = "GW_20260905_001_V1"
EXPECTED_PARENT_ID = "GW_20260903_001_V1"
EXPECTED_PREVIOUS_RESULT_ID = "SR_20260903_001_V2"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Accept the persisted Pool Test 3 proposal and atomically create "
            "its acceptance, generated workout, and NOT_STARTED result."
        )
    )
    parser.add_argument("--proposal", type=Path, required=True)
    return parser.parse_args()


def preflight_destinations(destinations: tuple[Path, ...]) -> None:
    existing = tuple(path for path in destinations if path.exists())
    if existing:
        raise FileExistsError(
            f"Refusing to create a partial or duplicate Pool Test 3 acceptance set: {existing}"
        )


def rollback_created_paths(created_paths: list[Path]) -> None:
    for path in reversed(created_paths):
        if path.exists():
            path.unlink()


def validate_acceptance_set(
    *,
    proposal: NextWorkoutProposal,
    acceptance: ProposalAcceptance,
    blank_result: WorkoutSessionResult,
) -> None:
    validate_pool_test_three_proposal(
        proposal,
        expected_parent_id=EXPECTED_PARENT_ID,
        expected_previous_result_id=EXPECTED_PREVIOUS_RESULT_ID,
        expected_generated_workout_id=EXPECTED_GENERATED_WORKOUT_ID,
    )
    if proposal.proposal_id != EXPECTED_PROPOSAL_ID:
        raise ValueError("Unexpected Pool Test 3 proposal ID.")
    generated = proposal.proposed_generated_workout
    if acceptance.proposal_id != proposal.proposal_id:
        raise ValueError("Acceptance must reference the proposal.")
    if acceptance.accepted_generated_workout_id != generated.generated_workout_id:
        raise ValueError("Acceptance must reference the proposed workout.")
    if blank_result.generated_workout_id != generated.generated_workout_id:
        raise ValueError("Blank result must reference the proposed workout.")
    if blank_result.completion_status.value != "NOT_STARTED":
        raise ValueError("Initial Pool Test 3 result must be NOT_STARTED.")
    if blank_result.session_result_id != "SR_20260905_001_V1":
        raise ValueError("Unexpected Pool Test 3 session-result ID.")


def validate_persisted_acceptance_set(
    *,
    proposal: NextWorkoutProposal,
    acceptance_path: Path,
    generated_path: Path,
    result_path: Path,
) -> None:
    acceptance = load_proposal_acceptance(acceptance_path)
    generated = load_generated_workout(generated_path)
    result = load_session_result(result_path)
    validate_acceptance_set(
        proposal=proposal,
        acceptance=acceptance,
        blank_result=result,
    )
    if generated != proposal.proposed_generated_workout:
        raise ValueError("Persisted generated workout does not match the proposal snapshot.")


def accept_pool_test_three_proposal(
    *,
    proposal_path_value: Path,
    acceptance_directory: Path = PROPOSAL_ACCEPTANCES_DIRECTORY,
    generated_directory: Path = GENERATED_WORKOUTS_DIRECTORY,
    result_directory: Path = SESSION_RESULTS_DIRECTORY,
) -> tuple[Path, Path, Path]:
    if not proposal_path_value.is_file():
        raise FileNotFoundError(f"Proposal file does not exist: {proposal_path_value}")

    proposal = load_proposal(proposal_path_value)
    acceptance = build_proposal_acceptance(
        proposal,
        notes=(
            "Accepted after swimmer review of the Pool Test 3 presentation "
            "with one 1:05 fins target."
        ),
    )
    generated = proposal.proposed_generated_workout
    blank_result = build_not_started_result(proposal)
    validate_acceptance_set(
        proposal=proposal,
        acceptance=acceptance,
        blank_result=blank_result,
    )

    destinations = (
        proposal_acceptance_path(acceptance.acceptance_id, acceptance_directory),
        generated_workout_path(generated.generated_workout_id, generated_directory),
        session_result_path(blank_result.session_result_id, result_directory),
    )
    preflight_destinations(destinations)

    created_paths: list[Path] = []
    try:
        created_paths.append(save_proposal_acceptance(acceptance, acceptance_directory))
        created_paths.append(save_generated_workout(generated, generated_directory))
        created_paths.append(save_session_result(generated, blank_result, result_directory))
        validate_persisted_acceptance_set(
            proposal=proposal,
            acceptance_path=created_paths[0],
            generated_path=created_paths[1],
            result_path=created_paths[2],
        )
    except Exception:
        rollback_created_paths(created_paths)
        raise

    return created_paths[0], created_paths[1], created_paths[2]


def main() -> None:
    arguments = parse_arguments()
    paths = accept_pool_test_three_proposal(
        proposal_path_value=arguments.proposal,
    )
    acceptance = load_proposal_acceptance(paths[0])
    generated = load_generated_workout(paths[1])
    result = load_session_result(paths[2])
    print(f"Acceptance: {paths[0]}")
    print(f"Generated workout: {paths[1]}")
    print(f"Blank session result: {paths[2]}")
    print(f"Acceptance ID: {acceptance.acceptance_id}")
    print(f"Generated workout ID: {generated.generated_workout_id}")
    print(f"Result ID: {result.session_result_id}")
    print(f"Completion status: {result.completion_status.value}")


if __name__ == "__main__":
    main()
