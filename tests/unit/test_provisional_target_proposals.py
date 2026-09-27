from __future__ import annotations

import pytest
from pydantic import ValidationError

from adaptive_swimming.domain.workout import (
    EquipmentCode,
    ExerciseCode,
    IntensityCode,
)
from adaptive_swimming.evaluation.calibration_eligibility import (
    CalibrationEligibilityAssessment,
    CalibrationEligibilityPolicy,
    CalibrationEligibilityStatus,
    assess_calibration_eligibility,
)
from adaptive_swimming.evaluation.pace_calibration import (
    PaceObservation,
    PaceObservationKey,
    ProvisionalPaceSummary,
)
from adaptive_swimming.planning.provisional_target_proposals import (
    ProvisionalTargetProposal,
    ProvisionalTargetProposalStatus,
    propose_eligible_targets_for_review,
    propose_target_for_review,
    round_half_up,
)


def build_summary(
    values: tuple[int, ...] = (62, 65, 65, 75, 65, 64, 62, 64),
    session_ids: tuple[str, ...] = (
        "SR_20260901_001_V2",
        "SR_20260901_001_V2",
        "SR_20260901_001_V2",
        "SR_20260901_001_V2",
        "SR_20260903_001_V2",
        "SR_20260903_001_V2",
        "SR_20260903_001_V2",
        "SR_20260903_001_V2",
    ),
) -> ProvisionalPaceSummary:
    key = PaceObservationKey(
        exercise=ExerciseCode.FREESTYLE,
        distance_meters=50,
        equipment=(EquipmentCode.FINS,),
        intensity=IntensityCode.UNRESOLVED,
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
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    median_value = (ordered[midpoint - 1] + ordered[midpoint]) / 2

    return ProvisionalPaceSummary(
        key=key,
        sample_count=len(values),
        minimum_seconds=min(values),
        maximum_seconds=max(values),
        mean_seconds=sum(values) / len(values),
        median_seconds=median_value,
        observations=observations,
        limitations=("Synthetic test summary.",),
    )


def eligible_assessment() -> CalibrationEligibilityAssessment:
    return assess_calibration_eligibility(build_summary())


def test_round_half_up_uses_explicit_policy() -> None:
    assert round_half_up(64.5) == 65
    assert round_half_up(64.4) == 64


def test_round_half_up_rejects_nonpositive_values() -> None:
    with pytest.raises(ValueError, match="positive"):
        round_half_up(0)


def test_eligible_summary_proposes_rounded_median() -> None:
    proposal = propose_target_for_review(eligible_assessment())
    assert proposal.proposed_target_seconds == 65
    assert proposal.observed_median_seconds == 64.5


def test_proposal_preserves_observed_statistics() -> None:
    proposal = propose_target_for_review(eligible_assessment())
    assert proposal.observed_minimum_seconds == 62
    assert proposal.observed_maximum_seconds == 75
    assert proposal.observed_mean_seconds == pytest.approx(65.25)


def test_proposal_preserves_evidence_counts() -> None:
    proposal = propose_target_for_review(eligible_assessment())
    assert proposal.evidence_session_count == 2
    assert proposal.evidence_sample_count == 8


def test_proposal_preserves_distinct_sorted_source_ids() -> None:
    proposal = propose_target_for_review(eligible_assessment())
    assert proposal.source_session_result_ids == (
        "SR_20260901_001_V2",
        "SR_20260903_001_V2",
    )


def test_proposal_is_proposed_and_requires_review() -> None:
    proposal = propose_target_for_review(eligible_assessment())
    assert proposal.status == ProvisionalTargetProposalStatus.PROPOSED
    assert any("human review" in value for value in proposal.limitations)
    assert any("does not modify" in value for value in proposal.limitations)


def test_ineligible_assessment_is_rejected() -> None:
    assessment = assess_calibration_eligibility(
        build_summary(
            values=(62, 65, 64),
            session_ids=("SR_20260901_001_V2",) * 3,
        )
    )
    assert assessment.status == CalibrationEligibilityStatus.INSUFFICIENT_SESSIONS
    with pytest.raises(ValueError, match="ELIGIBLE_FOR_REVIEW"):
        propose_target_for_review(assessment)


def test_custom_ineligible_policy_is_respected() -> None:
    assessment = assess_calibration_eligibility(
        build_summary(),
        CalibrationEligibilityPolicy(
            minimum_session_count=3,
            minimum_sample_count=8,
        ),
    )
    with pytest.raises(ValueError, match="ELIGIBLE_FOR_REVIEW"):
        propose_target_for_review(assessment)


def test_batch_proposes_only_eligible_assessments() -> None:
    eligible = eligible_assessment()
    ineligible = assess_calibration_eligibility(
        build_summary(
            values=(62, 65, 64),
            session_ids=("SR_20260901_001_V2",) * 3,
        )
    )
    proposals = propose_eligible_targets_for_review((ineligible, eligible))
    assert len(proposals) == 1
    assert proposals[0].key == eligible.summary.key


def test_candidate_must_remain_within_observed_range() -> None:
    proposal = propose_target_for_review(eligible_assessment())
    payload = proposal.model_dump()
    payload["proposed_target_seconds"] = 90
    with pytest.raises(ValidationError, match="within the observed range"):
        ProvisionalTargetProposal.model_validate(payload)


def test_invalid_observed_range_is_rejected() -> None:
    proposal = propose_target_for_review(eligible_assessment())
    payload = proposal.model_dump()
    payload["observed_minimum_seconds"] = 80
    with pytest.raises(ValidationError, match="minimum cannot exceed"):
        ProvisionalTargetProposal.model_validate(payload)


def test_proposal_round_trips_through_json() -> None:
    proposal = propose_target_for_review(eligible_assessment())
    loaded = ProvisionalTargetProposal.model_validate_json(proposal.model_dump_json())
    assert loaded == proposal


def test_proposal_is_immutable() -> None:
    proposal = propose_target_for_review(eligible_assessment())
    with pytest.raises(ValidationError):
        proposal.proposed_target_seconds = 70


def test_proposal_does_not_modify_assessment_or_summary() -> None:
    assessment = eligible_assessment()
    before = assessment.model_dump_json()
    propose_target_for_review(assessment)
    assert assessment.model_dump_json() == before
