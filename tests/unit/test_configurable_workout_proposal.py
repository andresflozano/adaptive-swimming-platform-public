from __future__ import annotations

from typing import Any

import pytest

from adaptive_swimming.domain.session_results import (
    CompletionStatus,
    GeneratedWorkout,
    WorkoutSessionResult,
)
from adaptive_swimming.domain.workout import Target, TargetType
from adaptive_swimming.planning.configurable_workout_proposal import (
    TargetApplicationSelection,
    build_configurable_workout_proposal,
    format_target_seconds,
)
from adaptive_swimming.planning.recalibrated_target_review import (
    RecalibratedTargetReviewAction,
    RecalibratedTargetReviewDecision,
    build_recalibrated_target_review_decision,
)
from adaptive_swimming.planning.workout_proposal import (
    AdaptationTraceEntry,
    NextWorkoutProposal,
    ProposalStatus,
    build_pool_test_two_workout,
)
from tests.unit.test_recalibrated_target_review import (
    build_prior_decision,
)
from tests.unit.test_recalibrated_target_review import (
    build_proposal as build_target_proposal,
)


def build_parent() -> GeneratedWorkout:
    workout = build_pool_test_two_workout()
    target = Target(
        target_type=TargetType.REPETITION_COMPLETION_TIME,
        raw_value="1:05",
        target_seconds=65,
    )
    block_four = workout.blocks[3]
    group = block_four.set_groups[0]
    item = group.items[0].model_copy(update={"target": target})
    updated_group = group.model_copy(update={"items": (item,)})
    updated_block = block_four.model_copy(update={"set_groups": (updated_group,)})
    blocks = list(workout.blocks)
    blocks[3] = updated_block

    return GeneratedWorkout(
        generated_workout_id="GW_20260905_001_V1",
        workout_version=1,
        workout=workout.model_copy(
            update={
                "session_id": "WT_ENGINE_POOL_TEST_003_V1",
                "blocks": tuple(blocks),
            }
        ),
        pool_length_meters=12.5,
        available_training_seconds=3600,
        generation_reason="POOL_TEST_3_ACCEPTED_FINS_TARGET_PROPOSAL",
    )


def build_previous_result(
    *,
    completion_status: CompletionStatus = CompletionStatus.COMPLETED_WITH_MODIFICATIONS,
    safety_issue_reported: bool = False,
) -> WorkoutSessionResult:
    completed_distance = 0 if completion_status == CompletionStatus.NOT_STARTED else 1500
    return WorkoutSessionResult(
        session_result_id="SR_20260905_001_V2",
        generated_workout_id="GW_20260905_001_V1",
        result_version=2,
        completion_status=completion_status,
        completed_distance_meters=completed_distance,
        actual_total_seconds=(None if completion_status == CompletionStatus.NOT_STARTED else 3480),
        safety_issue_reported=safety_issue_reported,
    )


def build_reviewed_decision(
    action: RecalibratedTargetReviewAction = (RecalibratedTargetReviewAction.RETAIN_CURRENT_TARGET),
) -> RecalibratedTargetReviewDecision:
    proposal = build_target_proposal()
    return build_recalibrated_target_review_decision(
        proposal,
        review_decision_id="RTRD_20260906_001_V1",
        review_decision_version=1,
        action=action,
        effective_target_seconds=(
            65 if action == RecalibratedTargetReviewAction.RETAIN_CURRENT_TARGET else None
        ),
        prior_decision=(
            build_prior_decision()
            if action == RecalibratedTargetReviewAction.RETAIN_CURRENT_TARGET
            else None
        ),
        rationale=("Synthetic configurable proposal test.",),
    )


def build_proposal(
    **overrides: Any,
) -> NextWorkoutProposal:
    arguments: dict[str, Any] = {
        "parent_generated_workout": build_parent(),
        "previous_result": build_previous_result(),
        "reviewed_decision": build_reviewed_decision(),
        "selection": TargetApplicationSelection(
            block_sequence=4,
            set_group_sequence=1,
            item_sequence=1,
        ),
        "proposal_id": "NWP_20261001_007_V1",
        "proposal_version": 1,
        "generated_workout_id": "GW_20261001_007_V1",
        "generated_workout_version": 1,
        "workout_session_id": "WT_ENGINE_CONFIGURABLE_007_V1",
        "generation_reason": "CONFIGURABLE_REVIEWED_TARGET_PROPOSAL",
        "adaptation_trace": (
            AdaptationTraceEntry(
                rule_id="APPLY_REVIEWED_TARGET",
                description="Apply one reviewed target at an explicit coordinate.",
            ),
        ),
        "limitations": ("Synthetic proposal test only.",),
    }
    arguments.update(overrides)
    return build_configurable_workout_proposal(**arguments)


def test_formats_target_seconds() -> None:
    assert format_target_seconds(59) == "59"
    assert format_target_seconds(65) == "1:05"
    assert format_target_seconds(120) == "2:00"


def test_retained_target_builds_proposed_workout() -> None:
    proposal = build_proposal()
    item = proposal.proposed_generated_workout.workout.blocks[3].set_groups[0].items[0]

    assert proposal.status == ProposalStatus.PROPOSED
    assert proposal.parent_generated_workout_id == "GW_20260905_001_V1"
    assert proposal.previous_session_result_id == "SR_20260905_001_V2"
    assert item.target is not None
    assert item.target.target_seconds == 65
    assert item.target.raw_value == "1:05"


def test_parent_and_previous_result_remain_unchanged() -> None:
    parent = build_parent()
    previous = build_previous_result()
    parent_before = parent.model_dump_json()
    previous_before = previous.model_dump_json()

    build_proposal(parent_generated_workout=parent, previous_result=previous)

    assert parent.model_dump_json() == parent_before
    assert previous.model_dump_json() == previous_before


def test_only_selected_item_changes() -> None:
    parent = build_parent()
    proposal = build_proposal(parent_generated_workout=parent)
    proposed = proposal.proposed_generated_workout.workout

    for block_index, (old_block, new_block) in enumerate(
        zip(parent.workout.blocks, proposed.blocks, strict=True), start=1
    ):
        for group_index, (old_group, new_group) in enumerate(
            zip(old_block.set_groups, new_block.set_groups, strict=True), start=1
        ):
            for item_index, (old_item, new_item) in enumerate(
                zip(old_group.items, new_group.items, strict=True), start=1
            ):
                if (block_index, group_index, item_index) == (4, 1, 1):
                    assert new_item != old_item
                else:
                    assert new_item == old_item


def test_identical_inputs_are_deterministic() -> None:
    assert build_proposal() == build_proposal()


def test_selection_key_must_match_reviewed_key() -> None:
    with pytest.raises(ValueError, match="strict key"):
        build_proposal(
            selection=TargetApplicationSelection(
                block_sequence=3,
                set_group_sequence=1,
                item_sequence=1,
            )
        )


def test_missing_coordinate_is_rejected() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        build_proposal(
            selection=TargetApplicationSelection(
                block_sequence=99,
                set_group_sequence=1,
                item_sequence=1,
            )
        )


def test_deferred_decision_is_rejected() -> None:
    with pytest.raises(ValueError, match="applicable prior decision"):
        build_proposal(
            reviewed_decision=build_reviewed_decision(RecalibratedTargetReviewAction.DEFER)
        )


def test_not_started_previous_result_is_rejected() -> None:
    with pytest.raises(ValueError, match="completed previous"):
        build_proposal(
            previous_result=build_previous_result(completion_status=CompletionStatus.NOT_STARTED)
        )


def test_safety_flagged_previous_result_is_rejected() -> None:
    with pytest.raises(ValueError, match="reported safety issue"):
        build_proposal(previous_result=build_previous_result(safety_issue_reported=True))


def test_conflicting_existing_target_is_rejected() -> None:
    parent = build_parent()
    workout = parent.workout
    block = workout.blocks[3]
    group = block.set_groups[0]
    item = group.items[0].model_copy(
        update={
            "target": Target(
                target_type=TargetType.REPETITION_COMPLETION_TIME,
                raw_value="1:04",
                target_seconds=64,
            )
        }
    )
    updated_group = group.model_copy(update={"items": (item,)})
    updated_block = block.model_copy(update={"set_groups": (updated_group,)})
    blocks = list(workout.blocks)
    blocks[3] = updated_block
    conflicting_parent = parent.model_copy(
        update={"workout": workout.model_copy(update={"blocks": tuple(blocks)})}
    )

    with pytest.raises(ValueError, match="conflicting existing target"):
        build_proposal(parent_generated_workout=conflicting_parent)


def test_proposal_id_version_must_match() -> None:
    with pytest.raises(ValueError, match="Proposal ID version"):
        build_proposal(proposal_version=2)


def test_generated_workout_id_must_differ_from_parent() -> None:
    with pytest.raises(ValueError, match="new generated-workout ID"):
        build_proposal(generated_workout_id="GW_20260905_001_V1")
