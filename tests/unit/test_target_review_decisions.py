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
from adaptive_swimming.planning.target_review_decisions import (
    TargetReviewDecision,
    TargetReviewDecisionType,
    record_target_review_decision,
)

REVIEW_DECISION_ID = "TRD_20260905_001_V1"
REVIEW_DECISION_VERSION = 1


def build_proposal() -> ProvisionalTargetProposal:
    key = PaceObservationKey(
        exercise=ExerciseCode.FREESTYLE,
        distance_meters=50,
        equipment=(EquipmentCode.FINS,),
        intensity=IntensityCode.UNRESOLVED,
    )
    values = (62, 65, 65, 75, 65, 64, 62, 64)
    session_ids = (
        "SR_20260901_001_V2",
        "SR_20260901_001_V2",
        "SR_20260901_001_V2",
        "SR_20260901_001_V2",
        "SR_20260903_001_V2",
        "SR_20260903_001_V2",
        "SR_20260903_001_V2",
        "SR_20260903_001_V2",
    )
    observations = tuple(
        PaceObservation(
            generated_workout_id=(
                "GW_20260901_001_V1" if session_id == "SR_20260901_001_V2" else "GW_20260903_001_V1"
            ),
            session_result_id=session_id,
            block_sequence=4,
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
    summary = ProvisionalPaceSummary(
        key=key,
        sample_count=8,
        minimum_seconds=62,
        maximum_seconds=75,
        mean_seconds=65.25,
        median_seconds=64.5,
        observations=observations,
        limitations=("Synthetic test summary.",),
    )
    return propose_target_for_review(assess_calibration_eligibility(summary))


def record_decision(
    decision: TargetReviewDecisionType,
    rationale: tuple[str, ...],
) -> TargetReviewDecision:
    return record_target_review_decision(
        build_proposal(),
        review_decision_id=REVIEW_DECISION_ID,
        review_decision_version=REVIEW_DECISION_VERSION,
        decision=decision,
        rationale=rationale,
    )


def test_acceptance_allows_future_application_only() -> None:
    decision = record_decision(
        TargetReviewDecisionType.ACCEPTED_FOR_FUTURE_WORKOUT,
        ("Review anchor accepted for a controlled future test.",),
    )

    assert decision.review_decision_id == REVIEW_DECISION_ID
    assert decision.review_decision_version == REVIEW_DECISION_VERSION
    assert decision.may_be_applied_to_future_workout is True
    assert decision.reviewed_target_seconds == 65


def test_deferred_decision_is_not_applicable() -> None:
    decision = record_decision(
        TargetReviewDecisionType.DEFERRED,
        ("Preparation target deferred pending further review.",),
    )

    assert decision.may_be_applied_to_future_workout is False


def test_rejected_decision_is_not_applicable() -> None:
    decision = record_decision(
        TargetReviewDecisionType.REJECTED,
        ("Proposal rejected for the intended workout role.",),
    )

    assert decision.may_be_applied_to_future_workout is False


def test_empty_rationale_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires rationale"):
        record_target_review_decision(
            build_proposal(),
            review_decision_id=REVIEW_DECISION_ID,
            review_decision_version=REVIEW_DECISION_VERSION,
            decision=TargetReviewDecisionType.DEFERRED,
            rationale=(),
        )


def test_review_cannot_silently_change_target() -> None:
    proposal = build_proposal()

    with pytest.raises(
        ValidationError,
        match="cannot silently change",
    ):
        TargetReviewDecision(
            review_decision_id=REVIEW_DECISION_ID,
            review_decision_version=REVIEW_DECISION_VERSION,
            proposal=proposal,
            decision=(TargetReviewDecisionType.ACCEPTED_FOR_FUTURE_WORKOUT),
            reviewed_target_seconds=66,
            rationale=("Changed without a new proposal.",),
            limitations=("Synthetic limitation.",),
        )


def test_review_decision_rejects_mismatched_version() -> None:
    proposal = build_proposal()

    with pytest.raises(
        ValidationError,
        match="ID version must match",
    ):
        TargetReviewDecision(
            review_decision_id="TRD_20260905_001_V2",
            review_decision_version=1,
            proposal=proposal,
            decision=TargetReviewDecisionType.DEFERRED,
            reviewed_target_seconds=(proposal.proposed_target_seconds),
            rationale=("Synthetic review decision.",),
            limitations=("Synthetic limitation.",),
        )


def test_acceptance_does_not_modify_proposal() -> None:
    proposal = build_proposal()
    before = proposal.model_dump_json()

    record_target_review_decision(
        proposal,
        review_decision_id=REVIEW_DECISION_ID,
        review_decision_version=REVIEW_DECISION_VERSION,
        decision=(TargetReviewDecisionType.ACCEPTED_FOR_FUTURE_WORKOUT),
        rationale=("Review anchor accepted for a controlled future test.",),
    )

    assert proposal.model_dump_json() == before


def test_decision_round_trips_through_json() -> None:
    decision = record_decision(
        TargetReviewDecisionType.DEFERRED,
        ("Deferred for additional evidence.",),
    )

    loaded = TargetReviewDecision.model_validate_json(decision.model_dump_json())

    assert loaded == decision
    assert loaded.review_decision_id == REVIEW_DECISION_ID
    assert loaded.review_decision_version == REVIEW_DECISION_VERSION


def test_decision_is_immutable() -> None:
    decision = record_decision(
        TargetReviewDecisionType.DEFERRED,
        ("Deferred for additional evidence.",),
    )

    with pytest.raises(ValidationError):
        decision.reviewed_target_seconds = 70
