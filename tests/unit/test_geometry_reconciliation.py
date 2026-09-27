from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from adaptive_swimming.domain.geometry_reconciliation import (
    GeometryReconciliation,
    GeometryReconciliationReviewStatus,
    LengthCountObservation,
    LengthCountObservationSource,
    ReviewedCompletedLengthCount,
    SourceDisagreementStatus,
)
from adaptive_swimming.domain.pool_geometry import (
    ExecutionMappingPolicy,
    PoolGeometry,
    PoolMeasurementMethod,
    PoolMeasurementStatus,
    map_distance_to_lengths,
)
from adaptive_swimming.domain.session_geometry import (
    MappedWorkoutPlan,
    MappedWorkoutStep,
    SessionGeometry,
    SessionGeometryReviewStatus,
)


def _session_geometry(
    pool_length_m: str,
    *,
    reviewed: bool = True,
) -> SessionGeometry:
    return SessionGeometry(
        pool_geometry=PoolGeometry(
            physical_length_m=Decimal(pool_length_m),
            measurement_method=(
                PoolMeasurementMethod.PHYSICAL_MEASUREMENT
            ),
            measurement_status=PoolMeasurementStatus.VERIFIED,
        ),
        mapping_policy=ExecutionMappingPolicy.CLOSEST,
        review_status=(
            SessionGeometryReviewStatus.REVIEWED
            if reviewed
            else SessionGeometryReviewStatus.PENDING
        ),
    )


def _mapped_plan(
    pool_length_m: str,
    *target_distances_m: str,
) -> MappedWorkoutPlan:
    steps = tuple(
        MappedWorkoutStep.from_execution_mapping(
            map_distance_to_lengths(
                target_distance_m=Decimal(target_distance_m),
                pool_length_m=Decimal(pool_length_m),
            )
        )
        for target_distance_m in target_distances_m
    )
    return MappedWorkoutPlan.from_steps(steps)


def test_manual_only_reconciliation_derives_actual_distance() -> None:
    observation = LengthCountObservation(
        source=LengthCountObservationSource.MANUAL,
        observed_length_count=10,
    )
    reconciliation = GeometryReconciliation.from_reviewed_count(
        mapped_plan=_mapped_plan("18", "100", "75"),
        session_geometry=_session_geometry("18"),
        reviewed_count=ReviewedCompletedLengthCount(10),
        source_observations=(observation,),
    )

    assert reconciliation.source_observations == (observation,)
    assert (
        reconciliation.source_disagreement_status
        is SourceDisagreementStatus.SINGLE_SOURCE
    )
    assert reconciliation.planned_distance_m == Decimal("175")
    assert reconciliation.mapped_planned_length_count == 10
    assert reconciliation.mapped_planned_distance_m == Decimal("180")
    assert reconciliation.actual_pool_length_m == Decimal("18")
    assert reconciliation.reviewed_completed_length_count == 10
    assert reconciliation.actual_distance_m == Decimal("180")
    assert reconciliation.planned_vs_actual_error_m == Decimal("5")
    assert reconciliation.mapped_vs_actual_error_m == Decimal("0")
    assert (
        reconciliation.review_status
        is GeometryReconciliationReviewStatus.PENDING
    )


def test_manual_and_device_observations_can_agree() -> None:
    reconciliation = GeometryReconciliation.from_reviewed_count(
        mapped_plan=_mapped_plan("18", "100"),
        session_geometry=_session_geometry("18"),
        reviewed_count=ReviewedCompletedLengthCount(6),
        source_observations=(
            LengthCountObservation(
                source=LengthCountObservationSource.MANUAL,
                observed_length_count=6,
            ),
            LengthCountObservation(
                source=LengthCountObservationSource.DEVICE,
                observed_length_count=6,
            ),
        ),
    )

    assert (
        reconciliation.source_disagreement_status
        is SourceDisagreementStatus.AGREEMENT
    )


def test_manual_and_device_disagreement_remains_explicit() -> None:
    observations = (
        LengthCountObservation(
            source=LengthCountObservationSource.MANUAL,
            observed_length_count=6,
        ),
        LengthCountObservation(
            source=LengthCountObservationSource.DEVICE,
            observed_length_count=5,
        ),
    )
    reconciliation = GeometryReconciliation.from_reviewed_count(
        mapped_plan=_mapped_plan("18", "100"),
        session_geometry=_session_geometry("18"),
        reviewed_count=ReviewedCompletedLengthCount(6),
        source_observations=observations,
    )

    assert reconciliation.source_observations == observations
    assert (
        reconciliation.source_disagreement_status
        is SourceDisagreementStatus.DISAGREEMENT
    )
    assert reconciliation.reviewed_completed_length_count == 6
    assert observations[1].observed_length_count == 5


def test_reconciliation_does_not_require_source_observations() -> None:
    reconciliation = GeometryReconciliation.from_reviewed_count(
        mapped_plan=_mapped_plan("25", "100"),
        session_geometry=_session_geometry("25"),
        reviewed_count=ReviewedCompletedLengthCount(4),
    )

    assert reconciliation.source_observations == ()
    assert (
        reconciliation.source_disagreement_status
        is SourceDisagreementStatus.NO_OBSERVATIONS
    )
    assert reconciliation.actual_distance_m == Decimal("100")


def test_reconciliation_requires_reviewed_session_geometry() -> None:
    with pytest.raises(
        ValueError,
        match="requires reviewed session geometry",
    ):
        GeometryReconciliation.from_reviewed_count(
            mapped_plan=_mapped_plan("18", "100"),
            session_geometry=_session_geometry("18", reviewed=False),
            reviewed_count=ReviewedCompletedLengthCount(6),
        )


@pytest.mark.parametrize("invalid_count", (-1, True, Decimal("1")))
def test_length_count_observation_rejects_invalid_count(
    invalid_count: object,
) -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        LengthCountObservation(
            source=LengthCountObservationSource.MANUAL,
            observed_length_count=invalid_count,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("invalid_count", (-1, True, Decimal("1")))
def test_reviewed_completed_count_rejects_invalid_count(
    invalid_count: object,
) -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        ReviewedCompletedLengthCount(
            completed_length_count=invalid_count,  # type: ignore[arg-type]
        )


def test_same_workout_reconciles_using_each_session_pool() -> None:
    short_pool_reconciliation = GeometryReconciliation.from_reviewed_count(
        mapped_plan=_mapped_plan("12.5", "100"),
        session_geometry=_session_geometry("12.5"),
        reviewed_count=ReviewedCompletedLengthCount(8),
    )
    long_pool_reconciliation = GeometryReconciliation.from_reviewed_count(
        mapped_plan=_mapped_plan("25", "100"),
        session_geometry=_session_geometry("25"),
        reviewed_count=ReviewedCompletedLengthCount(4),
    )

    assert short_pool_reconciliation.actual_pool_length_m == Decimal("12.5")
    assert long_pool_reconciliation.actual_pool_length_m == Decimal("25")
    assert short_pool_reconciliation.actual_distance_m == Decimal("100")
    assert long_pool_reconciliation.actual_distance_m == Decimal("100")


def test_reconciliation_is_immutable() -> None:
    reconciliation = GeometryReconciliation.from_reviewed_count(
        mapped_plan=_mapped_plan("18", "100"),
        session_geometry=_session_geometry("18"),
        reviewed_count=ReviewedCompletedLengthCount(6),
    )
    attribute_name = "actual_distance_m"

    with pytest.raises(FrozenInstanceError):
        setattr(reconciliation, attribute_name, Decimal("0"))


def test_reconciliation_rejects_mapped_plan_from_different_pool() -> None:
    with pytest.raises(
        ValueError,
        match="pool length must match reviewed session geometry",
    ):
        GeometryReconciliation.from_reviewed_count(
            mapped_plan=_mapped_plan("18", "100"),
            session_geometry=_session_geometry("25"),
            reviewed_count=ReviewedCompletedLengthCount(4),
        )
