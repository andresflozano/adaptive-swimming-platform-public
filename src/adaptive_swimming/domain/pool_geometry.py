import math
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class PoolMeasurementMethod(StrEnum):
    PHYSICAL_MEASUREMENT = "PHYSICAL_MEASUREMENT"
    FACILITY_SPECIFICATION = "FACILITY_SPECIFICATION"
    REVIEWED_DOCUMENTATION = "REVIEWED_DOCUMENTATION"
    OPERATOR_DECLARATION = "OPERATOR_DECLARATION"
    ESTIMATE = "ESTIMATE"
    UNKNOWN = "UNKNOWN"


class PoolMeasurementStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PROVISIONAL = "PROVISIONAL"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"


class ExecutionMappingPolicy(StrEnum):
    CLOSEST = "CLOSEST"


class MappingStatus(StrEnum):
    EXACT = "EXACT"
    APPROXIMATED = "APPROXIMATED"


def _validate_positive_finite(
    value: Decimal,
    name: str,
) -> None:
    if value.is_nan():
        raise ValueError(f"{name} must not be NaN")

    if value.is_infinite():
        raise ValueError(f"{name} must be finite")

    if value <= Decimal("0"):
        raise ValueError(f"{name} must be positive")


@dataclass(frozen=True, slots=True)
class PoolGeometry:
    physical_length_m: Decimal
    measurement_method: PoolMeasurementMethod
    measurement_status: PoolMeasurementStatus

    def __post_init__(self) -> None:
        _validate_positive_finite(
            self.physical_length_m,
            "physical_length_m",
        )


@dataclass(frozen=True, slots=True)
class ExecutionMapping:
    target_distance_m: Decimal
    pool_length_m: Decimal

    selected_length_count: int

    mapped_distance_m: Decimal

    signed_error_m: Decimal
    absolute_error_m: Decimal
    absolute_error_pct: Decimal

    mapping_status: MappingStatus


def map_distance_to_lengths(
    *,
    target_distance_m: Decimal,
    pool_length_m: Decimal,
    policy: ExecutionMappingPolicy = ExecutionMappingPolicy.CLOSEST,
) -> ExecutionMapping:
    _validate_positive_finite(
        target_distance_m,
        "target_distance_m",
    )

    _validate_positive_finite(
        pool_length_m,
        "pool_length_m",
    )

    if policy is not ExecutionMappingPolicy.CLOSEST:
        raise ValueError(f"Unsupported policy: {policy}")

    ratio = target_distance_m / pool_length_m

    lower = max(1, math.floor(ratio))
    upper = max(1, math.ceil(ratio))

    if lower == upper:
        selected = lower
    else:
        lower_distance = Decimal(lower) * pool_length_m
        upper_distance = Decimal(upper) * pool_length_m

        lower_error = abs(lower_distance - target_distance_m)
        upper_error = abs(upper_distance - target_distance_m)

        if lower_error < upper_error:
            selected = lower
        else:
            selected = upper

    mapped = Decimal(selected) * pool_length_m

    signed_error = mapped - target_distance_m
    absolute_error = abs(signed_error)
    absolute_error_pct = (
        absolute_error / target_distance_m * Decimal("100")
    )

    status = (
        MappingStatus.EXACT
        if absolute_error == Decimal("0")
        else MappingStatus.APPROXIMATED
    )

    return ExecutionMapping(
        target_distance_m=target_distance_m,
        pool_length_m=pool_length_m,
        selected_length_count=selected,
        mapped_distance_m=mapped,
        signed_error_m=signed_error,
        absolute_error_m=absolute_error,
        absolute_error_pct=absolute_error_pct,
        mapping_status=status,
    )