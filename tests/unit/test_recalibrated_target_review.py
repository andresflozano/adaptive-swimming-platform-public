from __future__ import annotations

import pytest
from pydantic import ValidationError

from adaptive_swimming.domain.workout import (
    EquipmentCode,
    ExerciseCode,
    IntensityCode,
)
from adaptive_swimming.evaluation.calibration_eligibility import (
    assess_calibration_eligibility,
)
from adaptive_swimming.evaluation.pace_calibration import (
    PaceObservation,
    PaceObservationKey,
    ProvisionalPaceSummary,
)
from adaptive_swimming.planning.provisional_target_proposals import (
    ProvisionalTargetProposal,
    propose_target_for_review,
)
from adaptive_swimming.planning.recalibrated_target_review import (
    RecalibratedTargetReviewAction,
    RecalibratedTargetReviewDecision,
    RecalibratedTargetReviewSet,
    build_recalibrated_target_review_decision,
    build_recalibrated_target_review_set,
)
from adaptive_swimming.planning.target_review_decisions import (
    TargetReviewDecision,
    TargetReviewDecisionType,
    record_target_review_decision,
)


def test_retain_can_reference_prior_recalibrated_decision() -> None:
    proposal = build_proposal()

    first_recalibrated_decision = build_recalibrated_target_review_decision(
        proposal,
        review_decision_id=("RTRD_20260906_001_V1"),
        review_decision_version=1,
        action=(RecalibratedTargetReviewAction.RETAIN_CURRENT_TARGET),
        effective_target_seconds=65,
        prior_decision=build_prior_decision(),
        rationale=("Retain the current target.",),
    )

    next_decision = build_recalibrated_target_review_decision(
        proposal,
        review_decision_id=("RTRD_20260907_001_V1"),
        review_decision_version=1,
        action=(RecalibratedTargetReviewAction.RETAIN_CURRENT_TARGET),
        effective_target_seconds=65,
        prior_decision=(first_recalibrated_decision),
        rationale=("Retain the target for another cycle.",),
    )

    assert next_decision.prior_review_decision_id == ("RTRD_20260906_001_V1")
    assert next_decision.effective_target_seconds == 65


def build_proposal(
    target_values: tuple[int, ...] = (
        62,
        65,
        65,
        75,
        65,
        64,
        62,
        64,
        59,
        58,
        64,
        56,
    ),
    session_ids: tuple[str, ...] = (
        "SR_20260901_001_V2",
        "SR_20260901_001_V2",
        "SR_20260901_001_V2",
        "SR_20260901_001_V2",
        "SR_20260903_001_V2",
        "SR_20260903_001_V2",
        "SR_20260903_001_V2",
        "SR_20260903_001_V2",
        "SR_20260905_001_V2",
        "SR_20260905_001_V2",
        "SR_20260905_001_V2",
        "SR_20260905_001_V2",
    ),
) -> ProvisionalTargetProposal:
    if len(target_values) != len(session_ids):
        raise ValueError("Target values and session IDs must have equal lengths.")

    key = PaceObservationKey(
        exercise=ExerciseCode.FREESTYLE,
        distance_meters=50,
        equipment=(EquipmentCode.FINS,),
        intensity=IntensityCode.UNRESOLVED,
    )

    observations = tuple(
        PaceObservation(
            generated_workout_id=(f"GW_{session_id[3:11]}_001_V1"),
            session_result_id=session_id,
            block_sequence=4,
            set_group_sequence=1,
            item_sequence=1,
            repetition_number=index,
            key=key,
            actual_seconds=value,
        )
        for index, (value, session_id) in enumerate(
            zip(
                target_values,
                session_ids,
                strict=True,
            ),
            start=1,
        )
    )

    ordered_values = sorted(target_values)
    midpoint = len(ordered_values) // 2

    if len(ordered_values) % 2 == 0:
        median_seconds = (ordered_values[midpoint - 1] + ordered_values[midpoint]) / 2
    else:
        median_seconds = float(ordered_values[midpoint])

    summary = ProvisionalPaceSummary(
        key=key,
        sample_count=len(target_values),
        minimum_seconds=min(target_values),
        maximum_seconds=max(target_values),
        mean_seconds=(sum(target_values) / len(target_values)),
        median_seconds=median_seconds,
        observations=observations,
        limitations=("Synthetic test evidence.",),
    )

    return propose_target_for_review(assess_calibration_eligibility(summary))


def build_prior_decision() -> TargetReviewDecision:
    prior_proposal = build_proposal(
        target_values=(
            62,
            65,
            65,
            75,
            65,
            64,
            62,
            64,
        ),
        session_ids=(
            "SR_20260901_001_V2",
            "SR_20260901_001_V2",
            "SR_20260901_001_V2",
            "SR_20260901_001_V2",
            "SR_20260903_001_V2",
            "SR_20260903_001_V2",
            "SR_20260903_001_V2",
            "SR_20260903_001_V2",
        ),
    )

    return record_target_review_decision(
        prior_proposal,
        review_decision_id=("TRD_20260905_001_V1"),
        review_decision_version=1,
        decision=(TargetReviewDecisionType.ACCEPTED_FOR_FUTURE_WORKOUT),
        rationale=("Accepted for Pool Test 3.",),
    )


def test_accept_new_target_uses_recalibrated_proposal() -> None:
    proposal = build_proposal()
    decision = build_recalibrated_target_review_decision(
        proposal,
        review_decision_id="RTRD_20260906_001_V1",
        review_decision_version=1,
        action=RecalibratedTargetReviewAction.ACCEPT_NEW_TARGET,
        effective_target_seconds=proposal.proposed_target_seconds,
        rationale=("Accept the recalibrated target.",),
    )
    assert decision.may_be_applied_to_future_workout is True


def test_accept_new_rejects_different_effective_target() -> None:
    with pytest.raises(ValidationError, match="match the recalibrated proposal"):
        RecalibratedTargetReviewDecision(
            review_decision_id="RTRD_20260906_001_V1",
            review_decision_version=1,
            proposal=build_proposal(),
            action=RecalibratedTargetReviewAction.ACCEPT_NEW_TARGET,
            effective_target_seconds=65,
            rationale=("Invalid target.",),
            limitations=("Synthetic limitation.",),
        )


def test_retain_current_target_preserves_prior_target() -> None:
    decision = build_recalibrated_target_review_decision(
        build_proposal(),
        review_decision_id="RTRD_20260906_001_V1",
        review_decision_version=1,
        action=RecalibratedTargetReviewAction.RETAIN_CURRENT_TARGET,
        effective_target_seconds=65,
        prior_decision=build_prior_decision(),
        rationale=("Retain for one more targeted session.",),
    )
    assert decision.effective_target_seconds == 65
    assert decision.proposal.proposed_target_seconds == 64
    assert decision.prior_review_decision_id == "TRD_20260905_001_V1"


def test_retain_requires_prior_decision() -> None:
    with pytest.raises(ValueError, match="requires a prior"):
        build_recalibrated_target_review_decision(
            build_proposal(),
            review_decision_id="RTRD_20260906_001_V1",
            review_decision_version=1,
            action=RecalibratedTargetReviewAction.RETAIN_CURRENT_TARGET,
            effective_target_seconds=65,
            rationale=("Missing prior decision.",),
        )


@pytest.mark.parametrize(
    "action",
    (RecalibratedTargetReviewAction.DEFER, RecalibratedTargetReviewAction.REJECT),
)
def test_non_applicable_actions_require_null_target(action: RecalibratedTargetReviewAction) -> None:
    with pytest.raises(ValidationError, match="cannot define an effective target"):
        RecalibratedTargetReviewDecision(
            review_decision_id="RTRD_20260906_001_V1",
            review_decision_version=1,
            proposal=build_proposal(),
            action=action,
            effective_target_seconds=64,
            rationale=("Not applicable.",),
            limitations=("Synthetic limitation.",),
        )


def test_review_set_derives_exact_lineage() -> None:
    decision = build_recalibrated_target_review_decision(
        build_proposal(),
        review_decision_id="RTRD_20260906_001_V1",
        review_decision_version=1,
        action=RecalibratedTargetReviewAction.DEFER,
        rationale=("Defer.",),
    )
    review_set = build_recalibrated_target_review_set(
        review_set_id="RTRS_20260906_001_V1",
        review_set_version=1,
        decisions=(decision,),
    )
    assert review_set.source_session_result_ids == (
        "SR_20260901_001_V2",
        "SR_20260903_001_V2",
        "SR_20260905_001_V2",
    )


def test_duplicate_strict_keys_are_rejected() -> None:
    decision = build_recalibrated_target_review_decision(
        build_proposal(),
        review_decision_id="RTRD_20260906_001_V1",
        review_decision_version=1,
        action=RecalibratedTargetReviewAction.DEFER,
        rationale=("Defer.",),
    )
    second = decision.model_copy(update={"review_decision_id": "RTRD_20260906_002_V1"})
    with pytest.raises(ValidationError, match="duplicate strict keys"):
        RecalibratedTargetReviewSet(
            review_set_id="RTRS_20260906_001_V1",
            review_set_version=1,
            decisions=(decision, second),
            source_session_result_ids=decision.proposal.source_session_result_ids,
            limitations=("Synthetic limitation.",),
        )


def test_review_set_round_trips_and_is_immutable() -> None:
    decision = build_recalibrated_target_review_decision(
        build_proposal(),
        review_decision_id="RTRD_20260906_001_V1",
        review_decision_version=1,
        action=RecalibratedTargetReviewAction.DEFER,
        rationale=("Defer.",),
    )
    review_set = build_recalibrated_target_review_set(
        review_set_id="RTRS_20260906_001_V1",
        review_set_version=1,
        decisions=(decision,),
    )
    assert (
        RecalibratedTargetReviewSet.model_validate_json(review_set.model_dump_json()) == review_set
    )
    with pytest.raises(ValidationError):
        review_set.review_set_version = 2
