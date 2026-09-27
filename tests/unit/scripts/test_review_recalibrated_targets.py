from __future__ import annotations

from pathlib import Path

import pytest
import scripts.review_recalibrated_targets as workflow
from pydantic import ValidationError
from tests.unit.test_pool_test_three_proposal import (
    build_parent,
    build_previous_result,
)
from tests.unit.test_recalibrated_target_review import (
    build_prior_decision,
    build_proposal,
)

from adaptive_swimming.domain.session_results import CompletionStatus
from adaptive_swimming.domain.workout import (
    EquipmentCode,
    ExerciseCode,
    IntensityCode,
)
from adaptive_swimming.evaluation.pace_calibration import PaceObservationKey
from adaptive_swimming.persistence.recalibrated_target_review_records import (
    load_recalibrated_review_set,
    save_recalibrated_review_set,
)
from adaptive_swimming.persistence.target_review_records import (
    save_target_review_decision,
)
from adaptive_swimming.planning.recalibrated_target_review import (
    RecalibratedTargetReviewAction,
    RecalibratedTargetReviewSet,
    build_recalibrated_target_review_decision,
    build_recalibrated_target_review_set,
)

REVIEW_SET_ID = "RTRS_20260906_001_V1"
DECISION_ID = "RTRD_20260906_001_V1"


def fins_key() -> PaceObservationKey:
    return PaceObservationKey(
        exercise=ExerciseCode.FREESTYLE,
        distance_meters=50,
        equipment=(EquipmentCode.FINS,),
        intensity=IntensityCode.UNRESOLVED,
    )


def aerobic_key() -> PaceObservationKey:
    return PaceObservationKey(
        exercise=ExerciseCode.FREESTYLE,
        distance_meters=100,
        equipment=(),
        intensity=IntensityCode.AEROBIC,
    )


def specification_entry(
    *,
    key: PaceObservationKey | None = None,
    decision_id: str = DECISION_ID,
    action: RecalibratedTargetReviewAction = (RecalibratedTargetReviewAction.DEFER),
    effective_target_seconds: int | None = None,
    prior_path: Path | None = None,
    prior_id: str | None = None,
) -> workflow.RecalibratedReviewSpecificationEntry:
    return workflow.RecalibratedReviewSpecificationEntry(
        review_decision_id=decision_id,
        review_decision_version=1,
        key=key or fins_key(),
        action=action,
        effective_target_seconds=effective_target_seconds,
        prior_review_decision_path=prior_path,
        prior_review_decision_id=prior_id,
        rationale=("Synthetic workflow review.",),
    )


def specification(
    *entries: workflow.RecalibratedReviewSpecificationEntry,
) -> workflow.RecalibratedReviewSpecification:
    return workflow.RecalibratedReviewSpecification(
        review_set_id=REVIEW_SET_ID,
        review_set_version=1,
        decisions=entries or (specification_entry(),),
    )


def review_set_for_persistence() -> RecalibratedTargetReviewSet:
    decision = build_recalibrated_target_review_decision(
        build_proposal(),
        review_decision_id=DECISION_ID,
        review_decision_version=1,
        action=RecalibratedTargetReviewAction.RETAIN_CURRENT_TARGET,
        effective_target_seconds=65,
        prior_decision=build_prior_decision(),
        rationale=("Retain the current target.",),
    )
    return build_recalibrated_target_review_set(
        review_set_id=REVIEW_SET_ID,
        review_set_version=1,
        decisions=(decision,),
    )


def write_json_model(path: Path, model: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")  # type: ignore[attr-defined]
    return path


def test_manifest_rejects_duplicate_path_pairs() -> None:
    entry = workflow.SessionManifestEntry(
        generated_workout_path=Path("workout.json"),
        session_result_path=Path("result.json"),
    )
    with pytest.raises(ValidationError, match="duplicate workout/result"):
        workflow.SessionManifest(sessions=(entry, entry))


def test_specification_rejects_prior_path_without_id() -> None:
    with pytest.raises(ValidationError, match="both be present"):
        specification_entry(prior_path=Path("prior.json"))


def test_specification_rejects_prior_id_without_path() -> None:
    with pytest.raises(ValidationError, match="both be present"):
        specification_entry(prior_id="TRD_20260905_001_V1")


def test_retain_specification_requires_prior_reference() -> None:
    with pytest.raises(ValidationError, match="requires a prior"):
        specification_entry(
            action=RecalibratedTargetReviewAction.RETAIN_CURRENT_TARGET,
            effective_target_seconds=65,
        )


def test_specification_rejects_duplicate_strict_keys() -> None:
    first = specification_entry()
    second = specification_entry(decision_id="RTRD_20260906_002_V1")
    with pytest.raises(ValidationError, match="strict keys must be unique"):
        specification(first, second)


def test_match_requires_exact_proposal_coverage() -> None:
    proposal = build_proposal()
    with pytest.raises(ValueError, match="Missing review specifications"):
        workflow.match_proposals_to_specification(
            (proposal,),
            specification(specification_entry(key=aerobic_key())),
        )


def test_match_returns_exact_strict_key_pair() -> None:
    proposal = build_proposal()
    entry = specification_entry(key=proposal.key)
    matched = workflow.match_proposals_to_specification((proposal,), specification(entry))
    assert matched == ((proposal, entry),)


def test_load_session_pairs_rejects_not_started(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workout_path = tmp_path / "workout.json"
    result_path = tmp_path / "result.json"
    workout_path.touch()
    result_path.touch()
    parent = build_parent()
    not_started = build_previous_result().model_copy(
        update={
            "completion_status": CompletionStatus.NOT_STARTED,
            "completed_distance_meters": 0,
            "actual_total_seconds": None,
        }
    )
    monkeypatch.setattr(workflow, "load_generated_workout", lambda _path: parent)
    monkeypatch.setattr(workflow, "load_session_result", lambda _path: not_started)
    monkeypatch.setattr(workflow, "validate_session_result", lambda *_args: None)
    manifest = workflow.SessionManifest(
        sessions=(
            workflow.SessionManifestEntry(
                generated_workout_path=workout_path,
                session_result_path=result_path,
            ),
        )
    )
    with pytest.raises(ValueError, match="NOT_STARTED"):
        workflow.load_session_pairs(manifest)


def test_load_session_pairs_rejects_duplicate_result_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = tuple(tmp_path / name for name in ("w1", "r1", "w2", "r2"))
    for path in paths:
        path.touch()
    parent = build_parent()
    result = build_previous_result()
    monkeypatch.setattr(workflow, "load_generated_workout", lambda _path: parent)
    monkeypatch.setattr(workflow, "load_session_result", lambda _path: result)
    monkeypatch.setattr(workflow, "validate_session_result", lambda *_args: None)
    manifest = workflow.SessionManifest(
        sessions=(
            workflow.SessionManifestEntry(
                generated_workout_path=paths[0], session_result_path=paths[1]
            ),
            workflow.SessionManifestEntry(
                generated_workout_path=paths[2], session_result_path=paths[3]
            ),
        )
    )
    with pytest.raises(ValueError, match="duplicate session-result IDs"):
        workflow.load_session_pairs(manifest)


def test_resolve_legacy_prior_decision(tmp_path: Path) -> None:
    prior = build_prior_decision()
    path = save_target_review_decision(prior, tmp_path)
    assert workflow.resolve_prior_decision(path=path, decision_id=prior.review_decision_id) == prior


def test_resolve_prior_recalibrated_decision(tmp_path: Path) -> None:
    review_set = review_set_for_persistence()
    path = save_recalibrated_review_set(review_set, tmp_path)
    resolved = workflow.resolve_prior_decision(path=path, decision_id=DECISION_ID)
    assert resolved == review_set.decisions[0]


def test_resolve_missing_recalibrated_decision_is_rejected(
    tmp_path: Path,
) -> None:
    path = save_recalibrated_review_set(review_set_for_persistence(), tmp_path)
    with pytest.raises(ValueError, match="found 0"):
        workflow.resolve_prior_decision(
            path=path,
            decision_id="RTRD_20260906_999_V1",
        )


def test_review_workflow_persists_and_reloads_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    spec_path = tmp_path / "specification.json"
    manifest_path.write_text("{}", encoding="utf-8")
    spec_path.write_text("{}", encoding="utf-8")
    expected = review_set_for_persistence()
    monkeypatch.setattr(
        workflow,
        "load_session_manifest",
        lambda _path: workflow.SessionManifest(
            sessions=(
                workflow.SessionManifestEntry(
                    generated_workout_path=Path("w.json"),
                    session_result_path=Path("r.json"),
                ),
            )
        ),
    )
    monkeypatch.setattr(
        workflow,
        "load_review_specification",
        lambda _path: specification(),
    )
    monkeypatch.setattr(workflow, "load_session_pairs", lambda _manifest: ())
    monkeypatch.setattr(
        workflow,
        "build_review_set",
        lambda **_kwargs: expected,
    )
    path = workflow.review_recalibrated_targets(
        session_manifest_path=manifest_path,
        review_specification_path=spec_path,
        output_directory=tmp_path / "reviews",
    )
    assert load_recalibrated_review_set(path) == expected


def test_existing_review_set_destination_prevents_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    spec_path = tmp_path / "specification.json"
    manifest_path.write_text("{}", encoding="utf-8")
    spec_path.write_text("{}", encoding="utf-8")
    expected = review_set_for_persistence()
    monkeypatch.setattr(workflow, "load_session_manifest", lambda _path: object())
    monkeypatch.setattr(workflow, "load_review_specification", lambda _path: object())
    monkeypatch.setattr(workflow, "load_session_pairs", lambda _manifest: ())
    monkeypatch.setattr(workflow, "build_review_set", lambda **_kwargs: expected)
    output = tmp_path / "reviews"
    output.mkdir()
    destination = output / f"{REVIEW_SET_ID}.json"
    destination.write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        workflow.review_recalibrated_targets(
            session_manifest_path=manifest_path,
            review_specification_path=spec_path,
            output_directory=output,
        )
    assert destination.read_text(encoding="utf-8") == "existing"


def test_post_write_validation_failure_rolls_back_new_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    spec_path = tmp_path / "specification.json"
    manifest_path.write_text("{}", encoding="utf-8")
    spec_path.write_text("{}", encoding="utf-8")
    expected = review_set_for_persistence()
    monkeypatch.setattr(workflow, "load_session_manifest", lambda _path: object())
    monkeypatch.setattr(workflow, "load_review_specification", lambda _path: object())
    monkeypatch.setattr(workflow, "load_session_pairs", lambda _manifest: ())
    monkeypatch.setattr(workflow, "build_review_set", lambda **_kwargs: expected)

    def fail_validation(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Simulated post-write validation failure")

    monkeypatch.setattr(workflow, "validate_persisted_review_set", fail_validation)
    output = tmp_path / "reviews"
    with pytest.raises(RuntimeError, match="post-write"):
        workflow.review_recalibrated_targets(
            session_manifest_path=manifest_path,
            review_specification_path=spec_path,
            output_directory=output,
        )
    assert not tuple(output.glob("*.json"))


def test_success_leaves_no_temporary_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    spec_path = tmp_path / "specification.json"
    manifest_path.write_text("{}", encoding="utf-8")
    spec_path.write_text("{}", encoding="utf-8")
    expected = review_set_for_persistence()
    monkeypatch.setattr(workflow, "load_session_manifest", lambda _path: object())
    monkeypatch.setattr(workflow, "load_review_specification", lambda _path: object())
    monkeypatch.setattr(workflow, "load_session_pairs", lambda _manifest: ())
    monkeypatch.setattr(workflow, "build_review_set", lambda **_kwargs: expected)
    workflow.review_recalibrated_targets(
        session_manifest_path=manifest_path,
        review_specification_path=spec_path,
        output_directory=tmp_path / "reviews",
    )
    assert not tuple(tmp_path.rglob("*.tmp"))
