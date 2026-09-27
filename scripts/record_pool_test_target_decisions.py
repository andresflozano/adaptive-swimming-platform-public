from __future__ import annotations

import argparse
from pathlib import Path

from adaptive_swimming.domain.workout import (
    EquipmentCode,
    ExerciseCode,
    IntensityCode,
)
from adaptive_swimming.evaluation.calibration_eligibility import (
    assess_calibration_summaries,
)
from adaptive_swimming.evaluation.pace_calibration import (
    PaceObservationKey,
    calibrate_pace_from_sessions,
)
from adaptive_swimming.persistence.session_records import (
    TARGET_REVIEW_DECISIONS_DIRECTORY,
    load_generated_workout,
    load_session_result,
)
from adaptive_swimming.persistence.target_review_records import (
    load_target_review_decision,
    target_review_decision_path,
)
from adaptive_swimming.persistence.target_review_records import (
    save_target_review_decision as save_target_review_decision,
)
from adaptive_swimming.planning.provisional_target_proposals import (
    ProvisionalTargetProposal,
    propose_eligible_targets_for_review,
)
from adaptive_swimming.planning.target_review_decisions import (
    TargetReviewDecision,
    TargetReviewDecisionType,
    record_target_review_decision,
)

FINS_KEY = PaceObservationKey(
    exercise=ExerciseCode.FREESTYLE,
    distance_meters=50,
    equipment=(EquipmentCode.FINS,),
    intensity=IntensityCode.UNRESOLVED,
)
PADDLES_KEY = PaceObservationKey(
    exercise=ExerciseCode.FREESTYLE,
    distance_meters=100,
    equipment=(EquipmentCode.PADDLES_INVERTED,),
    intensity=IntensityCode.UNRESOLVED,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Record the reviewed Pool Test pace-target decisions "
            "without overwriting existing records."
        )
    )
    parser.add_argument("--pool-test-one-workout", type=Path, required=True)
    parser.add_argument("--pool-test-one-result", type=Path, required=True)
    parser.add_argument("--pool-test-two-workout", type=Path, required=True)
    parser.add_argument("--pool-test-two-result", type=Path, required=True)
    return parser.parse_args()


def find_proposal(
    proposals: tuple[ProvisionalTargetProposal, ...],
    key: PaceObservationKey,
) -> ProvisionalTargetProposal:
    matches = tuple(proposal for proposal in proposals if proposal.key == key)
    if len(matches) != 1:
        raise ValueError(
            "Expected exactly one eligible target proposal for "
            f"{key.model_dump_json()}; found {len(matches)}."
        )
    return matches[0]


def build_pool_test_target_decisions(
    *,
    pool_test_one_workout_path: Path,
    pool_test_one_result_path: Path,
    pool_test_two_workout_path: Path,
    pool_test_two_result_path: Path,
) -> tuple[TargetReviewDecision, TargetReviewDecision]:
    pairs = (
        (
            load_generated_workout(pool_test_one_workout_path),
            load_session_result(pool_test_one_result_path),
        ),
        (
            load_generated_workout(pool_test_two_workout_path),
            load_session_result(pool_test_two_result_path),
        ),
    )
    summaries = calibrate_pace_from_sessions(pairs)
    assessments = assess_calibration_summaries(summaries)
    proposals = propose_eligible_targets_for_review(assessments)

    if len(proposals) != 2:
        raise ValueError(
            f"Expected exactly two eligible Pool Test target proposals; found {len(proposals)}."
        )

    fins_proposal = find_proposal(proposals, FINS_KEY)
    paddles_proposal = find_proposal(proposals, PADDLES_KEY)

    if fins_proposal.proposed_target_seconds != 65:
        raise ValueError("Expected the fins review anchor to be 65 seconds.")
    if paddles_proposal.proposed_target_seconds != 156:
        raise ValueError("Expected the inverted-paddles review anchor to be 156 seconds.")

    accepted_fins = record_target_review_decision(
        fins_proposal,
        review_decision_id="TRD_20260905_001_V1",
        review_decision_version=1,
        decision=TargetReviewDecisionType.ACCEPTED_FOR_FUTURE_WORKOUT,
        rationale=(
            "Accept as the single controlled target change for a future Pool Test 3 proposal.",
        ),
    )
    deferred_paddles = record_target_review_decision(
        paddles_proposal,
        review_decision_id="TRD_20260905_002_V1",
        review_decision_version=1,
        decision=TargetReviewDecisionType.DEFERRED,
        rationale=(
            "Preserve as an observation anchor because the block serves a "
            "preparation role rather than the primary target set.",
        ),
    )
    return accepted_fins, deferred_paddles


def preflight_destinations(destinations: tuple[Path, ...]) -> None:
    existing = tuple(path for path in destinations if path.exists())
    if existing:
        raise FileExistsError(
            f"Refusing to create a partial or duplicate target-review decision set: {existing}"
        )


def rollback_created_paths(created_paths: list[Path]) -> None:
    for path in reversed(created_paths):
        if path.exists():
            path.unlink()


def validate_persisted_decisions(
    accepted_path: Path,
    deferred_path: Path,
    accepted_source: TargetReviewDecision,
    deferred_source: TargetReviewDecision,
) -> None:
    accepted = load_target_review_decision(accepted_path)
    deferred = load_target_review_decision(deferred_path)
    if accepted != accepted_source or deferred != deferred_source:
        raise ValueError("Persisted target-review decisions do not match their sources.")
    if not accepted.may_be_applied_to_future_workout:
        raise ValueError("The fins decision must permit future application.")
    if deferred.may_be_applied_to_future_workout:
        raise ValueError("The paddles decision must remain unapplied.")


def record_pool_test_target_decisions(
    *,
    pool_test_one_workout_path: Path,
    pool_test_one_result_path: Path,
    pool_test_two_workout_path: Path,
    pool_test_two_result_path: Path,
    decision_directory: Path = TARGET_REVIEW_DECISIONS_DIRECTORY,
) -> tuple[Path, Path]:
    accepted, deferred = build_pool_test_target_decisions(
        pool_test_one_workout_path=pool_test_one_workout_path,
        pool_test_one_result_path=pool_test_one_result_path,
        pool_test_two_workout_path=pool_test_two_workout_path,
        pool_test_two_result_path=pool_test_two_result_path,
    )
    accepted_destination = target_review_decision_path(
        accepted.review_decision_id, decision_directory
    )
    deferred_destination = target_review_decision_path(
        deferred.review_decision_id, decision_directory
    )
    preflight_destinations((accepted_destination, deferred_destination))

    created_paths: list[Path] = []
    try:
        created_paths.append(save_target_review_decision(accepted, decision_directory))
        created_paths.append(save_target_review_decision(deferred, decision_directory))
        validate_persisted_decisions(created_paths[0], created_paths[1], accepted, deferred)
    except Exception:
        rollback_created_paths(created_paths)
        raise

    return created_paths[0], created_paths[1]


def main() -> None:
    arguments = parse_arguments()
    paths = record_pool_test_target_decisions(
        pool_test_one_workout_path=arguments.pool_test_one_workout,
        pool_test_one_result_path=arguments.pool_test_one_result,
        pool_test_two_workout_path=arguments.pool_test_two_workout,
        pool_test_two_result_path=arguments.pool_test_two_result,
    )
    for path in paths:
        decision = load_target_review_decision(path)
        print(f"Saved target review decision: {path}")
        print(f"Decision ID: {decision.review_decision_id}")
        print(f"Decision: {decision.decision.value}")
        print(f"Reviewed target: {decision.reviewed_target_seconds} seconds")


if __name__ == "__main__":
    main()
