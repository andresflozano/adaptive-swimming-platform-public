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
    assess_calibration_summaries,
)
from adaptive_swimming.evaluation.pace_calibration import (
    PaceObservation,
    PaceObservationKey,
    ProvisionalPaceSummary,
)


def build_summary(
    *,
    sample_count: int,
    session_ids: tuple[str, ...],
) -> ProvisionalPaceSummary:
    if len(session_ids) != sample_count:
        raise ValueError("session_ids must match sample_count")

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
            actual_seconds=60 + index,
        )
        for index, session_id in enumerate(session_ids, start=1)
    )
    values = tuple(item.actual_seconds for item in observations)

    return ProvisionalPaceSummary(
        key=key,
        sample_count=sample_count,
        minimum_seconds=min(values),
        maximum_seconds=max(values),
        mean_seconds=sum(values) / len(values),
        median_seconds=float(sorted(values)[len(values) // 2]),
        observations=observations,
        provisional=True,
        limitations=("Synthetic test summary.",),
    )


def test_default_policy_requires_two_sessions_and_four_samples() -> None:
    policy = CalibrationEligibilityPolicy()
    assert policy.minimum_session_count == 2
    assert policy.minimum_sample_count == 4


def test_policy_rejects_zero_thresholds() -> None:
    with pytest.raises(ValidationError):
        CalibrationEligibilityPolicy(minimum_session_count=0)
    with pytest.raises(ValidationError):
        CalibrationEligibilityPolicy(minimum_sample_count=0)


def test_single_observation_has_specific_status() -> None:
    assessment = assess_calibration_eligibility(
        build_summary(
            sample_count=1,
            session_ids=("SR_20260901_001_V2",),
        )
    )
    assert assessment.status == CalibrationEligibilityStatus.SINGLE_OBSERVATION_ONLY
    assert assessment.eligible_for_review is False


def test_multiple_samples_from_one_session_are_insufficient_sessions() -> None:
    assessment = assess_calibration_eligibility(
        build_summary(
            sample_count=5,
            session_ids=("SR_20260901_001_V2",) * 5,
        )
    )
    assert assessment.session_count == 1
    assert assessment.status == CalibrationEligibilityStatus.INSUFFICIENT_SESSIONS


def test_two_sessions_but_too_few_samples_are_insufficient_samples() -> None:
    assessment = assess_calibration_eligibility(
        build_summary(
            sample_count=2,
            session_ids=(
                "SR_20260901_001_V2",
                "SR_20260903_001_V2",
            ),
        )
    )
    assert assessment.session_count == 2
    assert assessment.status == CalibrationEligibilityStatus.INSUFFICIENT_SAMPLES


def test_group_meeting_both_thresholds_is_eligible_for_review() -> None:
    assessment = assess_calibration_eligibility(
        build_summary(
            sample_count=4,
            session_ids=(
                "SR_20260901_001_V2",
                "SR_20260901_001_V2",
                "SR_20260903_001_V2",
                "SR_20260903_001_V2",
            ),
        )
    )
    assert assessment.status == CalibrationEligibilityStatus.ELIGIBLE_FOR_REVIEW
    assert assessment.eligible_for_review is True


def test_duplicate_observations_do_not_inflate_session_count() -> None:
    assessment = assess_calibration_eligibility(
        build_summary(
            sample_count=4,
            session_ids=("SR_20260901_001_V2",) * 4,
        )
    )
    assert assessment.session_count == 1


def test_custom_policy_is_applied() -> None:
    assessment = assess_calibration_eligibility(
        build_summary(
            sample_count=4,
            session_ids=(
                "SR_20260901_001_V2",
                "SR_20260901_001_V2",
                "SR_20260903_001_V2",
                "SR_20260903_001_V2",
            ),
        ),
        CalibrationEligibilityPolicy(
            minimum_session_count=3,
            minimum_sample_count=6,
        ),
    )
    assert assessment.status == CalibrationEligibilityStatus.INSUFFICIENT_SESSIONS
    assert assessment.required_session_count == 3
    assert assessment.required_sample_count == 6


def test_eligibility_does_not_change_provisional_summary() -> None:
    summary = build_summary(
        sample_count=4,
        session_ids=(
            "SR_20260901_001_V2",
            "SR_20260901_001_V2",
            "SR_20260903_001_V2",
            "SR_20260903_001_V2",
        ),
    )
    before = summary.model_dump_json()
    assessment = assess_calibration_eligibility(summary)
    assert summary.model_dump_json() == before
    assert assessment.summary == summary
    assert assessment.summary.provisional is True


def test_eligible_reason_does_not_claim_target_creation() -> None:
    assessment = assess_calibration_eligibility(
        build_summary(
            sample_count=4,
            session_ids=(
                "SR_20260901_001_V2",
                "SR_20260901_001_V2",
                "SR_20260903_001_V2",
                "SR_20260903_001_V2",
            ),
        )
    )
    assert any("does not create a mandatory target" in reason for reason in assessment.reasons)


def test_assessment_round_trips_through_json() -> None:
    assessment = assess_calibration_eligibility(
        build_summary(
            sample_count=4,
            session_ids=(
                "SR_20260901_001_V2",
                "SR_20260901_001_V2",
                "SR_20260903_001_V2",
                "SR_20260903_001_V2",
            ),
        )
    )
    loaded = CalibrationEligibilityAssessment.model_validate_json(assessment.model_dump_json())
    assert loaded == assessment


def test_assessment_is_immutable() -> None:
    assessment = assess_calibration_eligibility(
        build_summary(
            sample_count=1,
            session_ids=("SR_20260901_001_V2",),
        )
    )
    with pytest.raises(ValidationError):
        assessment.eligible_for_review = True


def test_assess_summaries_preserves_input_order() -> None:
    first = build_summary(
        sample_count=1,
        session_ids=("SR_20260901_001_V2",),
    )
    second = build_summary(
        sample_count=4,
        session_ids=(
            "SR_20260901_001_V2",
            "SR_20260901_001_V2",
            "SR_20260903_001_V2",
            "SR_20260903_001_V2",
        ),
    )
    assessments = assess_calibration_summaries((first, second))
    assert [assessment.summary for assessment in assessments] == [first, second]


def test_empty_summaries_return_no_assessments() -> None:
    assert assess_calibration_summaries(()) == ()
