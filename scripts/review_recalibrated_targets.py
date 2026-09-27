from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import Field, model_validator

from adaptive_swimming.domain.session_results import (
    CompletionStatus,
    GeneratedWorkout,
    WorkoutSessionResult,
    validate_session_result,
)
from adaptive_swimming.domain.workout import StrictDomainModel
from adaptive_swimming.evaluation.calibration_eligibility import (
    assess_calibration_summaries,
)
from adaptive_swimming.evaluation.pace_calibration import (
    PaceObservationKey,
    calibrate_pace_from_sessions,
)
from adaptive_swimming.persistence.recalibrated_target_review_records import (
    load_recalibrated_review_set,
    recalibrated_review_set_path,
    save_recalibrated_review_set,
)
from adaptive_swimming.persistence.session_records import (
    RECALIBRATED_TARGET_REVIEWS_DIRECTORY,
    load_generated_workout,
    load_session_result,
)
from adaptive_swimming.persistence.target_review_records import (
    load_target_review_decision,
)
from adaptive_swimming.planning.provisional_target_proposals import (
    ProvisionalTargetProposal,
    propose_eligible_targets_for_review,
)
from adaptive_swimming.planning.recalibrated_target_review import (
    PriorTargetReviewDecision,
    RecalibratedTargetReviewAction,
    RecalibratedTargetReviewDecision,
    RecalibratedTargetReviewSet,
    build_recalibrated_target_review_decision,
    build_recalibrated_target_review_set,
)


class SessionManifestEntry(StrictDomainModel):
    generated_workout_path: Path
    session_result_path: Path


class SessionManifest(StrictDomainModel):
    sessions: tuple[SessionManifestEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_entries(self) -> SessionManifest:
        path_pairs = tuple(
            (
                str(entry.generated_workout_path),
                str(entry.session_result_path),
            )
            for entry in self.sessions
        )
        if len(path_pairs) != len(set(path_pairs)):
            raise ValueError("Session manifest cannot contain duplicate workout/result path pairs.")
        return self


class RecalibratedReviewSpecificationEntry(StrictDomainModel):
    review_decision_id: str = Field(pattern=r"^RTRD_[0-9]{8}_[0-9]{3}_V[0-9]+$")
    review_decision_version: int = Field(ge=1)
    key: PaceObservationKey
    action: RecalibratedTargetReviewAction
    effective_target_seconds: int | None = Field(default=None, gt=0)
    prior_review_decision_path: Path | None = None
    prior_review_decision_id: str | None = Field(
        default=None,
        pattern=r"^(?:TRD|RTRD)_[0-9]{8}_[0-9]{3}_V[0-9]+$",
    )
    rationale: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_prior_reference(self) -> RecalibratedReviewSpecificationEntry:
        has_path = self.prior_review_decision_path is not None
        has_id = self.prior_review_decision_id is not None
        if has_path != has_id:
            raise ValueError(
                "Prior review decision path and ID must either both be present or both be absent."
            )
        if self.action == RecalibratedTargetReviewAction.RETAIN_CURRENT_TARGET and not has_path:
            raise ValueError("Retaining a target requires a prior review decision reference.")
        return self


class RecalibratedReviewSpecification(StrictDomainModel):
    review_set_id: str = Field(pattern=r"^RTRS_[0-9]{8}_[0-9]{3}_V[0-9]+$")
    review_set_version: int = Field(ge=1)
    decisions: tuple[RecalibratedReviewSpecificationEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_decisions(self) -> RecalibratedReviewSpecification:
        decision_ids = tuple(decision.review_decision_id for decision in self.decisions)
        if len(decision_ids) != len(set(decision_ids)):
            raise ValueError("Review specification decision IDs must be unique.")

        key_tokens = tuple(key_token(decision.key) for decision in self.decisions)
        if len(key_tokens) != len(set(key_tokens)):
            raise ValueError("Review specification strict keys must be unique.")
        return self


def key_token(key: PaceObservationKey) -> str:
    return key.model_dump_json()


def load_session_manifest(path: Path) -> SessionManifest:
    if not path.is_file():
        raise FileNotFoundError(f"Session manifest does not exist: {path}")
    return SessionManifest.model_validate_json(path.read_text(encoding="utf-8"))


def load_review_specification(path: Path) -> RecalibratedReviewSpecification:
    if not path.is_file():
        raise FileNotFoundError(f"Review specification does not exist: {path}")
    return RecalibratedReviewSpecification.model_validate_json(path.read_text(encoding="utf-8"))


def load_session_pairs(
    manifest: SessionManifest,
) -> tuple[tuple[GeneratedWorkout, WorkoutSessionResult], ...]:
    pairs: list[tuple[GeneratedWorkout, WorkoutSessionResult]] = []
    result_ids: set[str] = set()

    for entry in manifest.sessions:
        if not entry.generated_workout_path.is_file():
            raise FileNotFoundError(
                f"Generated workout does not exist: {entry.generated_workout_path}"
            )
        if not entry.session_result_path.is_file():
            raise FileNotFoundError(f"Session result does not exist: {entry.session_result_path}")

        generated_workout = load_generated_workout(entry.generated_workout_path)
        session_result = load_session_result(entry.session_result_path)
        validate_session_result(generated_workout, session_result)

        if session_result.completion_status == CompletionStatus.NOT_STARTED:
            raise ValueError("Recalibration cannot use a NOT_STARTED session result.")
        if session_result.session_result_id in result_ids:
            raise ValueError("Session manifest contains duplicate session-result IDs.")

        result_ids.add(session_result.session_result_id)
        pairs.append((generated_workout, session_result))

    return tuple(pairs)


def resolve_prior_decision(
    *,
    path: Path,
    decision_id: str,
) -> PriorTargetReviewDecision:
    if not path.is_file():
        raise FileNotFoundError(f"Prior review-decision file does not exist: {path}")

    if decision_id.startswith("TRD_"):
        decision = load_target_review_decision(path)
        if decision.review_decision_id != decision_id:
            raise ValueError("Loaded legacy prior decision ID does not match the specification.")
        return decision

    review_set = load_recalibrated_review_set(path)
    matches = tuple(
        decision for decision in review_set.decisions if decision.review_decision_id == decision_id
    )
    if len(matches) != 1:
        raise ValueError(
            "Expected exactly one recalibrated prior decision with ID "
            f"{decision_id}; found {len(matches)}."
        )
    return matches[0]


def match_proposals_to_specification(
    proposals: tuple[ProvisionalTargetProposal, ...],
    specification: RecalibratedReviewSpecification,
) -> tuple[tuple[ProvisionalTargetProposal, RecalibratedReviewSpecificationEntry], ...]:
    proposals_by_key = {key_token(proposal.key): proposal for proposal in proposals}
    specifications_by_key = {key_token(entry.key): entry for entry in specification.decisions}

    proposal_keys = set(proposals_by_key)
    specification_keys = set(specifications_by_key)
    missing = tuple(sorted(proposal_keys - specification_keys))
    unexpected = tuple(sorted(specification_keys - proposal_keys))

    if missing or unexpected:
        raise ValueError(
            "Review specification does not exactly cover eligible proposals. "
            f"Missing review specifications: {missing}. "
            f"Unexpected review specifications: {unexpected}."
        )

    return tuple(
        (proposals_by_key[token], specifications_by_key[token]) for token in sorted(proposal_keys)
    )


def build_review_set(
    *,
    pairs: tuple[tuple[GeneratedWorkout, WorkoutSessionResult], ...],
    specification: RecalibratedReviewSpecification,
) -> RecalibratedTargetReviewSet:
    summaries = calibrate_pace_from_sessions(pairs)
    assessments = assess_calibration_summaries(summaries)
    proposals = propose_eligible_targets_for_review(assessments)
    matched = match_proposals_to_specification(proposals, specification)

    decisions: list[RecalibratedTargetReviewDecision] = []
    for proposal, entry in matched:
        prior_decision: PriorTargetReviewDecision | None = None
        if (
            entry.prior_review_decision_path is not None
            and entry.prior_review_decision_id is not None
        ):
            prior_decision = resolve_prior_decision(
                path=entry.prior_review_decision_path,
                decision_id=entry.prior_review_decision_id,
            )

        decisions.append(
            build_recalibrated_target_review_decision(
                proposal,
                review_decision_id=entry.review_decision_id,
                review_decision_version=entry.review_decision_version,
                action=entry.action,
                effective_target_seconds=entry.effective_target_seconds,
                prior_decision=prior_decision,
                rationale=entry.rationale,
            )
        )

    return build_recalibrated_target_review_set(
        review_set_id=specification.review_set_id,
        review_set_version=specification.review_set_version,
        decisions=tuple(decisions),
    )


def validate_persisted_review_set(
    path: Path,
    source: RecalibratedTargetReviewSet,
) -> None:
    loaded = load_recalibrated_review_set(path)
    if loaded != source:
        raise ValueError("Persisted recalibrated review set does not match the source set.")


def review_recalibrated_targets(
    *,
    session_manifest_path: Path,
    review_specification_path: Path,
    output_directory: Path = RECALIBRATED_TARGET_REVIEWS_DIRECTORY,
) -> Path:
    manifest = load_session_manifest(session_manifest_path)
    specification = load_review_specification(review_specification_path)
    pairs = load_session_pairs(manifest)
    review_set = build_review_set(pairs=pairs, specification=specification)

    destination = recalibrated_review_set_path(review_set.review_set_id, output_directory)
    if destination.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing recalibrated review set: {destination}"
        )

    created_path: Path | None = None
    try:
        created_path = save_recalibrated_review_set(review_set, output_directory)
        validate_persisted_review_set(created_path, review_set)
    except Exception:
        if created_path is not None and created_path.exists():
            created_path.unlink()
        raise

    return created_path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review every eligible recalibrated target and persist one atomic reviewed set."
        )
    )
    parser.add_argument("--session-manifest", type=Path, required=True)
    parser.add_argument("--review-specification", type=Path, required=True)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=RECALIBRATED_TARGET_REVIEWS_DIRECTORY,
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    path = review_recalibrated_targets(
        session_manifest_path=arguments.session_manifest,
        review_specification_path=arguments.review_specification,
        output_directory=arguments.output_directory,
    )
    review_set = load_recalibrated_review_set(path)

    print(f"Saved recalibrated target review set: {path}")
    print(f"Review set ID: {review_set.review_set_id}")
    print(f"Decisions: {len(review_set.decisions)}")
    print(f"Source session results: {len(review_set.source_session_result_ids)}")
    for decision in review_set.decisions:
        print(
            decision.review_decision_id,
            decision.action.value,
            decision.proposal.proposed_target_seconds,
            decision.effective_target_seconds,
        )


if __name__ == "__main__":
    main()
