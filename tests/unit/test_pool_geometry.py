from decimal import Decimal

import pytest

from adaptive_swimming.domain.pool_geometry import (
    PoolGeometry,
    PoolMeasurementMethod,
    PoolMeasurementStatus,
)


def test_pool_geometry_accepts_positive_length() -> None:
    geometry = PoolGeometry(
        physical_length_m=Decimal("12.5"),
        measurement_method=PoolMeasurementMethod.PHYSICAL_MEASUREMENT,
        measurement_status=PoolMeasurementStatus.VERIFIED,
    )

    assert geometry.physical_length_m == Decimal("12.5")


@pytest.mark.parametrize(
    "length",
    [
        Decimal("0"),
        Decimal("-1"),
    ],
)
def test_pool_geometry_rejects_non_positive_length(
    length: Decimal,
) -> None:
    with pytest.raises(ValueError):
        PoolGeometry(
            physical_length_m=length,
            measurement_method=PoolMeasurementMethod.UNKNOWN,
            measurement_status=PoolMeasurementStatus.UNKNOWN,
        )


@pytest.mark.parametrize(
    "length",
    [
        Decimal("NaN"),
        Decimal("Infinity"),
    ],
)
def test_pool_geometry_rejects_non_finite_length(
    length: Decimal,
) -> None:
    with pytest.raises(ValueError):
        PoolGeometry(
            physical_length_m=length,
            measurement_method=PoolMeasurementMethod.UNKNOWN,
            measurement_status=PoolMeasurementStatus.UNKNOWN,
        )