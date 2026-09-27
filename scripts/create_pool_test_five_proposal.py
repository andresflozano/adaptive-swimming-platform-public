from __future__ import annotations

import argparse
from pathlib import Path

from adaptive_swimming.domain.session_results import GeneratedWorkout
from adaptive_swimming.domain.workout import EquipmentCode
from adaptive_swimming.persistence.proposal_records import (
    load_proposal,
    proposal_path,
    save_proposal,
)
from adaptive_swimming.persistence.recalibrated_target_review_records import (
    load_recalibrated_review_set,
)
from adaptive_swimming.persistence.session_records import (
    PROPOSALS_DIRECTORY,
    load_generated_workout,
    load_session_result,
)
from adaptive_swimming.planning.pool_test_five_proposal import (
    build_pool_test_five_proposal,
)
from adaptive_swimming.planning.workout_progression import (
    WorkoutProgressionObjective,
    compare_workout_progression,
)
from adaptive_swimming.planning.workout_proposal import (
    NextWorkoutProposal,
    ProposalStatus,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build and persist the proposed adaptive Pool Test 5 workout "
            "without accepting it or creating execution records."
        )
    )
    parser.add_argument("--parent-generated-workout", type=Path, required=True)
    parser.add_argument("--previous-result", type=Path, required=True)
    parser.add_argument("--review-set", type=Path, required=True)
    parser.add_argument("--review-decision-id", required=True)
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--generated-workout-id", required=True)
    return parser.parse_args()


def require_input_file(path: Path, record_name: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{record_name} file does not exist: {path}")


def validate_pool_test_five_proposal(
    proposal: NextWorkoutProposal,
    *,
    parent_generated_workout_id: str,
    previous_result_id: str,
    generated_workout_id: str,
) -> None:
    if proposal.status != ProposalStatus.PROPOSED:
        raise ValueError("Pool Test 5 proposal must remain PROPOSED.")
    if proposal.parent_generated_workout_id != parent_generated_workout_id:
        raise ValueError("Pool Test 5 proposal parent ID does not match the loaded parent.")
    if proposal.previous_session_result_id != previous_result_id:
        raise ValueError("Pool Test 5 previous-result ID does not match the loaded result.")

    generated = proposal.proposed_generated_workout
    if generated.generated_workout_id != generated_workout_id:
        raise ValueError("Pool Test 5 generated-workout ID does not match the requested ID.")
    if generated.planned_distance_meters != 1500:
        raise ValueError("Pool Test 5 must contain exactly 1,500 planned meters.")
    if generated.available_training_seconds != 3600:
        raise ValueError("Pool Test 5 must preserve the 3,600-second availability constraint.")
    if generated.configured_rest_seconds != 360:
        raise ValueError("Pool Test 5 must contain exactly 360 configured rest seconds.")
    if proposal.time_feasibility.status.value != "UNRESOLVED":
        raise ValueError("Pool Test 5 time feasibility must remain explicitly UNRESOLVED.")

    targeted = tuple(
        (block.sequence, group.sequence, item)
        for block in generated.workout.blocks
        for group in block.set_groups
        for item in group.items
        if item.target is not None
    )
    if len(targeted) != 1:
        raise ValueError("Pool Test 5 must contain exactly one targeted item.")

    block_sequence, group_sequence, item = targeted[0]
    if (block_sequence, group_sequence, item.sequence) != (4, 1, 1):
        raise ValueError("Pool Test 5 target must remain at coordinate (4, 1, 1).")
    if item.repetitions != 4 or item.distance_meters != 50:
        raise ValueError("Pool Test 5 target must apply to 4 x 50 m repetitions.")
    if item.equipment != (EquipmentCode.FINS,):
        raise ValueError("Pool Test 5 target must apply to the fins item.")
    if item.target is None or item.target.target_seconds != 65:
        raise ValueError("Pool Test 5 fins target must remain 65 seconds.")


def validate_persisted_pool_test_five_proposal(
    path: Path,
    source: NextWorkoutProposal,
    *,
    parent_generated_workout: GeneratedWorkout,
) -> None:
    loaded = load_proposal(path)
    if loaded != source:
        raise ValueError("Persisted Pool Test 5 proposal does not match the source proposal.")

    validate_pool_test_five_proposal(
        loaded,
        parent_generated_workout_id=source.parent_generated_workout_id,
        previous_result_id=source.previous_session_result_id,
        generated_workout_id=source.proposed_generated_workout.generated_workout_id,
    )

    assessment = compare_workout_progression(
        parent=parent_generated_workout,
        candidate=loaded.proposed_generated_workout,
        objective=WorkoutProgressionObjective.ADAPTIVE_PROGRESSION,
    )
    if not assessment.satisfies_objective or not assessment.structural_changes:
        raise ValueError("Persisted Pool Test 5 proposal does not satisfy adaptive progression.")


def create_pool_test_five_proposal(
    *,
    parent_generated_workout_path: Path,
    previous_result_path: Path,
    review_set_path: Path,
    review_decision_id: str,
    proposal_id: str,
    generated_workout_id: str,
    proposal_directory: Path = PROPOSALS_DIRECTORY,
) -> Path:
    for path, name in (
        (parent_generated_workout_path, "Parent generated workout"),
        (previous_result_path, "Previous result"),
        (review_set_path, "Review set"),
    ):
        require_input_file(path, name)

    input_paths = (
        parent_generated_workout_path,
        previous_result_path,
        review_set_path,
    )
    input_bytes_before = {path: path.read_bytes() for path in input_paths}

    parent = load_generated_workout(parent_generated_workout_path)
    previous_result = load_session_result(previous_result_path)
    review_set = load_recalibrated_review_set(review_set_path)

    proposal, assessment = build_pool_test_five_proposal(
        parent,
        previous_result,
        review_set,
        review_decision_id=review_decision_id,
        proposal_id=proposal_id,
        generated_workout_id=generated_workout_id,
    )
    if not assessment.satisfies_objective or not assessment.structural_changes:
        raise ValueError("Pool Test 5 proposal does not satisfy adaptive progression.")

    validate_pool_test_five_proposal(
        proposal,
        parent_generated_workout_id=parent.generated_workout_id,
        previous_result_id=previous_result.session_result_id,
        generated_workout_id=generated_workout_id,
    )

    destination = proposal_path(proposal_id, proposal_directory)
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing Pool Test 5 proposal: {destination}")

    created_path: Path | None = None
    try:
        created_path = save_proposal(proposal, proposal_directory)
        validate_persisted_pool_test_five_proposal(
            created_path,
            proposal,
            parent_generated_workout=parent,
        )

        changed_inputs = tuple(
            path for path in input_paths if path.read_bytes() != input_bytes_before[path]
        )
        if changed_inputs:
            raise ValueError(f"Pool Test 5 proposal creation modified inputs: {changed_inputs}")
    except Exception:
        if created_path is not None and created_path.exists():
            created_path.unlink()
        raise

    return created_path


def main() -> None:
    arguments = parse_arguments()
    path = create_pool_test_five_proposal(
        parent_generated_workout_path=arguments.parent_generated_workout,
        previous_result_path=arguments.previous_result,
        review_set_path=arguments.review_set,
        review_decision_id=arguments.review_decision_id,
        proposal_id=arguments.proposal_id,
        generated_workout_id=arguments.generated_workout_id,
    )
    proposal = load_proposal(path)

    print(f"Saved Pool Test 5 proposal: {path}")
    print(f"Proposal ID: {proposal.proposal_id}")
    print(f"Generated workout ID: {proposal.proposed_generated_workout.generated_workout_id}")
    print(f"Status: {proposal.status.value}")
    print(f"Time feasibility: {proposal.time_feasibility.status.value}")
    print("Acceptance records created: none")
    print("Execution records created: none")


if __name__ == "__main__":
    main()
