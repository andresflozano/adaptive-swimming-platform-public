from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from adaptive_swimming.domain.workout import StrictDomainModel
from adaptive_swimming.evaluation.pace_calibration import ProvisionalPaceSummary


class CalibrationEligibilityStatus(StrEnum):
    ELIGIBLE_FOR_REVIEW = "ELIGIBLE_FOR_REVIEW"
    INSUFFICIENT_SESSIONS = "INSUFFICIENT_SESSIONS"
    INSUFFICIENT_SAMPLES = "INSUFFICIENT_SAMPLES"
    SINGLE_OBSERVATION_ONLY = "SINGLE_OBSERVATION_ONLY"


class CalibrationEligibilityPolicy(StrictDomainModel):
    minimum_session_count: int = Field(default=2, ge=1)
    minimum_sample_count: int = Field(default=4, ge=1)


class CalibrationEligibilityAssessment(StrictDomainModel):
    summary: ProvisionalPaceSummary
    status: CalibrationEligibilityStatus
    session_count: int = Field(ge=1)
    sample_count: int = Field(ge=1)
    required_session_count: int = Field(ge=1)
    required_sample_count: int = Field(ge=1)
    eligible_for_review: bool
    reasons: tuple[str, ...] = Field(min_length=1)


def assess_calibration_eligibility(
    summary: ProvisionalPaceSummary,
    policy: CalibrationEligibilityPolicy | None = None,
) -> CalibrationEligibilityAssessment:
    effective_policy = policy if policy is not None else CalibrationEligibilityPolicy()
    session_count = len({observation.session_result_id for observation in summary.observations})

    reasons: tuple[str, ...]

    if summary.sample_count == 1:
        status = CalibrationEligibilityStatus.SINGLE_OBSERVATION_ONLY
        reasons = ("The strict pace group contains only one observation.",)
    elif session_count < effective_policy.minimum_session_count:
        status = CalibrationEligibilityStatus.INSUFFICIENT_SESSIONS
        reasons = ("The strict pace group does not meet the minimum completed-session count.",)
    elif summary.sample_count < effective_policy.minimum_sample_count:
        status = CalibrationEligibilityStatus.INSUFFICIENT_SAMPLES
        reasons = ("The strict pace group does not meet the minimum observation count.",)
    else:
        status = CalibrationEligibilityStatus.ELIGIBLE_FOR_REVIEW
        reasons = (
            "The strict pace group meets the configured evidence thresholds.",
            "Eligibility permits human review but does not create a mandatory target.",
        )

    eligible = status == CalibrationEligibilityStatus.ELIGIBLE_FOR_REVIEW

    return CalibrationEligibilityAssessment(
        summary=summary,
        status=status,
        session_count=session_count,
        sample_count=summary.sample_count,
        required_session_count=effective_policy.minimum_session_count,
        required_sample_count=effective_policy.minimum_sample_count,
        eligible_for_review=eligible,
        reasons=reasons,
    )


def assess_calibration_summaries(
    summaries: tuple[ProvisionalPaceSummary, ...],
    policy: CalibrationEligibilityPolicy | None = None,
) -> tuple[CalibrationEligibilityAssessment, ...]:
    effective_policy = policy if policy is not None else CalibrationEligibilityPolicy()

    return tuple(
        assess_calibration_eligibility(
            summary,
            effective_policy,
        )
        for summary in summaries
    )
