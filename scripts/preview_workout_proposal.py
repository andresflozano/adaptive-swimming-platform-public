from __future__ import annotations

import argparse
from pathlib import Path

from adaptive_swimming.persistence.recalibrated_target_review_records import (
    load_recalibrated_review_set,
)
from adaptive_swimming.persistence.session_records import (
    load_generated_workout,
    load_session_result,
)
from adaptive_swimming.planning.configurable_workout_proposal import (
    TargetApplicationSelection,
    build_configurable_workout_proposal,
)
from adaptive_swimming.planning.recalibrated_target_review import (
    RecalibratedTargetReviewDecision,
    applicable_target_seconds,
)
from adaptive_swimming.planning.workout_proposal import (
    AdaptationTraceEntry,
    NextWorkoutProposal,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Preview a configurable workout proposal from explicit persisted inputs "
            "without writing any records."
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
    parser.add_argument(
        "--output-format",
        choices=("summary", "json"),
        default="summary",
    )
    return parser.parse_args()


def require_input_file(path: Path, record_name: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{record_name} file does not exist: {path}")


def select_review_decision(
    *,
    review_set_path: Path,
    review_decision_id: str,
) -> RecalibratedTargetReviewDecision:
    require_input_file(review_set_path, "Review set")
    review_set = load_recalibrated_review_set(review_set_path)
    matches = tuple(
        decision
        for decision in review_set.decisions
        if decision.review_decision_id == review_decision_id
    )
    if len(matches) != 1:
        raise ValueError(
            "Expected exactly one review decision with ID "
            f"{review_decision_id}; found {len(matches)}."
        )
    return matches[0]


def build_preview(
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
) -> NextWorkoutProposal:
    require_input_file(parent_generated_workout_path, "Parent generated workout")
    require_input_file(previous_result_path, "Previous result")

    input_paths = (
        parent_generated_workout_path,
        previous_result_path,
        review_set_path,
    )
    before = {path: path.read_bytes() for path in input_paths}

    parent = load_generated_workout(parent_generated_workout_path)
    previous_result = load_session_result(previous_result_path)
    reviewed_decision = select_review_decision(
        review_set_path=review_set_path,
        review_decision_id=review_decision_id,
    )

    proposal = build_configurable_workout_proposal(
        parent_generated_workout=parent,
        previous_result=previous_result,
        reviewed_decision=reviewed_decision,
        selection=selection,
        proposal_id=proposal_id,
        proposal_version=proposal_version,
        generated_workout_id=generated_workout_id,
        generated_workout_version=generated_workout_version,
        workout_session_id=workout_session_id,
        generation_reason=generation_reason,
        adaptation_trace=(
            AdaptationTraceEntry(
                rule_id="APPLY_EXPLICIT_REVIEWED_TARGET",
                description=(
                    f"Previewed decision {reviewed_decision.review_decision_id} at "
                    f"coordinate ({selection.block_sequence}, "
                    f"{selection.set_group_sequence}, {selection.item_sequence})."
                ),
            ),
        ),
        limitations=(
            "Preview only; no proposal, acceptance, workout, or result was persisted.",
            "The reviewed target remains provisional until evaluated in a completed session.",
        ),
    )

    changed_inputs = tuple(path for path in input_paths if path.read_bytes() != before[path])
    if changed_inputs:
        raise ValueError(f"Preview modified input records: {changed_inputs}")

    return proposal


def render_summary(
    proposal: NextWorkoutProposal,
    reviewed_decision: RecalibratedTargetReviewDecision,
    selection: TargetApplicationSelection,
) -> str:
    key = reviewed_decision.proposal.key
    return "\n".join(
        (
            f"Proposal ID: {proposal.proposal_id}",
            f"Generated workout ID: {proposal.proposed_generated_workout.generated_workout_id}",
            f"Status: {proposal.status.value}",
            f"Parent workout: {proposal.parent_generated_workout_id}",
            f"Previous result: {proposal.previous_session_result_id}",
            f"Review decision: {reviewed_decision.review_decision_id}",
            f"Review action: {reviewed_decision.action.value}",
            f"Recalibration proposal: {reviewed_decision.proposal.proposed_target_seconds} seconds",
            f"Effective target: {applicable_target_seconds(reviewed_decision)} seconds",
            (
                "Strict key: "
                f"{key.exercise.value}, {key.distance_meters} m, "
                f"equipment={[item.value for item in key.equipment]}, "
                f"intensity={key.intensity.value}"
            ),
            (
                "Selected coordinate: "
                f"{selection.block_sequence}, {selection.set_group_sequence}, "
                f"{selection.item_sequence}"
            ),
            f"Time feasibility: {proposal.time_feasibility.status.value}",
            "Writes performed: none",
        )
    )


def main() -> None:
    arguments = parse_arguments()
    selection = TargetApplicationSelection(
        block_sequence=arguments.block_sequence,
        set_group_sequence=arguments.set_group_sequence,
        item_sequence=arguments.item_sequence,
    )
    reviewed_decision = select_review_decision(
        review_set_path=arguments.review_set,
        review_decision_id=arguments.review_decision_id,
    )
    proposal = build_preview(
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

    if arguments.output_format == "json":
        print(proposal.model_dump_json(indent=2))
    else:
        print(render_summary(proposal, reviewed_decision, selection))


if __name__ == "__main__":
    main()
