from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from adaptive_swimming.domain.pool_geometry import (
    ExecutionMappingPolicy,
    PoolGeometry,
    PoolMeasurementMethod,
    PoolMeasurementStatus,
)
from adaptive_swimming.domain.session_geometry import (
    SessionGeometry,
    SessionGeometryReviewStatus,
)


def test_session_geometry_defaults_to_pending() -> None:
    geometry = PoolGeometry(
        physical_length_m=Decimal("12.5"),
        measurement_method=PoolMeasurementMethod.PHYSICAL_MEASUREMENT,
        measurement_status=PoolMeasurementStatus.VERIFIED,
    )

    session_geometry = SessionGeometry(
        pool_geometry=geometry,
        mapping_policy=ExecutionMappingPolicy.CLOSEST,
    )

    assert (
        session_geometry.review_status
        is SessionGeometryReviewStatus.PENDING
    )


def test_session_geometry_can_be_explicitly_reviewed() -> None:
    geometry = PoolGeometry(
        physical_length_m=Decimal("18"),
        measurement_method=PoolMeasurementMethod.PHYSICAL_MEASUREMENT,
        measurement_status=PoolMeasurementStatus.VERIFIED,
    )

    session_geometry = SessionGeometry(
        pool_geometry=geometry,
        mapping_policy=ExecutionMappingPolicy.CLOSEST,
        review_status=SessionGeometryReviewStatus.REVIEWED,
    )

    assert (
        session_geometry.review_status
        is SessionGeometryReviewStatus.REVIEWED
    )


def test_session_geometry_is_immutable() -> None:
    geometry = PoolGeometry(
        physical_length_m=Decimal("25"),
        measurement_method=PoolMeasurementMethod.PHYSICAL_MEASUREMENT,
        measurement_status=PoolMeasurementStatus.VERIFIED,
    )
    session_geometry = SessionGeometry(
        pool_geometry=geometry,
        mapping_policy=ExecutionMappingPolicy.CLOSEST,
    )

    attribute_name = "review_status"

    with pytest.raises(FrozenInstanceError):
        setattr(
            session_geometry,
            attribute_name,
            SessionGeometryReviewStatus.REVIEWED,
        )
