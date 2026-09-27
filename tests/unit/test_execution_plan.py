from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from adaptive_swimming.domain.pool_geometry import (
    MappingStatus,
    map_distance_to_lengths,
)
from adaptive_swimming.domain.session_geometry import (
    MappedWorkoutPlan,
    MappedWorkoutStep,
)


def _mapped_step(
    target_distance_m: str,
    pool_length_m: str,
) -> MappedWorkoutStep:
    mapping = map_distance_to_lengths(
        target_distance_m=Decimal(target_distance_m),
        pool_length_m=Decimal(pool_length_m),
    )
    return MappedWorkoutStep.from_execution_mapping(mapping)


def test_mapped_step_preserves_approximated_mapping() -> None:
    step = _mapped_step("100", "18")

    assert step.target_distance_m == Decimal("100")
    assert step.pool_length_m == Decimal("18")
    assert step.selected_length_count == 6
    assert step.mapped_distance_m == Decimal("108")
    assert step.signed_error_m == Decimal("8")
    assert step.absolute_error_m == Decimal("8")
    assert step.absolute_error_pct == Decimal("8")
    assert step.mapping_status is MappingStatus.APPROXIMATED


def test_mapped_step_preserves_exact_mapping() -> None:
    step = _mapped_step("100", "12.5")

    assert step.target_distance_m == Decimal("100")
    assert step.pool_length_m == Decimal("12.5")
    assert step.selected_length_count == 8
    assert step.mapped_distance_m == Decimal("100")
    assert step.signed_error_m == Decimal("0")
    assert step.absolute_error_m == Decimal("0")
    assert step.absolute_error_pct == Decimal("0")
    assert step.mapping_status is MappingStatus.EXACT


def test_plan_aggregates_distances_and_errors() -> None:
    plan = MappedWorkoutPlan.from_steps(
        (
            _mapped_step("100", "18"),
            _mapped_step("75", "18"),
        )
    )

    assert plan.planned_distance_m == Decimal("175")
    assert plan.mapped_distance_m == Decimal("180")
    assert plan.total_signed_error_m == Decimal("5")
    assert plan.absolute_net_error_m == Decimal("5")
    assert plan.aggregate_absolute_step_error_m == Decimal("11")


def test_plan_preserves_approximation_when_signed_errors_cancel() -> None:
    plan = MappedWorkoutPlan.from_steps(
        (
            _mapped_step("100", "18"),
            _mapped_step("80", "18"),
        )
    )

    assert plan.total_signed_error_m == Decimal("0")
    assert plan.absolute_net_error_m == Decimal("0")
    assert plan.aggregate_absolute_step_error_m == Decimal("16")
    assert all(
        step.mapping_status is MappingStatus.APPROXIMATED
        for step in plan.steps
    )


def test_plan_normalizes_steps_to_immutable_tuple() -> None:
    source_steps = [_mapped_step("100", "18")]

    plan = MappedWorkoutPlan.from_steps(source_steps)
    source_steps.append(_mapped_step("75", "18"))

    assert isinstance(plan.steps, tuple)
    assert len(plan.steps) == 1

    attribute_name = "planned_distance_m"

    with pytest.raises(FrozenInstanceError):
        setattr(plan, attribute_name, Decimal("0"))


def test_plan_rejects_empty_step_collection() -> None:
    with pytest.raises(
        ValueError,
        match="requires at least one step",
    ):
        MappedWorkoutPlan.from_steps(())
