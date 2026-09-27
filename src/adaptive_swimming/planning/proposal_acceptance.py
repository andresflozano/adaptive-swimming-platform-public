from __future__ import annotations

from pydantic import Field, model_validator

from adaptive_swimming.domain.session_results import (
    CompletionStatus,
    WorkoutSessionResult,
)
from adaptive_swimming.domain.workout import StrictDomainModel
from adaptive_swimming.planning.workout_proposal import (
    NextWorkoutProposal,
    ProposalStatus,
)


class ProposalAcceptance(StrictDomainModel):
    acceptance_id: str = Field(pattern=r"^NWA_[0-9]{8}_[0-9]{3}_V[0-9]+$")
    acceptance_version: int = Field(ge=1)
    proposal_id: str = Field(pattern=r"^NWP_[0-9]{8}_[0-9]{3}_V[0-9]+$")
    accepted_generated_workout_id: str = Field(pattern=r"^GW_[0-9]{8}_[0-9]{3}_V[0-9]+$")
    accepted: bool = True
    notes: str | None = None

    @model_validator(mode="after")
    def validate_acceptance(self) -> ProposalAcceptance:
        version_text = self.acceptance_id.rsplit(
            "_V",
            maxsplit=1,
        )[1]

        if int(version_text) != self.acceptance_version:
            raise ValueError("Acceptance ID version must match acceptance_version.")

        if not self.accepted:
            raise ValueError("Proposal acceptance records must be accepted.")

        return self


def build_proposal_acceptance(
    proposal: NextWorkoutProposal,
    *,
    notes: str = ("Accepted after swimmer review of the workout presentation."),
) -> ProposalAcceptance:
    if proposal.status != ProposalStatus.PROPOSED:
        raise ValueError("Only a proposed workout can be accepted.")

    identifier_body = proposal.proposal_id.removeprefix("NWP_")
    acceptance_id = f"NWA_{identifier_body}"

    return ProposalAcceptance(
        acceptance_id=acceptance_id,
        acceptance_version=proposal.proposal_version,
        proposal_id=proposal.proposal_id,
        accepted_generated_workout_id=(proposal.proposed_generated_workout.generated_workout_id),
        accepted=True,
        notes=notes,
    )


def build_not_started_result(
    proposal: NextWorkoutProposal,
) -> WorkoutSessionResult:
    generated_workout = proposal.proposed_generated_workout

    identifier_body = generated_workout.generated_workout_id.removeprefix("GW_")
    session_result_id = f"SR_{identifier_body}"

    return WorkoutSessionResult(
        session_result_id=session_result_id,
        generated_workout_id=(generated_workout.generated_workout_id),
        result_version=generated_workout.workout_version,
        completion_status=CompletionStatus.NOT_STARTED,
        completed_distance_meters=0,
        actual_total_seconds=None,
        perceived_exertion=None,
        equipment_used=(),
        block_results=(),
        safety_issue_reported=False,
        notes=None,
    )
