from decimal import Decimal

import pytest

from adaptive_swimming.domain.pool_geometry import (
    ExecutionMappingPolicy,
    MappingStatus,
    map_distance_to_lengths,
)


def test_exact_mapping_100m_12_5m_pool() -> None:
    result = map_distance_to_lengths(
        target_distance_m=Decimal("100"),
        pool_length_m=Decimal("12.5"),
    )

    assert result.selected_length_count == 8
    assert result.mapping_status is MappingStatus.EXACT


def test_exact_mapping_100m_25m_pool() -> None:
    result = map_distance_to_lengths(
        target_distance_m=Decimal("100"),
        pool_length_m=Decimal("25"),
    )

    assert result.selected_length_count == 4


def test_exact_mapping_100m_50m_pool() -> None:
    result = map_distance_to_lengths(
        target_distance_m=Decimal("100"),
        pool_length_m=Decimal("50"),
    )

    assert result.selected_length_count == 2


def test_100m_in_13m_pool() -> None:
    result = map_distance_to_lengths(
        target_distance_m=Decimal("100"),
        pool_length_m=Decimal("13"),
    )

    assert result.selected_length_count == 8
    assert result.mapping_status is MappingStatus.APPROXIMATED


def test_100m_in_18m_pool() -> None:
    result = map_distance_to_lengths(
        target_distance_m=Decimal("100"),
        pool_length_m=Decimal("18"),
    )

    assert result.selected_length_count == 6


def test_75m_in_18m_pool() -> None:
    result = map_distance_to_lengths(
        target_distance_m=Decimal("75"),
        pool_length_m=Decimal("18"),
    )

    assert result.selected_length_count == 4


@pytest.mark.parametrize(
    ("distance", "pool"),
    [
        (Decimal("0"), Decimal("25")),
        (Decimal("-1"), Decimal("25")),
        (Decimal("100"), Decimal("0")),
        (Decimal("100"), Decimal("-1")),
    ],
)
def test_invalid_inputs_raise(
    distance: Decimal,
    pool: Decimal,
) -> None:
    with pytest.raises(ValueError):
        map_distance_to_lengths(
            target_distance_m=distance,
            pool_length_m=pool,
            policy=ExecutionMappingPolicy.CLOSEST,
        )

@pytest.mark.parametrize(
    ("distance", "pool"),
    [
        (Decimal("NaN"), Decimal("25")),
        (Decimal("Infinity"), Decimal("25")),
        (Decimal("100"), Decimal("NaN")),
        (Decimal("100"), Decimal("Infinity")),
    ],
)
def test_non_finite_inputs_raise(
    distance: Decimal,
    pool: Decimal,
) -> None:
    with pytest.raises(ValueError):
        map_distance_to_lengths(
            target_distance_m=distance,
            pool_length_m=pool,
        )


def test_equal_error_selects_higher_length_count() -> None:
    result = map_distance_to_lengths(
        target_distance_m=Decimal("15"),
        pool_length_m=Decimal("10"),
    )

    assert result.selected_length_count == 2