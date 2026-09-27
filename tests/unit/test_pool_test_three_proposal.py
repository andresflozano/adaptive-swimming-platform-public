from __future__ import annotations

from pathlib import Path

import pytest

from adaptive_swimming.domain.session_results import (
    CompletionStatus,
    GeneratedWorkout,
    WorkoutSessionResult,
)
from adaptive_swimming.domain.workout import (
    EquipmentCode,
    ExerciseCode,
    IntensityCode,
    SetItem,
    TargetType,
)
from adaptive_swimming.evaluation.pace_calibration import (
    PaceObservation,
    PaceObservationKey,
    ProvisionalPaceSummary,
)
from adaptive_swimming.planning.pool_test_three_proposal import (
    build_pool_test_three_proposal,
)
from adaptive_swimming.planning.provisional_target_proposals import (
    ProvisionalTargetProposal,
    propose_target_for_review,
)
from adaptive_swimming.planning.target_review_decisions import (
    TargetReviewDecision,
    TargetReviewDecisionType,
    record_target_review_decision,
)
from adaptive_swimming.planning.workout_proposal import (
    NextWorkoutProposal,
    ProposalStatus,
    build_pool_test_two_workout,
)

PARENT_WORKOUT_ID = "GW_20260903_001_V1"
PREVIOUS_RESULT_ID = "SR_20260903_001_V2"
PROPOSAL_ID = "NWP_20260905_001_V1"
GENERATED_WORKOUT_ID = "GW_20260905_001_V1"


def build_parent() -> GeneratedWorkout:
    return GeneratedWorkout(
        generated_workout_id=PARENT_WORKOUT_ID,
        workout_version=1,
        workout=build_pool_test_two_workout(),
        pool_length_meters=12.5,
        available_training_seconds=3600,
        equipment_available=(
            EquipmentCode.FINS,
            EquipmentCode.PADDLES,
            EquipmentCode.KICKBOARD,
        ),
        generation_reason="POOL_TEST_2_TIME_CONSTRAINED_PROPOSAL",
    )


def build_previous_result() -> WorkoutSessionResult:
    return WorkoutSessionResult(
        session_result_id=PREVIOUS_RESULT_ID,
        generated_workout_id=PARENT_WORKOUT_ID,
        result_version=2,
        completion_status=CompletionStatus.COMPLETED_AS_WRITTEN,
        completed_distance_meters=1500,
        actual_total_seconds=3093,
        perceived_exertion=7,
        safety_issue_reported=False,
    )


def build_provisional_proposal(
    *,
    key: PaceObservationKey,
    values: tuple[int, ...],
) -> ProvisionalTargetProposal:
    session_ids = tuple(
        "SR_20260901_001_V2" if index < len(values) // 2 else PREVIOUS_RESULT_ID
        for index in range(len(values))
    )
    observations = tuple(
        PaceObservation(
            generated_workout_id=(
                "GW_20260901_001_V1" if session_id == "SR_20260901_001_V2" else PARENT_WORKOUT_ID
            ),
            session_result_id=session_id,
            block_sequence=4 if key.distance_meters == 50 else 2,
            set_group_sequence=1,
            item_sequence=1,
            repetition_number=index,
            key=key,
            actual_seconds=value,
        )
        for index, (value, session_id) in enumerate(
            zip(values, session_ids, strict=True),
            start=1,
        )
    )
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    median_seconds = (
        float(ordered[midpoint])
        if len(ordered) % 2
        else (ordered[midpoint - 1] + ordered[midpoint]) / 2
    )
    summary = ProvisionalPaceSummary(
        key=key,
        sample_count=len(values),
        minimum_seconds=min(values),
        maximum_seconds=max(values),
        mean_seconds=sum(values) / len(values),
        median_seconds=median_seconds,
        observations=observations,
        limitations=("Synthetic test summary.",),
    )
    from adaptive_swimming.evaluation.calibration_eligibility import (
        assess_calibration_eligibility,
    )

    return propose_target_for_review(assess_calibration_eligibility(summary))


def build_decisions() -> tuple[TargetReviewDecision, TargetReviewDecision]:
    fins_key = PaceObservationKey(
        exercise=ExerciseCode.FREESTYLE,
        distance_meters=50,
        equipment=(EquipmentCode.FINS,),
        intensity=IntensityCode.UNRESOLVED,
    )
    paddles_key = PaceObservationKey(
        exercise=ExerciseCode.FREESTYLE,
        distance_meters=100,
        equipment=(EquipmentCode.PADDLES_INVERTED,),
        intensity=IntensityCode.UNRESOLVED,
    )
    fins_proposal = build_provisional_proposal(
        key=fins_key,
        values=(62, 65, 65, 75, 65, 64, 62, 64),
    )
    paddles_proposal = build_provisional_proposal(
        key=paddles_key,
        values=(155, 155, 157, 157),
    )
    accepted = record_target_review_decision(
        fins_proposal,
        review_decision_id="TRD_20260905_001_V1",
        review_decision_version=1,
        decision=TargetReviewDecisionType.ACCEPTED_FOR_FUTURE_WORKOUT,
        rationale=("Accepted for a controlled Pool Test 3 proposal.",),
    )
    deferred = record_target_review_decision(
        paddles_proposal,
        review_decision_id="TRD_20260905_002_V1",
        review_decision_version=1,
        decision=TargetReviewDecisionType.DEFERRED,
        rationale=("Deferred because this is preparation work.",),
    )
    return accepted, deferred


def build_proposal() -> NextWorkoutProposal:
    accepted, deferred = build_decisions()
    return build_pool_test_three_proposal(
        build_parent(),
        build_previous_result(),
        accepted,
        deferred,
        proposal_id=PROPOSAL_ID,
        generated_workout_id=GENERATED_WORKOUT_ID,
    )


def planned_items(
    proposal: NextWorkoutProposal,
) -> tuple[tuple[int, int, SetItem], ...]:
    return tuple(
        (block.sequence, group.sequence, item)
        for block in proposal.proposed_generated_workout.workout.blocks
        for group in block.set_groups
        for item in group.items
    )


def test_proposal_references_pool_test_two_lineage() -> None:
    proposal = build_proposal()
    assert proposal.parent_generated_workout_id == PARENT_WORKOUT_ID
    assert proposal.previous_session_result_id == PREVIOUS_RESULT_ID
    assert proposal.status == ProposalStatus.PROPOSED
    assert proposal.proposed_generated_workout.generated_workout_id == GENERATED_WORKOUT_ID


def test_only_fifty_meter_fins_item_has_target() -> None:
    proposal = build_proposal()
    targeted = tuple(entry for entry in planned_items(proposal) if entry[2].target is not None)
    assert len(targeted) == 1
    block_sequence, group_sequence, item = targeted[0]
    assert (block_sequence, group_sequence, item.sequence) == (4, 1, 1)
    assert item.exercise == ExerciseCode.FREESTYLE
    assert item.distance_meters == 50
    assert item.repetitions == 4
    assert item.equipment == (EquipmentCode.FINS,)
    assert item.target is not None
    assert item.target.target_type == TargetType.REPETITION_COMPLETION_TIME
    assert item.target.raw_value == "1:05"
    assert item.target.target_seconds == 65


def test_paddles_and_aerobic_items_remain_without_targets() -> None:
    proposal = build_proposal()
    items = planned_items(proposal)
    paddles = next(item for block, _group, item in items if block == 2)
    aerobic = next(item for block, _group, item in items if block == 3)
    assert paddles.target is None
    assert aerobic.target is None


def test_structure_distance_environment_and_availability_are_preserved() -> None:
    parent = build_parent()
    accepted, deferred = build_decisions()
    proposal = build_pool_test_three_proposal(
        parent,
        build_previous_result(),
        accepted,
        deferred,
        proposal_id=PROPOSAL_ID,
        generated_workout_id=GENERATED_WORKOUT_ID,
    )
    generated = proposal.proposed_generated_workout
    assert len(generated.workout.blocks) == 6
    assert generated.workout.total_distance_meters() == 1500
    assert generated.pool_length_meters == 12.5
    assert generated.available_training_seconds == 3600
    assert generated.equipment_available == parent.equipment_available


def test_rest_policies_and_exercise_order_are_preserved() -> None:
    parent = build_parent()
    accepted, deferred = build_decisions()
    proposal = build_pool_test_three_proposal(
        parent,
        build_previous_result(),
        accepted,
        deferred,
        proposal_id=PROPOSAL_ID,
        generated_workout_id=GENERATED_WORKOUT_ID,
    )
    proposed = proposal.proposed_generated_workout.workout
    parent_rests = tuple(
        group.rest for block in parent.workout.blocks for group in block.set_groups
    )
    proposed_rests = tuple(group.rest for block in proposed.blocks for group in block.set_groups)
    parent_exercises = tuple(
        item.exercise
        for block in parent.workout.blocks
        for group in block.set_groups
        for item in group.items
    )
    proposed_exercises = tuple(
        item.exercise
        for block in proposed.blocks
        for group in block.set_groups
        for item in group.items
    )
    assert proposed_rests == parent_rests
    assert proposed_exercises == parent_exercises


def test_targeted_duration_is_known_but_feasibility_remains_unresolved() -> None:
    proposal = build_proposal()
    feasibility = proposal.time_feasibility
    duration = proposal.proposed_generated_workout.workout.swim_duration_summary()
    assert duration.known_seconds == 260
    assert duration.known_distance_meters == 200
    assert duration.unresolved_distance_meters == 1300
    assert feasibility.status.value == "UNRESOLVED"


def test_adaptation_trace_and_limitations_preserve_scope() -> None:
    proposal = build_proposal()
    rule_ids = {entry.rule_id for entry in proposal.adaptation_trace}
    assert "APPLY_ACCEPTED_FINS_TARGET" in rule_ids
    assert "EXCLUDE_DEFERRED_PADDLES_TARGET" in rule_ids
    assert any("30 seconds" in value for value in proposal.limitations)
    assert any("not persisted or accepted" in value for value in proposal.limitations)


def test_parent_result_and_decisions_remain_unchanged() -> None:
    parent = build_parent()
    result = build_previous_result()
    accepted, deferred = build_decisions()
    before = tuple(value.model_dump_json() for value in (parent, result, accepted, deferred))
    build_pool_test_three_proposal(
        parent,
        result,
        accepted,
        deferred,
        proposal_id=PROPOSAL_ID,
        generated_workout_id=GENERATED_WORKOUT_ID,
    )
    after = tuple(value.model_dump_json() for value in (parent, result, accepted, deferred))
    assert after == before


def test_nonaccepted_fins_decision_is_rejected() -> None:
    accepted, deferred = build_decisions()
    payload = accepted.model_dump()
    payload["decision"] = TargetReviewDecisionType.DEFERRED
    invalid = TargetReviewDecision.model_validate(payload)
    with pytest.raises(ValueError, match="must be accepted"):
        build_pool_test_three_proposal(
            build_parent(),
            build_previous_result(),
            invalid,
            deferred,
            proposal_id=PROPOSAL_ID,
            generated_workout_id=GENERATED_WORKOUT_ID,
        )


def test_wrong_fins_target_is_rejected() -> None:
    accepted, deferred = build_decisions()
    payload = accepted.model_dump()
    payload["reviewed_target_seconds"] = 66
    payload["proposal"]["proposed_target_seconds"] = 66
    invalid = TargetReviewDecision.model_validate(payload)
    with pytest.raises(ValueError, match="must be 65 seconds"):
        build_pool_test_three_proposal(
            build_parent(),
            build_previous_result(),
            invalid,
            deferred,
            proposal_id=PROPOSAL_ID,
            generated_workout_id=GENERATED_WORKOUT_ID,
        )


def test_non_deferred_paddles_decision_is_rejected() -> None:
    accepted, deferred = build_decisions()
    payload = deferred.model_dump()
    payload["decision"] = TargetReviewDecisionType.REJECTED
    invalid = TargetReviewDecision.model_validate(payload)
    with pytest.raises(ValueError, match="must be deferred"):
        build_pool_test_three_proposal(
            build_parent(),
            build_previous_result(),
            accepted,
            invalid,
            proposal_id=PROPOSAL_ID,
            generated_workout_id=GENERATED_WORKOUT_ID,
        )


def test_invalid_result_linkage_is_rejected() -> None:
    accepted, deferred = build_decisions()
    invalid_result = build_previous_result().model_copy(
        update={"generated_workout_id": "GW_20260903_999_V1"}
    )
    with pytest.raises(ValueError, match="does not belong"):
        build_pool_test_three_proposal(
            build_parent(),
            invalid_result,
            accepted,
            deferred,
            proposal_id=PROPOSAL_ID,
            generated_workout_id=GENERATED_WORKOUT_ID,
        )


def test_proposal_round_trips_through_json() -> None:
    proposal = build_proposal()
    assert NextWorkoutProposal.model_validate_json(proposal.model_dump_json()) == proposal


def test_builder_does_not_persist_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    build_proposal()
    assert not tuple(tmp_path.rglob("*.json"))
