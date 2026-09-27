from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from adaptive_swimming.domain.workout import StrictDomainModel
from adaptive_swimming.planning.provisional_target_proposals import (
    ProvisionalTargetProposal,
    ProvisionalTargetProposalStatus,
)
from adaptive_swimming.planning.target_review_decisions import (
    TargetReviewDecision,
)


class RecalibratedTargetReviewAction(StrEnum):
    ACCEPT_NEW_TARGET = "ACCEPT_NEW_TARGET"
    RETAIN_CURRENT_TARGET = "RETAIN_CURRENT_TARGET"
    DEFER = "DEFER"
    REJECT = "REJECT"


class RecalibratedTargetReviewDecision(StrictDomainModel):
    review_decision_id: str = Field(pattern=r"^RTRD_[0-9]{8}_[0-9]{3}_V[0-9]+$")
    review_decision_version: int = Field(ge=1)
    proposal: ProvisionalTargetProposal
    action: RecalibratedTargetReviewAction
    effective_target_seconds: int | None = Field(default=None, gt=0)
    prior_review_decision_id: str | None = Field(
        default=None,
        pattern=(r"^(?:TRD|RTRD)_[0-9]{8}_[0-9]{3}_V[0-9]+$"),
    )
    rationale: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_decision(self) -> RecalibratedTargetReviewDecision:
        if self.proposal.status != ProvisionalTargetProposalStatus.PROPOSED:
            raise ValueError("Only a proposed recalibrated target can be reviewed.")

        version_text = self.review_decision_id.rsplit("_V", maxsplit=1)[1]
        if int(version_text) != self.review_decision_version:
            raise ValueError("Recalibrated decision ID version must match review_decision_version.")

        if self.action == RecalibratedTargetReviewAction.ACCEPT_NEW_TARGET:
            if self.effective_target_seconds != self.proposal.proposed_target_seconds:
                raise ValueError(
                    "Accepting a new target requires the effective target to "
                    "match the recalibrated proposal."
                )
        elif self.action == RecalibratedTargetReviewAction.RETAIN_CURRENT_TARGET:
            if self.prior_review_decision_id is None:
                raise ValueError("Retaining a current target requires a prior review decision.")
            if self.effective_target_seconds is None:
                raise ValueError("Retaining a current target requires an effective target.")
        elif self.effective_target_seconds is not None:
            raise ValueError("Deferred and rejected proposals cannot define an effective target.")

        return self

    @property
    def may_be_applied_to_future_workout(self) -> bool:
        return self.action in {
            RecalibratedTargetReviewAction.ACCEPT_NEW_TARGET,
            RecalibratedTargetReviewAction.RETAIN_CURRENT_TARGET,
        }


PriorTargetReviewDecision = TargetReviewDecision | RecalibratedTargetReviewDecision


class RecalibratedTargetReviewSet(StrictDomainModel):
    review_set_id: str = Field(pattern=r"^RTRS_[0-9]{8}_[0-9]{3}_V[0-9]+$")
    review_set_version: int = Field(ge=1)
    decisions: tuple[RecalibratedTargetReviewDecision, ...] = Field(min_length=1)
    source_session_result_ids: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_review_set(self) -> RecalibratedTargetReviewSet:
        version_text = self.review_set_id.rsplit("_V", maxsplit=1)[1]
        if int(version_text) != self.review_set_version:
            raise ValueError("Recalibrated review-set ID version must match review_set_version.")

        decision_ids = tuple(decision.review_decision_id for decision in self.decisions)
        if len(decision_ids) != len(set(decision_ids)):
            raise ValueError("Recalibrated decision IDs must be unique within a set.")

        keys = tuple(decision.proposal.key for decision in self.decisions)
        serialized_keys = tuple(key.model_dump_json() for key in keys)
        if len(serialized_keys) != len(set(serialized_keys)):
            raise ValueError("A recalibrated review set cannot contain duplicate strict keys.")

        expected_source_ids = tuple(
            sorted(
                {
                    result_id
                    for decision in self.decisions
                    for result_id in decision.proposal.source_session_result_ids
                }
            )
        )
        if self.source_session_result_ids != expected_source_ids:
            raise ValueError(
                "Review-set source session-result IDs must exactly match "
                "the embedded proposal evidence."
            )

        return self


def applicable_target_seconds(
    decision: PriorTargetReviewDecision,
) -> int:
    if not decision.may_be_applied_to_future_workout:
        raise ValueError("A retained target requires an applicable prior decision.")

    if isinstance(
        decision,
        RecalibratedTargetReviewDecision,
    ):
        if decision.effective_target_seconds is None:
            raise ValueError("Applicable recalibrated decisions must define an effective target.")

        return decision.effective_target_seconds

    return decision.reviewed_target_seconds


def build_recalibrated_target_review_decision(
    proposal: ProvisionalTargetProposal,
    *,
    review_decision_id: str,
    review_decision_version: int,
    action: RecalibratedTargetReviewAction,
    rationale: tuple[str, ...],
    effective_target_seconds: int | None = None,
    prior_decision: PriorTargetReviewDecision | None = None,
) -> RecalibratedTargetReviewDecision:
    if not rationale:
        raise ValueError("A recalibrated target review requires rationale.")

    if prior_decision is not None and prior_decision.proposal.key != proposal.key:
        raise ValueError("Prior review decision strict key must match the recalibrated proposal.")

    prior_review_decision_id = (
        prior_decision.review_decision_id if prior_decision is not None else None
    )

    if action == RecalibratedTargetReviewAction.RETAIN_CURRENT_TARGET:
        if prior_decision is None:
            raise ValueError("Retaining a current target requires a prior review decision.")
        prior_target_seconds = applicable_target_seconds(prior_decision)

        if effective_target_seconds != prior_target_seconds:
            raise ValueError("Retained effective target must match the prior effective target.")

    limitations: tuple[str, ...]
    if action == RecalibratedTargetReviewAction.ACCEPT_NEW_TARGET:
        limitations = (
            "The accepted recalibrated target remains provisional until evaluated.",
            "This decision does not modify a workout.",
        )
    elif action == RecalibratedTargetReviewAction.RETAIN_CURRENT_TARGET:
        limitations = (
            "The new recalibrated proposal is not applied.",
            "The prior target remains provisional and requires future evaluation.",
        )
    elif action == RecalibratedTargetReviewAction.DEFER:
        limitations = ("The recalibrated proposal remains unapplied pending further review.",)
    else:
        limitations = ("The rejected recalibrated proposal must not be applied to a workout.",)

    return RecalibratedTargetReviewDecision(
        review_decision_id=review_decision_id,
        review_decision_version=review_decision_version,
        proposal=proposal,
        action=action,
        effective_target_seconds=effective_target_seconds,
        prior_review_decision_id=prior_review_decision_id,
        rationale=rationale,
        limitations=limitations,
    )


def build_recalibrated_target_review_set(
    *,
    review_set_id: str,
    review_set_version: int,
    decisions: tuple[RecalibratedTargetReviewDecision, ...],
) -> RecalibratedTargetReviewSet:
    source_session_result_ids = tuple(
        sorted(
            {
                result_id
                for decision in decisions
                for result_id in decision.proposal.source_session_result_ids
            }
        )
    )
    return RecalibratedTargetReviewSet(
        review_set_id=review_set_id,
        review_set_version=review_set_version,
        decisions=decisions,
        source_session_result_ids=source_session_result_ids,
        limitations=(
            "The reviewed set records decisions but applies no workout targets.",
            "Eligibility and rounded medians do not establish target suitability.",
        ),
    )
