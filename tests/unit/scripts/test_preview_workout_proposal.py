from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from scripts.preview_workout_proposal import (
    build_preview,
    render_summary,
    select_review_decision,
)
from tests.unit.test_configurable_workout_proposal import (
    build_parent,
    build_previous_result,
    build_reviewed_decision,
)

from adaptive_swimming.persistence.recalibrated_target_review_records import (
    save_recalibrated_review_set,
)
from adaptive_swimming.persistence.session_records import (
    save_generated_workout,
    save_session_result,
)
from adaptive_swimming.planning.configurable_workout_proposal import (
    TargetApplicationSelection,
)
from adaptive_swimming.planning.recalibrated_target_review import (
    build_recalibrated_target_review_set,
)
from adaptive_swimming.planning.workout_proposal import NextWorkoutProposal


def write_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    parent = build_parent()
    previous = build_previous_result()
    decision = build_reviewed_decision()
    review_set = build_recalibrated_target_review_set(
        review_set_id="RTRS_20260906_001_V1",
        review_set_version=1,
        decisions=(decision,),
    )
    parent_path = save_generated_workout(parent, tmp_path / "generated")
    result_path = save_session_result(parent, previous, tmp_path / "results")
    review_path = save_recalibrated_review_set(review_set, tmp_path / "reviews")
    return parent_path, result_path, review_path


def build_test_preview(tmp_path: Path) -> NextWorkoutProposal:
    parent_path, result_path, review_path = write_inputs(tmp_path)
    return build_preview(
        parent_generated_workout_path=parent_path,
        previous_result_path=result_path,
        review_set_path=review_path,
        review_decision_id="RTRD_20260906_001_V1",
        selection=TargetApplicationSelection(
            block_sequence=4,
            set_group_sequence=1,
            item_sequence=1,
        ),
        proposal_id="NWP_20261001_007_V1",
        proposal_version=1,
        generated_workout_id="GW_20261001_007_V1",
        generated_workout_version=1,
        workout_session_id="WT_ENGINE_CONFIGURABLE_007_V1",
        generation_reason="CONFIGURABLE_REVIEWED_TARGET_PROPOSAL",
    )


def test_direct_file_help_succeeds() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/preview_workout_proposal.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "--review-set" in completed.stdout
    assert "--output-format" in completed.stdout
    assert "ModuleNotFoundError" not in completed.stderr


def test_module_help_succeeds() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.preview_workout_proposal", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "--proposal-id" in completed.stdout


def test_preview_builds_retained_target_without_writes(tmp_path: Path) -> None:
    before = tuple(sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")))
    proposal = build_test_preview(tmp_path)
    after = tuple(sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")))
    item = proposal.proposed_generated_workout.workout.blocks[3].set_groups[0].items[0]

    assert item.target is not None
    assert item.target.target_seconds == 65
    assert proposal.parent_generated_workout_id == "GW_20260905_001_V1"
    assert before == ()
    assert all("NWP_" not in str(path) for path in after)
    assert all("NWA_" not in str(path) for path in after)
    assert all("GW_20261001_007" not in str(path) for path in after)
    assert all("SR_20261001_007" not in str(path) for path in after)


def test_preview_preserves_all_input_bytes(tmp_path: Path) -> None:
    parent_path, result_path, review_path = write_inputs(tmp_path)
    inputs = (parent_path, result_path, review_path)
    before = {path: path.read_bytes() for path in inputs}

    build_preview(
        parent_generated_workout_path=parent_path,
        previous_result_path=result_path,
        review_set_path=review_path,
        review_decision_id="RTRD_20260906_001_V1",
        selection=TargetApplicationSelection(
            block_sequence=4,
            set_group_sequence=1,
            item_sequence=1,
        ),
        proposal_id="NWP_20261001_007_V1",
        proposal_version=1,
        generated_workout_id="GW_20261001_007_V1",
        generated_workout_version=1,
        workout_session_id="WT_ENGINE_CONFIGURABLE_007_V1",
        generation_reason="CONFIGURABLE_REVIEWED_TARGET_PROPOSAL",
    )

    assert {path: path.read_bytes() for path in inputs} == before


def test_summary_distinguishes_proposed_and_effective_targets(tmp_path: Path) -> None:
    proposal = build_test_preview(tmp_path)
    _, _, review_path = write_inputs(tmp_path / "summary-inputs")
    decision = select_review_decision(
        review_set_path=review_path,
        review_decision_id="RTRD_20260906_001_V1",
    )
    summary = render_summary(
        proposal,
        decision,
        TargetApplicationSelection(
            block_sequence=4,
            set_group_sequence=1,
            item_sequence=1,
        ),
    )
    assert "Recalibration proposal: 64 seconds" in summary
    assert "Effective target: 65 seconds" in summary
    assert "Writes performed: none" in summary


def test_missing_input_is_rejected(tmp_path: Path) -> None:
    _, result_path, review_path = write_inputs(tmp_path)
    with pytest.raises(FileNotFoundError, match="Parent generated workout"):
        build_preview(
            parent_generated_workout_path=tmp_path / "missing.json",
            previous_result_path=result_path,
            review_set_path=review_path,
            review_decision_id="RTRD_20260906_001_V1",
            selection=TargetApplicationSelection(
                block_sequence=4,
                set_group_sequence=1,
                item_sequence=1,
            ),
            proposal_id="NWP_20261001_007_V1",
            proposal_version=1,
            generated_workout_id="GW_20261001_007_V1",
            generated_workout_version=1,
            workout_session_id="WT_ENGINE_CONFIGURABLE_007_V1",
            generation_reason="CONFIGURABLE_REVIEWED_TARGET_PROPOSAL",
        )


def test_unknown_review_decision_is_rejected(tmp_path: Path) -> None:
    _, _, review_path = write_inputs(tmp_path)
    with pytest.raises(ValueError, match="found 0"):
        select_review_decision(
            review_set_path=review_path,
            review_decision_id="RTRD_20260906_999_V1",
        )
