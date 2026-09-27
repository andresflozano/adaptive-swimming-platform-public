from __future__ import annotations

import argparse
import importlib
from pathlib import Path

from adaptive_swimming.persistence.proposal_records import (
    load_proposal,
    proposal_path,
    save_proposal,
)
from adaptive_swimming.persistence.session_records import PROPOSALS_DIRECTORY
from adaptive_swimming.planning.configurable_workout_proposal import (
    TargetApplicationSelection,
)
from adaptive_swimming.planning.workout_proposal import (
    AdaptationTraceEntry,
    NextWorkoutProposal,
)

preview_workflow = importlib.import_module(
    "scripts.preview_workout_proposal" if __package__ else "preview_workout_proposal"
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build and persist one reviewed workout proposal without accepting it "
            "or creating execution records."
        )
    )
    parser.add_argument("--parent-generated-workout", type=Path, required=True)
    parser.add_argument("--previous-result", type=Path, required=True)
    parser.add_argument("--review-set", type=Path, required=True)
    parser.add_argument("--review-decision-id", required=True)
    parser.add_argument("--block-sequence", type=int, required=True)
    parser.add_argument("--set-group-sequence", type=int, required=True)
    parser.add_argument("--item-sequence", type=int, required=True)
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--proposal-version", type=int, required=True)
    parser.add_argument("--generated-workout-id", required=True)
    parser.add_argument("--generated-workout-version", type=int, required=True)
    parser.add_argument("--workout-session-id", required=True)
    parser.add_argument("--generation-reason", required=True)
    return parser.parse_args()


def require_input_file(
    path: Path,
    record_name: str,
) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{record_name} file does not exist: {path}")


def validate_persisted_proposal(
    path: Path,
    source: NextWorkoutProposal,
) -> None:
    loaded = load_proposal(path)
    if loaded != source:
        raise ValueError("Persisted proposal does not match the reviewed source proposal.")


def create_workout_proposal(
    *,
    parent_generated_workout_path: Path,
    previous_result_path: Path,
    review_set_path: Path,
    review_decision_id: str,
    selection: TargetApplicationSelection,
    proposal_id: str,
    proposal_version: int,
    generated_workout_id: str,
    generated_workout_version: int,
    workout_session_id: str,
    generation_reason: str,
    proposal_directory: Path = PROPOSALS_DIRECTORY,
) -> Path:
    require_input_file(
        parent_generated_workout_path,
        "Parent generated workout",
    )
    require_input_file(
        previous_result_path,
        "Previous result",
    )
    require_input_file(
        review_set_path,
        "Review set",
    )

    input_paths = (
        parent_generated_workout_path,
        previous_result_path,
        review_set_path,
    )
    input_bytes_before = {path: path.read_bytes() for path in input_paths}

    proposal = preview_workflow.build_preview(
        parent_generated_workout_path=parent_generated_workout_path,
        previous_result_path=previous_result_path,
        review_set_path=review_set_path,
        review_decision_id=review_decision_id,
        selection=selection,
        proposal_id=proposal_id,
        proposal_version=proposal_version,
        generated_workout_id=generated_workout_id,
        generated_workout_version=generated_workout_version,
        workout_session_id=workout_session_id,
        generation_reason=generation_reason,
    )

    proposal_payload = proposal.model_dump()
    proposal_payload["adaptation_trace"] = (
        AdaptationTraceEntry(
            rule_id="APPLY_EXPLICIT_REVIEWED_TARGET",
            description=(
                f"Applied reviewed decision {review_decision_id} at coordinate "
                f"({selection.block_sequence}, {selection.set_group_sequence}, "
                f"{selection.item_sequence})."
            ),
        ).model_dump(),
    )
    proposal_payload["limitations"] = (
        "Proposal persistence does not imply acceptance or execution.",
        "The reviewed target remains provisional until evaluated in a completed session.",
        (
            "Time feasibility status at proposal creation: "
            f"{proposal.time_feasibility.status.value}."
        ),
    )
    proposal = NextWorkoutProposal.model_validate(proposal_payload)

    destination = proposal_path(proposal.proposal_id, proposal_directory)
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing proposal: {destination}")

    created_path: Path | None = None
    try:
        created_path = save_proposal(proposal, proposal_directory)
        validate_persisted_proposal(created_path, proposal)

        changed_inputs = tuple(
            path for path in input_paths if path.read_bytes() != input_bytes_before[path]
        )
        if changed_inputs:
            raise ValueError(f"Proposal creation modified input records: {changed_inputs}")
    except Exception:
        if created_path is not None and created_path.exists():
            created_path.unlink()
        raise

    return created_path


def main() -> None:
    arguments = parse_arguments()
    selection = TargetApplicationSelection(
        block_sequence=arguments.block_sequence,
        set_group_sequence=arguments.set_group_sequence,
        item_sequence=arguments.item_sequence,
    )
    path = create_workout_proposal(
        parent_generated_workout_path=arguments.parent_generated_workout,
        previous_result_path=arguments.previous_result,
        review_set_path=arguments.review_set,
        review_decision_id=arguments.review_decision_id,
        selection=selection,
        proposal_id=arguments.proposal_id,
        proposal_version=arguments.proposal_version,
        generated_workout_id=arguments.generated_workout_id,
        generated_workout_version=arguments.generated_workout_version,
        workout_session_id=arguments.workout_session_id,
        generation_reason=arguments.generation_reason,
    )
    proposal = load_proposal(path)
    print(f"Saved proposal: {path}")
    print(f"Proposal ID: {proposal.proposal_id}")
    print(f"Generated workout ID: {proposal.proposed_generated_workout.generated_workout_id}")
    print(f"Status: {proposal.status.value}")
    print(f"Time feasibility: {proposal.time_feasibility.status.value}")
    print("Acceptance records created: none")
    print("Execution records created: none")


if __name__ == "__main__":
    main()
