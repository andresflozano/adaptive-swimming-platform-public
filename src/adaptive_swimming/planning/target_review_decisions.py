from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from adaptive_swimming.domain.workout import StrictDomainModel
from adaptive_swimming.planning.provisional_target_proposals import (
    ProvisionalTargetProposal,
    ProvisionalTargetProposalStatus,
)


class TargetReviewDecisionType(StrEnum):
    ACCEPTED_FOR_FUTURE_WORKOUT = "ACCEPTED_FOR_FUTURE_WORKOUT"
    DEFERRED = "DEFERRED"
    REJECTED = "REJECTED"


class TargetReviewDecision(StrictDomainModel):
    review_decision_id: str = Field(pattern=r"^TRD_[0-9]{8}_[0-9]{3}_V[0-9]+$")
    review_decision_version: int = Field(ge=1)
    proposal: ProvisionalTargetProposal
    decision: TargetReviewDecisionType
    reviewed_target_seconds: int = Field(gt=0)
    rationale: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_reviewed_target(self) -> TargetReviewDecision:
        if self.proposal.status != ProvisionalTargetProposalStatus.PROPOSED:
            raise ValueError("Only a proposed target can be reviewed.")

        if self.reviewed_target_seconds != self.proposal.proposed_target_seconds:
            raise ValueError("A review decision cannot silently change the proposed target.")

        version_text = self.review_decision_id.rsplit(
            "_V",
            maxsplit=1,
        )[1]

        if int(version_text) != self.review_decision_version:
            raise ValueError("Review decision ID version must match review_decision_version.")

        return self

    @property
    def may_be_applied_to_future_workout(self) -> bool:
        return self.decision == TargetReviewDecisionType.ACCEPTED_FOR_FUTURE_WORKOUT


def record_target_review_decision(
    proposal: ProvisionalTargetProposal,
    *,
    review_decision_id: str,
    review_decision_version: int,
    decision: TargetReviewDecisionType,
    rationale: tuple[str, ...],
) -> TargetReviewDecision:
    if not rationale:
        raise ValueError("A target review decision requires rationale.")

    limitations: tuple[str, ...]

    if decision == TargetReviewDecisionType.ACCEPTED_FOR_FUTURE_WORKOUT:
        limitations = (
            ("Acceptance permits later workout application but does not modify a workout."),
            ("The accepted value remains provisional until evaluated in a completed session."),
        )
    elif decision == TargetReviewDecisionType.DEFERRED:
        limitations = (
            ("The proposal remains unapplied while additional evidence or context is gathered."),
        )
    else:
        limitations = (("The rejected proposal must not be applied to a workout."),)

    return TargetReviewDecision(
        review_decision_id=review_decision_id,
        review_decision_version=review_decision_version,
        proposal=proposal,
        decision=decision,
        reviewed_target_seconds=(proposal.proposed_target_seconds),
        rationale=rationale,
        limitations=limitations,
    )
