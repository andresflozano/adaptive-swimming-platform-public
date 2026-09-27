from __future__ import annotations

import math
from enum import StrEnum

from pydantic import Field, model_validator

from adaptive_swimming.domain.workout import StrictDomainModel
from adaptive_swimming.evaluation.calibration_eligibility import (
    CalibrationEligibilityAssessment,
    CalibrationEligibilityStatus,
)
from adaptive_swimming.evaluation.pace_calibration import PaceObservationKey


class ProvisionalTargetProposalStatus(StrEnum):
    PROPOSED = "PROPOSED"


class ProvisionalTargetProposal(StrictDomainModel):
    key: PaceObservationKey
    status: ProvisionalTargetProposalStatus = ProvisionalTargetProposalStatus.PROPOSED
    proposed_target_seconds: int = Field(gt=0)
    observed_minimum_seconds: int = Field(gt=0)
    observed_maximum_seconds: int = Field(gt=0)
    observed_mean_seconds: float = Field(gt=0)
    observed_median_seconds: float = Field(gt=0)
    evidence_session_count: int = Field(ge=1)
    evidence_sample_count: int = Field(ge=1)
    source_session_result_ids: tuple[str, ...] = Field(min_length=1)
    rationale: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_observed_range(self) -> ProvisionalTargetProposal:
        if self.observed_minimum_seconds > self.observed_maximum_seconds:
            raise ValueError("Observed minimum cannot exceed observed maximum.")

        if not (
            self.observed_minimum_seconds
            <= self.proposed_target_seconds
            <= self.observed_maximum_seconds
        ):
            raise ValueError("Proposed target must remain within the observed range.")

        return self


def round_half_up(value: float) -> int:
    if value <= 0:
        raise ValueError("Target values must be positive.")

    return math.floor(value + 0.5)


def propose_target_for_review(
    assessment: CalibrationEligibilityAssessment,
) -> ProvisionalTargetProposal:
    if assessment.status != CalibrationEligibilityStatus.ELIGIBLE_FOR_REVIEW:
        raise ValueError("A target proposal requires an ELIGIBLE_FOR_REVIEW assessment.")

    summary = assessment.summary
    source_session_result_ids = tuple(
        sorted({observation.session_result_id for observation in summary.observations})
    )

    return ProvisionalTargetProposal(
        key=summary.key,
        proposed_target_seconds=round_half_up(summary.median_seconds),
        observed_minimum_seconds=summary.minimum_seconds,
        observed_maximum_seconds=summary.maximum_seconds,
        observed_mean_seconds=summary.mean_seconds,
        observed_median_seconds=summary.median_seconds,
        evidence_session_count=assessment.session_count,
        evidence_sample_count=assessment.sample_count,
        source_session_result_ids=source_session_result_ids,
        rationale=(
            "The candidate uses the rounded observed median as a review anchor.",
            "The candidate remains within the observed strict-group range.",
        ),
        limitations=(
            "The proposal is provisional and requires human review.",
            "The proposal does not modify or approve a workout target.",
            "The evidence thresholds are policy defaults, not validated training-science rules.",
            "Session structure, preceding workload, and fatigue may affect observed pace.",
        ),
    )


def propose_eligible_targets_for_review(
    assessments: tuple[CalibrationEligibilityAssessment, ...],
) -> tuple[ProvisionalTargetProposal, ...]:
    return tuple(
        propose_target_for_review(assessment)
        for assessment in assessments
        if (assessment.status == CalibrationEligibilityStatus.ELIGIBLE_FOR_REVIEW)
    )
