from __future__ import annotations

import re
from pathlib import Path

from adaptive_swimming.persistence.session_records import (
    TARGET_REVIEW_DECISIONS_DIRECTORY,
    write_new_json_record,
)
from adaptive_swimming.planning.target_review_decisions import (
    TargetReviewDecision,
)

TARGET_REVIEW_DECISION_ID_PATTERN = re.compile(r"^TRD_[0-9]{8}_[0-9]{3}_V[0-9]+$")


def validate_target_review_decision_id(
    review_decision_id: str,
) -> None:
    if TARGET_REVIEW_DECISION_ID_PATTERN.fullmatch(review_decision_id) is None:
        raise ValueError(f"Invalid target review decision identifier: {review_decision_id}")


def target_review_decision_path(
    review_decision_id: str,
    directory: Path = (TARGET_REVIEW_DECISIONS_DIRECTORY),
) -> Path:
    validate_target_review_decision_id(review_decision_id)

    return directory / f"{review_decision_id}.json"


def load_target_review_decision(
    path: Path,
) -> TargetReviewDecision:
    return TargetReviewDecision.model_validate_json(path.read_text(encoding="utf-8"))


def save_target_review_decision(
    decision: TargetReviewDecision,
    directory: Path = (TARGET_REVIEW_DECISIONS_DIRECTORY),
) -> Path:
    destination = target_review_decision_path(
        decision.review_decision_id,
        directory,
    )

    written_path = write_new_json_record(
        decision,
        destination,
    )

    loaded = load_target_review_decision(written_path)

    if loaded != decision:
        raise ValueError("Persisted target review decision does not match the source decision.")

    return written_path
