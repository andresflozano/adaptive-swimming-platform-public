from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from adaptive_swimming.domain.session_results import (
    GeneratedWorkout,
)
from adaptive_swimming.domain.workout import StrictDomainModel


class TimeFeasibilityStatus(StrEnum):
    NOT_PROVIDED = "NOT_PROVIDED"
    EXCEEDS_AVAILABLE_KNOWN_TIME = "EXCEEDS_AVAILABLE_KNOWN_TIME"
    UNRESOLVED = "UNRESOLVED"
    FITS_KNOWN_TIME = "FITS_KNOWN_TIME"


class WorkoutTimeFeasibility(StrictDomainModel):
    available_seconds: int | None = Field(
        default=None,
        gt=0,
    )
    known_swim_seconds: int = Field(ge=0)
    configured_rest_seconds: int = Field(ge=0)
    known_required_seconds: int = Field(ge=0)
    remaining_after_known_seconds: int | None = None
    unresolved_distance_meters: int = Field(ge=0)
    status: TimeFeasibilityStatus


def evaluate_time_feasibility(
    generated_workout: GeneratedWorkout,
) -> WorkoutTimeFeasibility:
    known_swim_seconds = generated_workout.known_swim_seconds
    configured_rest_seconds = generated_workout.configured_rest_seconds
    known_required_seconds = known_swim_seconds + configured_rest_seconds
    unresolved_distance = generated_workout.unresolved_distance_meters
    available_seconds = generated_workout.available_training_seconds

    if available_seconds is None:
        return WorkoutTimeFeasibility(
            available_seconds=None,
            known_swim_seconds=known_swim_seconds,
            configured_rest_seconds=configured_rest_seconds,
            known_required_seconds=known_required_seconds,
            remaining_after_known_seconds=None,
            unresolved_distance_meters=unresolved_distance,
            status=TimeFeasibilityStatus.NOT_PROVIDED,
        )

    remaining_seconds = available_seconds - known_required_seconds

    if remaining_seconds < 0:
        status = TimeFeasibilityStatus.EXCEEDS_AVAILABLE_KNOWN_TIME
    elif unresolved_distance > 0:
        status = TimeFeasibilityStatus.UNRESOLVED
    else:
        status = TimeFeasibilityStatus.FITS_KNOWN_TIME

    return WorkoutTimeFeasibility(
        available_seconds=available_seconds,
        known_swim_seconds=known_swim_seconds,
        configured_rest_seconds=configured_rest_seconds,
        known_required_seconds=known_required_seconds,
        remaining_after_known_seconds=remaining_seconds,
        unresolved_distance_meters=unresolved_distance,
        status=status,
    )
