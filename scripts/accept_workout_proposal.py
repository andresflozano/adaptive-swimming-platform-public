from __future__ import annotations

import argparse
from pathlib import Path

from adaptive_swimming.domain.session_results import (
    WorkoutSessionResult,
    validate_session_result,
)
from adaptive_swimming.persistence.proposal_records import (
    load_proposal,
    load_proposal_acceptance,
    proposal_acceptance_path,
    proposal_path,
    save_proposal,
    save_proposal_acceptance,
)
from adaptive_swimming.persistence.session_records import (
    GENERATED_WORKOUTS_DIRECTORY,
    PROPOSAL_ACCEPTANCES_DIRECTORY,
    PROPOSALS_DIRECTORY,
    SESSION_RESULTS_DIRECTORY,
    generated_workout_path,
    load_generated_workout,
    load_session_result,
    save_generated_workout,
    save_session_result,
    session_result_path,
)
from adaptive_swimming.planning.proposal_acceptance import (
    ProposalAcceptance,
    build_not_started_result,
    build_proposal_acceptance,
)
from adaptive_swimming.planning.workout_proposal import (
    NextWorkoutProposal,
    build_pool_test_two_proposal,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Accept an existing workout proposal and atomically persist its "
            "acceptance, generated workout, and initial NOT_STARTED result."
        )
    )
    parser.add_argument(
        "--proposal",
        type=Path,
        required=True,
        help="Path to an existing NextWorkoutProposal JSON record.",
    )
    return parser.parse_args()


def ensure_input_file(
    path: Path,
    record_name: str,
) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{record_name} file does not exist: {path}")


def preflight_destinations(
    destinations: tuple[Path, ...],
) -> None:
    existing_paths = tuple(path for path in destinations if path.exists())

    if existing_paths:
        raise FileExistsError(
            "Refusing to create a partial or duplicate "
            f"proposal acceptance record set: {existing_paths}"
        )


def rollback_created_paths(
    created_paths: list[Path],
) -> None:
    for path in reversed(created_paths):
        if path.exists():
            path.unlink()


def validate_acceptance_set(
    *,
    proposal: NextWorkoutProposal,
    acceptance: ProposalAcceptance,
    blank_result: WorkoutSessionResult,
) -> None:
    expected_acceptance = build_proposal_acceptance(proposal)

    if acceptance != expected_acceptance:
        raise ValueError("Proposal acceptance must match the proposal-derived acceptance record.")

    if acceptance.proposal_id != proposal.proposal_id:
        raise ValueError("Acceptance must reference the proposal.")

    generated_workout = proposal.proposed_generated_workout

    if acceptance.accepted_generated_workout_id != generated_workout.generated_workout_id:
        raise ValueError("Acceptance must reference the proposed generated workout.")

    if blank_result.generated_workout_id != generated_workout.generated_workout_id:
        raise ValueError("Blank result must reference the proposed generated workout.")

    validate_session_result(
        generated_workout,
        blank_result,
    )

    expected_blank_result = build_not_started_result(proposal)

    if blank_result != expected_blank_result:
        raise ValueError(
            "Initial session result must match the proposal-derived NOT_STARTED result."
        )


def validate_persisted_acceptance_set(
    *,
    proposal_path_value: Path,
    acceptance_path_value: Path,
    generated_path_value: Path,
    result_path_value: Path,
) -> None:
    proposal = load_proposal(proposal_path_value)
    acceptance = load_proposal_acceptance(acceptance_path_value)
    generated_workout = load_generated_workout(generated_path_value)
    blank_result = load_session_result(result_path_value)

    validate_acceptance_set(
        proposal=proposal,
        acceptance=acceptance,
        blank_result=blank_result,
    )

    if proposal.proposed_generated_workout != generated_workout:
        raise ValueError(
            "Persisted generated workout does not match the accepted proposal snapshot."
        )

    validate_session_result(
        generated_workout,
        blank_result,
    )


def accept_workout_proposal(
    *,
    proposal_path_value: Path,
    acceptance_directory: Path = PROPOSAL_ACCEPTANCES_DIRECTORY,
    generated_directory: Path = GENERATED_WORKOUTS_DIRECTORY,
    result_directory: Path = SESSION_RESULTS_DIRECTORY,
) -> tuple[Path, Path, Path]:
    ensure_input_file(
        proposal_path_value,
        "Proposal",
    )

    proposal_before = proposal_path_value.read_bytes()
    proposal = load_proposal(proposal_path_value)
    acceptance = build_proposal_acceptance(proposal)
    generated_workout = proposal.proposed_generated_workout
    blank_result = build_not_started_result(proposal)

    validate_acceptance_set(
        proposal=proposal,
        acceptance=acceptance,
        blank_result=blank_result,
    )

    destinations = (
        proposal_acceptance_path(
            acceptance.acceptance_id,
            acceptance_directory,
        ),
        generated_workout_path(
            generated_workout.generated_workout_id,
            generated_directory,
        ),
        session_result_path(
            blank_result.session_result_id,
            result_directory,
        ),
    )
    preflight_destinations(destinations)

    created_paths: list[Path] = []

    try:
        created_paths.append(
            save_proposal_acceptance(
                acceptance,
                acceptance_directory,
            )
        )
        created_paths.append(
            save_generated_workout(
                generated_workout,
                generated_directory,
            )
        )
        created_paths.append(
            save_session_result(
                generated_workout,
                blank_result,
                result_directory,
            )
        )

        validate_persisted_acceptance_set(
            proposal_path_value=proposal_path_value,
            acceptance_path_value=created_paths[0],
            generated_path_value=created_paths[1],
            result_path_value=created_paths[2],
        )

        if proposal_path_value.read_bytes() != proposal_before:
            raise ValueError("The source proposal changed during acceptance.")
    except Exception:
        rollback_created_paths(created_paths)
        raise

    return (
        created_paths[0],
        created_paths[1],
        created_paths[2],
    )


# Historical Pool Test 2 workflow retained for regression compatibility.
# New operational acceptance must use accept_workout_proposal().
def accept_pool_test_two_proposal(
    *,
    parent_generated_workout_path: Path,
    previous_result_path: Path,
    proposal_directory: Path = PROPOSALS_DIRECTORY,
    acceptance_directory: Path = PROPOSAL_ACCEPTANCES_DIRECTORY,
    generated_directory: Path = GENERATED_WORKOUTS_DIRECTORY,
    result_directory: Path = SESSION_RESULTS_DIRECTORY,
) -> tuple[Path, Path, Path, Path]:
    ensure_input_file(
        parent_generated_workout_path,
        "Parent generated workout",
    )
    ensure_input_file(
        previous_result_path,
        "Previous session result",
    )

    parent_generated_workout = load_generated_workout(parent_generated_workout_path)
    previous_result = load_session_result(previous_result_path)

    proposal = build_pool_test_two_proposal(
        parent_generated_workout,
        previous_result,
    )
    acceptance = build_proposal_acceptance(proposal)
    generated_workout = proposal.proposed_generated_workout
    blank_result = build_not_started_result(proposal)

    validate_acceptance_set(
        proposal=proposal,
        acceptance=acceptance,
        blank_result=blank_result,
    )

    proposal_destination = proposal_path(
        proposal.proposal_id,
        proposal_directory,
    )
    acceptance_destination = proposal_acceptance_path(
        acceptance.acceptance_id,
        acceptance_directory,
    )
    generated_destination = generated_workout_path(
        generated_workout.generated_workout_id,
        generated_directory,
    )
    result_destination = session_result_path(
        blank_result.session_result_id,
        result_directory,
    )

    destinations = (
        proposal_destination,
        acceptance_destination,
        generated_destination,
        result_destination,
    )
    preflight_destinations(destinations)

    created_paths: list[Path] = []

    try:
        created_paths.append(save_proposal(proposal, proposal_directory))
        created_paths.append(
            save_proposal_acceptance(
                acceptance,
                acceptance_directory,
            )
        )
        created_paths.append(
            save_generated_workout(
                generated_workout,
                generated_directory,
            )
        )
        created_paths.append(
            save_session_result(
                generated_workout,
                blank_result,
                result_directory,
            )
        )

        validate_persisted_acceptance_set(
            proposal_path_value=created_paths[0],
            acceptance_path_value=created_paths[1],
            generated_path_value=created_paths[2],
            result_path_value=created_paths[3],
        )
    except Exception:
        rollback_created_paths(created_paths)
        raise

    return (
        created_paths[0],
        created_paths[1],
        created_paths[2],
        created_paths[3],
    )


def main() -> None:
    arguments = parse_arguments()

    paths = accept_workout_proposal(
        proposal_path_value=arguments.proposal,
    )

    acceptance = load_proposal_acceptance(paths[0])
    generated_workout = load_generated_workout(paths[1])
    blank_result = load_session_result(paths[2])

    print(f"Acceptance: {paths[0]}")
    print(f"Generated workout: {paths[1]}")
    print(f"Initial session result: {paths[2]}")
    print(f"Proposal ID: {acceptance.proposal_id}")
    print(f"Acceptance ID: {acceptance.acceptance_id}")
    print(f"Generated workout ID: {generated_workout.generated_workout_id}")
    print(f"Result ID: {blank_result.session_result_id}")
    print(f"Completion status: {blank_result.completion_status.value}")


if __name__ == "__main__":
    main()
