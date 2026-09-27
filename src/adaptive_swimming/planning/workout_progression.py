from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from adaptive_swimming.domain.session_results import GeneratedWorkout
from adaptive_swimming.domain.workout import StrictDomainModel


class WorkoutProgressionObjective(StrEnum):
    REPEATABILITY = "REPEATABILITY"
    ADAPTIVE_PROGRESSION = "ADAPTIVE_PROGRESSION"


class WorkoutChangeCategory(StrEnum):
    STRUCTURAL = "STRUCTURAL"
    TARGET = "TARGET"
    METADATA = "METADATA"


class WorkoutChange(StrictDomainModel):
    category: WorkoutChangeCategory
    path: str = Field(min_length=1)
    field: str = Field(min_length=1)
    parent_value: Any
    candidate_value: Any


class WorkoutProgressionAssessment(StrictDomainModel):
    objective: WorkoutProgressionObjective
    structural_changes: tuple[WorkoutChange, ...]
    target_changes: tuple[WorkoutChange, ...]
    metadata_changes: tuple[WorkoutChange, ...]
    satisfies_objective: bool
    reasons: tuple[str, ...] = Field(min_length=1)


STRUCTURAL_ITEM_FIELDS = (
    "repetitions",
    "distance_meters",
    "exercise",
    "intensity",
    "equipment",
)

STRUCTURAL_GROUP_FIELDS = (
    "set_type",
    "repeat_cycles",
    "rest",
)


def _json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, tuple):
        return [getattr(item, "value", item) for item in value]
    return getattr(value, "value", value)


def _append_change(
    changes: list[WorkoutChange],
    *,
    category: WorkoutChangeCategory,
    path: str,
    field: str,
    parent_value: Any,
    candidate_value: Any,
) -> None:
    if parent_value == candidate_value:
        return
    changes.append(
        WorkoutChange(
            category=category,
            path=path,
            field=field,
            parent_value=_json_value(parent_value),
            candidate_value=_json_value(candidate_value),
        )
    )


def compare_workout_progression(
    *,
    parent: GeneratedWorkout,
    candidate: GeneratedWorkout,
    objective: WorkoutProgressionObjective,
) -> WorkoutProgressionAssessment:
    structural: list[WorkoutChange] = []
    targets: list[WorkoutChange] = []
    metadata: list[WorkoutChange] = []

    _append_change(
        metadata,
        category=WorkoutChangeCategory.METADATA,
        path="generated_workout",
        field="generated_workout_id",
        parent_value=parent.generated_workout_id,
        candidate_value=candidate.generated_workout_id,
    )
    for field in (
        "generation_reason",
        "available_training_seconds",
        "pool_length_meters",
        "equipment_available",
    ):
        _append_change(
            metadata,
            category=WorkoutChangeCategory.METADATA,
            path="generated_workout",
            field=field,
            parent_value=getattr(parent, field),
            candidate_value=getattr(candidate, field),
        )

    for field in ("session_id", "environment", "source_id", "source_sha256"):
        _append_change(
            metadata,
            category=WorkoutChangeCategory.METADATA,
            path="workout",
            field=field,
            parent_value=getattr(parent.workout, field),
            candidate_value=getattr(candidate.workout, field),
        )

    parent_blocks = {block.sequence: block for block in parent.workout.blocks}
    candidate_blocks = {block.sequence: block for block in candidate.workout.blocks}
    for sequence in sorted(set(parent_blocks) | set(candidate_blocks)):
        block_path = f"block[{sequence}]"
        parent_block = parent_blocks.get(sequence)
        candidate_block = candidate_blocks.get(sequence)
        if parent_block is None or candidate_block is None:
            _append_change(
                structural,
                category=WorkoutChangeCategory.STRUCTURAL,
                path=block_path,
                field="composition",
                parent_value=parent_block,
                candidate_value=candidate_block,
            )
            continue

        _append_change(
            structural,
            category=WorkoutChangeCategory.STRUCTURAL,
            path=block_path,
            field="role",
            parent_value=parent_block.role,
            candidate_value=candidate_block.role,
        )

        parent_groups = {group.sequence: group for group in parent_block.set_groups}
        candidate_groups = {group.sequence: group for group in candidate_block.set_groups}
        for group_sequence in sorted(set(parent_groups) | set(candidate_groups)):
            group_path = f"{block_path}.group[{group_sequence}]"
            parent_group = parent_groups.get(group_sequence)
            candidate_group = candidate_groups.get(group_sequence)
            if parent_group is None or candidate_group is None:
                _append_change(
                    structural,
                    category=WorkoutChangeCategory.STRUCTURAL,
                    path=group_path,
                    field="composition",
                    parent_value=parent_group,
                    candidate_value=candidate_group,
                )
                continue

            for field in STRUCTURAL_GROUP_FIELDS:
                _append_change(
                    structural,
                    category=WorkoutChangeCategory.STRUCTURAL,
                    path=group_path,
                    field=field,
                    parent_value=getattr(parent_group, field),
                    candidate_value=getattr(candidate_group, field),
                )

            parent_items = {item.sequence: item for item in parent_group.items}
            candidate_items = {item.sequence: item for item in candidate_group.items}
            for item_sequence in sorted(set(parent_items) | set(candidate_items)):
                item_path = f"{group_path}.item[{item_sequence}]"
                parent_item = parent_items.get(item_sequence)
                candidate_item = candidate_items.get(item_sequence)
                if parent_item is None or candidate_item is None:
                    _append_change(
                        structural,
                        category=WorkoutChangeCategory.STRUCTURAL,
                        path=item_path,
                        field="composition",
                        parent_value=parent_item,
                        candidate_value=candidate_item,
                    )
                    continue

                for field in STRUCTURAL_ITEM_FIELDS:
                    _append_change(
                        structural,
                        category=WorkoutChangeCategory.STRUCTURAL,
                        path=item_path,
                        field=field,
                        parent_value=getattr(parent_item, field),
                        candidate_value=getattr(candidate_item, field),
                    )
                _append_change(
                    targets,
                    category=WorkoutChangeCategory.TARGET,
                    path=item_path,
                    field="target",
                    parent_value=parent_item.target,
                    candidate_value=candidate_item.target,
                )

    if objective == WorkoutProgressionObjective.REPEATABILITY:
        satisfies = not structural
        reasons = (
            (
                "Repeatability permits identity, provenance, instruction, and target changes.",
                "Repeatability requires the workout structure to remain unchanged.",
            )
            if satisfies
            else ("Repeatability requires the workout structure to remain unchanged.",)
        )
    else:
        satisfies = bool(structural)
        reasons = (
            ("Adaptive progression contains at least one observed structural change.",)
            if satisfies
            else (
                "Adaptive progression requires a structural change; "
                "metadata-only and target-only changes are insufficient.",
            )
        )

    return WorkoutProgressionAssessment(
        objective=objective,
        structural_changes=tuple(structural),
        target_changes=tuple(targets),
        metadata_changes=tuple(metadata),
        satisfies_objective=satisfies,
        reasons=reasons,
    )
