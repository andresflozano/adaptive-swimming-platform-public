from __future__ import annotations

import re
from pathlib import Path

from adaptive_swimming.persistence.session_records import (
    PROPOSAL_ACCEPTANCES_DIRECTORY,
    PROPOSALS_DIRECTORY,
    write_new_json_record,
)
from adaptive_swimming.planning.proposal_acceptance import (
    ProposalAcceptance,
)
from adaptive_swimming.planning.workout_proposal import (
    NextWorkoutProposal,
)

PROPOSAL_ID_PATTERN = re.compile(r"^NWP_[0-9]{8}_[0-9]{3}_V[0-9]+$")
PROPOSAL_ACCEPTANCE_ID_PATTERN = re.compile(r"^NWA_[0-9]{8}_[0-9]{3}_V[0-9]+$")


def validate_proposal_record_id(
    identifier: str,
    pattern: re.Pattern[str],
    record_type: str,
) -> None:
    if pattern.fullmatch(identifier) is None:
        raise ValueError(f"Invalid {record_type} identifier: {identifier}")


def proposal_path(
    proposal_id: str,
    directory: Path = PROPOSALS_DIRECTORY,
) -> Path:
    validate_proposal_record_id(
        proposal_id,
        PROPOSAL_ID_PATTERN,
        "proposal",
    )
    return directory / f"{proposal_id}.json"


def proposal_acceptance_path(
    acceptance_id: str,
    directory: Path = PROPOSAL_ACCEPTANCES_DIRECTORY,
) -> Path:
    validate_proposal_record_id(
        acceptance_id,
        PROPOSAL_ACCEPTANCE_ID_PATTERN,
        "proposal acceptance",
    )
    return directory / f"{acceptance_id}.json"


def load_proposal(
    path: Path,
) -> NextWorkoutProposal:
    return NextWorkoutProposal.model_validate_json(path.read_text(encoding="utf-8"))


def load_proposal_acceptance(
    path: Path,
) -> ProposalAcceptance:
    return ProposalAcceptance.model_validate_json(path.read_text(encoding="utf-8"))


def save_proposal(
    proposal: NextWorkoutProposal,
    directory: Path = PROPOSALS_DIRECTORY,
) -> Path:
    destination = proposal_path(
        proposal.proposal_id,
        directory,
    )
    written_path = write_new_json_record(
        proposal,
        destination,
    )

    loaded = load_proposal(written_path)

    if loaded != proposal:
        raise ValueError("Persisted proposal does not match the source proposal.")

    return written_path


def save_proposal_acceptance(
    acceptance: ProposalAcceptance,
    directory: Path = PROPOSAL_ACCEPTANCES_DIRECTORY,
) -> Path:
    destination = proposal_acceptance_path(
        acceptance.acceptance_id,
        directory,
    )
    written_path = write_new_json_record(
        acceptance,
        destination,
    )

    loaded = load_proposal_acceptance(written_path)

    if loaded != acceptance:
        raise ValueError("Persisted proposal acceptance does not match the source acceptance.")

    return written_path
