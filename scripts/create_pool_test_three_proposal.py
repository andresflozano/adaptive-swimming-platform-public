from __future__ import annotations

import argparse
from pathlib import Path

from adaptive_swimming.persistence.proposal_records import (
    load_proposal,
    proposal_path,
)
from adaptive_swimming.persistence.proposal_records import (
    save_proposal as save_proposal,
)
from adaptive_swimming.persistence.session_records import (
    PROPOSALS_DIRECTORY,
    load_generated_workout,
    load_session_result,
)
from adaptive_swimming.persistence.target_review_records import (
    load_target_review_decision,
)
from adaptive_swimming.planning.pool_test_three_proposal import (
    build_pool_test_three_proposal,
)
from adaptive_swimming.planning.pool_test_three_validation import (
    validate_pool_test_three_proposal,
)
from adaptive_swimming.planning.workout_proposal import NextWorkoutProposal


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build and persist a proposed Pool Test 3 workout without "
            "accepting it or creating execution records."
        )
    )
    parser.add_argument("--parent-generated-workout", type=Path, required=True)
    parser.add_argument("--previous-result", type=Path, required=True)
    parser.add_argument("--accepted-fins-decision", type=Path, required=True)
    parser.add_argument("--deferred-paddles-decision", type=Path, required=True)
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--generated-workout-id", required=True)
    return parser.parse_args()


def validate_persisted_proposal(
    path: Path,
    source: NextWorkoutProposal,
) -> None:
    loaded = load_proposal(path)
    if loaded != source:
        raise ValueError("Persisted Pool Test 3 proposal does not match the source proposal.")
    validate_pool_test_three_proposal(
        loaded,
        expected_parent_id=source.parent_generated_workout_id,
        expected_previous_result_id=source.previous_session_result_id,
        expected_generated_workout_id=(source.proposed_generated_workout.generated_workout_id),
    )


def create_pool_test_three_proposal(
    *,
    parent_generated_workout_path: Path,
    previous_result_path: Path,
    accepted_fins_decision_path: Path,
    deferred_paddles_decision_path: Path,
    proposal_id: str,
    generated_workout_id: str,
    proposal_directory: Path = PROPOSALS_DIRECTORY,
) -> Path:
    parent = load_generated_workout(parent_generated_workout_path)
    previous_result = load_session_result(previous_result_path)
    accepted_fins = load_target_review_decision(accepted_fins_decision_path)
    deferred_paddles = load_target_review_decision(deferred_paddles_decision_path)

    proposal = build_pool_test_three_proposal(
        parent,
        previous_result,
        accepted_fins,
        deferred_paddles,
        proposal_id=proposal_id,
        generated_workout_id=generated_workout_id,
    )
    validate_pool_test_three_proposal(
        proposal,
        expected_parent_id=parent.generated_workout_id,
        expected_previous_result_id=previous_result.session_result_id,
        expected_generated_workout_id=generated_workout_id,
    )

    destination = proposal_path(proposal_id, proposal_directory)
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing Pool Test 3 proposal: {destination}")

    created_path: Path | None = None
    try:
        created_path = save_proposal(proposal, proposal_directory)
        validate_persisted_proposal(created_path, proposal)
    except Exception:
        if created_path is not None and created_path.exists():
            created_path.unlink()
        raise

    return created_path


def main() -> None:
    arguments = parse_arguments()
    path = create_pool_test_three_proposal(
        parent_generated_workout_path=arguments.parent_generated_workout,
        previous_result_path=arguments.previous_result,
        accepted_fins_decision_path=arguments.accepted_fins_decision,
        deferred_paddles_decision_path=arguments.deferred_paddles_decision,
        proposal_id=arguments.proposal_id,
        generated_workout_id=arguments.generated_workout_id,
    )
    proposal = load_proposal(path)
    print(f"Saved Pool Test 3 proposal: {path}")
    print(f"Proposal ID: {proposal.proposal_id}")
    print(f"Generated workout ID: {proposal.proposed_generated_workout.generated_workout_id}")
    print(f"Status: {proposal.status.value}")
    print("Targeted item: Block 4, 4 x 50 m freestyle with fins")
    print("Target per repetition: 65 seconds")
    print(f"Time feasibility: {proposal.time_feasibility.status.value}")


if __name__ == "__main__":
    main()
