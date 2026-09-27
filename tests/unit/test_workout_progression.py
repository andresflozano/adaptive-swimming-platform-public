from __future__ import annotations

from adaptive_swimming.domain.session_results import GeneratedWorkout
from adaptive_swimming.domain.workout import Target, TargetType
from adaptive_swimming.planning.workout_progression import (
    WorkoutChangeCategory,
    WorkoutProgressionObjective,
    compare_workout_progression,
)
from tests.unit.test_configurable_workout_proposal import build_parent


def candidate_from_parent(parent: GeneratedWorkout) -> GeneratedWorkout:
    workout = parent.workout.model_copy(update={"session_id": "WT_ENGINE_NEXT_V1"})
    return parent.model_copy(
        update={
            "generated_workout_id": "GW_20261001_007_V1",
            "generation_reason": "SYNTHETIC_CANDIDATE",
            "workout": workout,
        }
    )


def replace_item(
    generated: GeneratedWorkout,
    *,
    block_index: int,
    group_index: int,
    item_index: int,
    updates: dict[str, object],
) -> GeneratedWorkout:
    blocks = list(generated.workout.blocks)
    block = blocks[block_index]
    groups = list(block.set_groups)
    group = groups[group_index]
    items = list(group.items)
    items[item_index] = items[item_index].model_copy(update=updates)
    groups[group_index] = group.model_copy(update={"items": tuple(items)})
    blocks[block_index] = block.model_copy(update={"set_groups": tuple(groups)})
    workout = generated.workout.model_copy(update={"blocks": tuple(blocks)})
    return generated.model_copy(update={"workout": workout})


def test_identity_only_candidate_fails_adaptive_progression() -> None:
    parent = build_parent()
    candidate = candidate_from_parent(parent)
    assessment = compare_workout_progression(
        parent=parent,
        candidate=candidate,
        objective=WorkoutProgressionObjective.ADAPTIVE_PROGRESSION,
    )
    assert not assessment.satisfies_objective
    assert assessment.structural_changes == ()
    assert assessment.metadata_changes


def test_target_only_candidate_fails_adaptive_progression() -> None:
    parent = build_parent()
    candidate = replace_item(
        candidate_from_parent(parent),
        block_index=3,
        group_index=0,
        item_index=0,
        updates={
            "target": Target(
                target_type=TargetType.REPETITION_COMPLETION_TIME,
                raw_value="1:04",
                target_seconds=64,
            )
        },
    )
    assessment = compare_workout_progression(
        parent=parent,
        candidate=candidate,
        objective=WorkoutProgressionObjective.ADAPTIVE_PROGRESSION,
    )
    assert not assessment.satisfies_objective
    assert len(assessment.target_changes) == 1
    assert assessment.structural_changes == ()


def test_repetition_change_passes_adaptive_progression() -> None:
    parent = build_parent()
    candidate = replace_item(
        candidate_from_parent(parent),
        block_index=3,
        group_index=0,
        item_index=0,
        updates={"repetitions": 5},
    )
    assessment = compare_workout_progression(
        parent=parent,
        candidate=candidate,
        objective=WorkoutProgressionObjective.ADAPTIVE_PROGRESSION,
    )
    assert assessment.satisfies_objective
    assert any(change.field == "repetitions" for change in assessment.structural_changes)


def test_distance_change_passes_adaptive_progression() -> None:
    parent = build_parent()
    candidate = replace_item(
        candidate_from_parent(parent),
        block_index=4,
        group_index=0,
        item_index=0,
        updates={"distance_meters": 50},
    )
    assessment = compare_workout_progression(
        parent=parent,
        candidate=candidate,
        objective=WorkoutProgressionObjective.ADAPTIVE_PROGRESSION,
    )
    assert assessment.satisfies_objective
    assert any(change.field == "distance_meters" for change in assessment.structural_changes)


def test_rest_change_passes_adaptive_progression() -> None:
    parent = build_parent()
    candidate = candidate_from_parent(parent)
    blocks = list(candidate.workout.blocks)
    group = blocks[3].set_groups[0]
    assert group.rest is not None
    changed_rest = group.rest.model_copy(update={"seconds": 25})
    changed_group = group.model_copy(update={"rest": changed_rest})
    blocks[3] = blocks[3].model_copy(update={"set_groups": (changed_group,)})
    candidate = candidate.model_copy(
        update={"workout": candidate.workout.model_copy(update={"blocks": tuple(blocks)})}
    )
    assessment = compare_workout_progression(
        parent=parent,
        candidate=candidate,
        objective=WorkoutProgressionObjective.ADAPTIVE_PROGRESSION,
    )
    assert assessment.satisfies_objective
    assert any(change.field == "rest" for change in assessment.structural_changes)


def test_repeatability_accepts_same_structure() -> None:
    parent = build_parent()
    assessment = compare_workout_progression(
        parent=parent,
        candidate=candidate_from_parent(parent),
        objective=WorkoutProgressionObjective.REPEATABILITY,
    )
    assert assessment.satisfies_objective


def test_repeatability_rejects_structural_change() -> None:
    parent = build_parent()
    candidate = replace_item(
        candidate_from_parent(parent),
        block_index=3,
        group_index=0,
        item_index=0,
        updates={"repetitions": 5},
    )
    assessment = compare_workout_progression(
        parent=parent,
        candidate=candidate,
        objective=WorkoutProgressionObjective.REPEATABILITY,
    )
    assert not assessment.satisfies_objective


def test_change_records_are_categorized_and_round_trip() -> None:
    parent = build_parent()
    candidate = replace_item(
        candidate_from_parent(parent),
        block_index=3,
        group_index=0,
        item_index=0,
        updates={"repetitions": 5},
    )
    assessment = compare_workout_progression(
        parent=parent,
        candidate=candidate,
        objective=WorkoutProgressionObjective.ADAPTIVE_PROGRESSION,
    )
    assert all(
        change.category == WorkoutChangeCategory.STRUCTURAL
        for change in assessment.structural_changes
    )
    assert assessment.model_validate_json(assessment.model_dump_json()) == assessment


def test_source_text_and_instruction_do_not_count_as_structural() -> None:
    parent = build_parent()
    candidate = replace_item(
        candidate_from_parent(parent),
        block_index=3,
        group_index=0,
        item_index=0,
        updates={
            "source_text": "Engine proposal: rewritten text",
            "swimmer_instruction": "Rewritten instruction.",
        },
    )
    assessment = compare_workout_progression(
        parent=parent,
        candidate=candidate,
        objective=WorkoutProgressionObjective.ADAPTIVE_PROGRESSION,
    )
    assert not assessment.satisfies_objective
    assert assessment.structural_changes == ()
