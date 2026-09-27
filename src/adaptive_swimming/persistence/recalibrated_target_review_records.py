from __future__ import annotations

import re
from pathlib import Path

from adaptive_swimming.persistence.session_records import (
    RECALIBRATED_TARGET_REVIEWS_DIRECTORY,
    write_new_json_record,
)
from adaptive_swimming.planning.recalibrated_target_review import (
    RecalibratedTargetReviewSet,
)

RECALIBRATED_REVIEW_SET_ID_PATTERN = re.compile(r"^RTRS_[0-9]{8}_[0-9]{3}_V[0-9]+$")


def validate_recalibrated_review_set_id(
    review_set_id: str,
) -> None:
    if RECALIBRATED_REVIEW_SET_ID_PATTERN.fullmatch(review_set_id) is None:
        raise ValueError(f"Invalid recalibrated review-set identifier: {review_set_id}")


def recalibrated_review_set_path(
    review_set_id: str,
    directory: Path = (RECALIBRATED_TARGET_REVIEWS_DIRECTORY),
) -> Path:
    validate_recalibrated_review_set_id(review_set_id)

    return directory / f"{review_set_id}.json"


def load_recalibrated_review_set(
    path: Path,
) -> RecalibratedTargetReviewSet:
    return RecalibratedTargetReviewSet.model_validate_json(path.read_text(encoding="utf-8"))


def save_recalibrated_review_set(
    review_set: RecalibratedTargetReviewSet,
    directory: Path = (RECALIBRATED_TARGET_REVIEWS_DIRECTORY),
) -> Path:
    destination = recalibrated_review_set_path(
        review_set.review_set_id,
        directory,
    )

    written_path = write_new_json_record(
        review_set,
        destination,
    )

    loaded = load_recalibrated_review_set(written_path)

    if loaded != review_set:
        raise ValueError("Persisted recalibrated review set does not match the source review set.")

    return written_path
