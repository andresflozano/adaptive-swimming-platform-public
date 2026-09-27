from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from adaptive_swimming.domain.session_geometry import (
    MappedWorkoutPlan,
    SessionGeometry,
    SessionGeometryReviewStatus,
)


class LengthCountObservationSource(StrEnum):
    MANUAL = "MANUAL"
    DEVICE = "DEVICE"
    OTHER = "OTHER"


class SourceDisagreementStatus(StrEnum):
    NO_OBSERVATIONS = "NO_OBSERVATIONS"
    SINGLE_SOURCE = "SINGLE_SOURCE"
    AGREEMENT = "AGREEMENT"
    DISAGREEMENT = "DISAGREEMENT"


class GeometryReconciliationReviewStatus(StrEnum):
    PENDING = "PENDING"
    REVIEWED = "REVIEWED"


@dataclass(frozen=True, slots=True)
class LengthCountObservation:
    source: LengthCountObservationSource
    observed_length_count: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.observed_length_count, bool)
            or not isinstance(self.observed_length_count, int)
            or self.observed_length_count < 0
        ):
            raise ValueError(
                "Observed length count must be a non-negative integer"
            )


@dataclass(frozen=True, slots=True)
class ReviewedCompletedLengthCount:
    completed_length_count: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.completed_length_count, bool)
            or not isinstance(self.completed_length_count, int)
            or self.completed_length_count < 0
        ):
            raise ValueError(
                "Reviewed completed length count must be "
                "a non-negative integer"
            )


@dataclass(frozen=True, slots=True)
class GeometryReconciliation:
    source_observations: tuple[LengthCountObservation, ...]
    source_disagreement_status: SourceDisagreementStatus
    planned_distance_m: Decimal
    mapped_planned_length_count: int
    mapped_planned_distance_m: Decimal
    actual_pool_length_m: Decimal
    reviewed_completed_length_count: int
    actual_distance_m: Decimal
    planned_vs_actual_error_m: Decimal
    mapped_vs_actual_error_m: Decimal
    review_status: GeometryReconciliationReviewStatus = (
        GeometryReconciliationReviewStatus.PENDING
    )

    @classmethod
    def from_reviewed_count(
        cls,
        *,
        mapped_plan: MappedWorkoutPlan,
        session_geometry: SessionGeometry,
        reviewed_count: ReviewedCompletedLengthCount,
        source_observations: Iterable[LengthCountObservation] = (),
        review_status: GeometryReconciliationReviewStatus = (
            GeometryReconciliationReviewStatus.PENDING
        ),
    ) -> "GeometryReconciliation":
        if (
            session_geometry.review_status
            is not SessionGeometryReviewStatus.REVIEWED
        ):
            raise ValueError(
                "Geometry reconciliation requires reviewed session geometry"
            )

        normalized_observations = tuple(source_observations)
        source_disagreement_status = _source_disagreement_status(
            normalized_observations
        )
        actual_pool_length_m = (
            session_geometry.pool_geometry.physical_length_m
        )

        if any(
            step.pool_length_m != actual_pool_length_m
            for step in mapped_plan.steps
        ):
            raise ValueError(
                "Mapped workout plan pool length must match "
                "reviewed session geometry"
            )

        mapped_planned_length_count = sum(
            step.selected_length_count for step in mapped_plan.steps
        )
        actual_distance_m = (
            Decimal(reviewed_count.completed_length_count)
            * actual_pool_length_m
        )

        return cls(
            source_observations=normalized_observations,
            source_disagreement_status=source_disagreement_status,
            planned_distance_m=mapped_plan.planned_distance_m,
            mapped_planned_length_count=mapped_planned_length_count,
            mapped_planned_distance_m=mapped_plan.mapped_distance_m,
            actual_pool_length_m=actual_pool_length_m,
            reviewed_completed_length_count=(
                reviewed_count.completed_length_count
            ),
            actual_distance_m=actual_distance_m,
            planned_vs_actual_error_m=(
                actual_distance_m - mapped_plan.planned_distance_m
            ),
            mapped_vs_actual_error_m=(
                actual_distance_m - mapped_plan.mapped_distance_m
            ),
            review_status=review_status,
        )


def _source_disagreement_status(
    observations: tuple[LengthCountObservation, ...],
) -> SourceDisagreementStatus:
    if not observations:
        return SourceDisagreementStatus.NO_OBSERVATIONS

    if len(observations) == 1:
        return SourceDisagreementStatus.SINGLE_SOURCE

    distinct_counts = {
        observation.observed_length_count
        for observation in observations
    }
    if len(distinct_counts) == 1:
        return SourceDisagreementStatus.AGREEMENT

    return SourceDisagreementStatus.DISAGREEMENT
