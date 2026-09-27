from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from adaptive_swimming.domain.pool_geometry import (
    ExecutionMapping,
    ExecutionMappingPolicy,
    MappingStatus,
    PoolGeometry,
)


class SessionGeometryReviewStatus(StrEnum):
    PENDING = "PENDING"
    REVIEWED = "REVIEWED"


@dataclass(frozen=True, slots=True)
class SessionGeometry:
    pool_geometry: PoolGeometry
    mapping_policy: ExecutionMappingPolicy
    review_status: SessionGeometryReviewStatus = (
        SessionGeometryReviewStatus.PENDING
    )


@dataclass(frozen=True, slots=True)
class MappedWorkoutStep:
    target_distance_m: Decimal
    pool_length_m: Decimal
    selected_length_count: int
    mapped_distance_m: Decimal
    signed_error_m: Decimal
    absolute_error_m: Decimal
    absolute_error_pct: Decimal
    mapping_status: MappingStatus

    @classmethod
    def from_execution_mapping(
        cls,
        mapping: ExecutionMapping,
    ) -> "MappedWorkoutStep":
        return cls(
            target_distance_m=mapping.target_distance_m,
            pool_length_m=mapping.pool_length_m,
            selected_length_count=mapping.selected_length_count,
            mapped_distance_m=mapping.mapped_distance_m,
            signed_error_m=mapping.signed_error_m,
            absolute_error_m=mapping.absolute_error_m,
            absolute_error_pct=mapping.absolute_error_pct,
            mapping_status=mapping.mapping_status,
        )


@dataclass(frozen=True, slots=True)
class MappedWorkoutPlan:
    steps: tuple[MappedWorkoutStep, ...]
    planned_distance_m: Decimal
    mapped_distance_m: Decimal
    total_signed_error_m: Decimal
    absolute_net_error_m: Decimal
    aggregate_absolute_step_error_m: Decimal

    @classmethod
    def from_steps(
        cls,
        steps: Iterable[MappedWorkoutStep],
    ) -> "MappedWorkoutPlan":
        normalized_steps = tuple(steps)

        if not normalized_steps:
            raise ValueError("Mapped workout plan requires at least one step")

        planned_distance_m = sum(
            (step.target_distance_m for step in normalized_steps),
            start=Decimal("0"),
        )
        mapped_distance_m = sum(
            (step.mapped_distance_m for step in normalized_steps),
            start=Decimal("0"),
        )
        total_signed_error_m = sum(
            (step.signed_error_m for step in normalized_steps),
            start=Decimal("0"),
        )
        aggregate_absolute_step_error_m = sum(
            (step.absolute_error_m for step in normalized_steps),
            start=Decimal("0"),
        )

        return cls(
            steps=normalized_steps,
            planned_distance_m=planned_distance_m,
            mapped_distance_m=mapped_distance_m,
            total_signed_error_m=total_signed_error_m,
            absolute_net_error_m=abs(total_signed_error_m),
            aggregate_absolute_step_error_m=(
                aggregate_absolute_step_error_m
            ),
        )
