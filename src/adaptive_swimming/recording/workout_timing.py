from __future__ import annotations

from statistics import mean, median

from pydantic import Field, model_validator

from adaptive_swimming.domain.workout import StrictDomainModel


class ElapsedRepetitionReading(StrictDomainModel):
    repetition_number: int = Field(ge=1)
    finish_elapsed_seconds: int = Field(gt=0)
    rest_before_seconds: int = Field(default=0, ge=0)
    note: str | None = None


class ItemTimingCapture(StrictDomainModel):
    block_sequence: int = Field(ge=1)
    set_group_sequence: int = Field(ge=1)
    item_sequence: int = Field(ge=1)
    block_start_elapsed_seconds: int = Field(ge=0)
    readings: tuple[ElapsedRepetitionReading, ...] = Field(min_length=1)
    target_seconds: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_readings(self) -> ItemTimingCapture:
        repetition_numbers = tuple(reading.repetition_number for reading in self.readings)
        expected_numbers = tuple(range(1, len(self.readings) + 1))

        if repetition_numbers != expected_numbers:
            raise ValueError("Repetition numbers must be consecutive and start at 1.")

        if self.readings[0].rest_before_seconds != 0:
            raise ValueError("The first repetition cannot have rest before it.")

        previous_elapsed = self.block_start_elapsed_seconds
        for reading in self.readings:
            if reading.finish_elapsed_seconds <= previous_elapsed:
                raise ValueError("Finish elapsed readings must increase strictly.")

            calculated_seconds = (
                reading.finish_elapsed_seconds - previous_elapsed - reading.rest_before_seconds
            )
            if calculated_seconds <= 0:
                raise ValueError("Calculated repetition duration must be positive.")

            previous_elapsed = reading.finish_elapsed_seconds

        return self


class CalculatedRepetitionTiming(StrictDomainModel):
    block_sequence: int = Field(ge=1)
    set_group_sequence: int = Field(ge=1)
    item_sequence: int = Field(ge=1)
    repetition_number: int = Field(ge=1)
    previous_elapsed_seconds: int = Field(ge=0)
    finish_elapsed_seconds: int = Field(gt=0)
    rest_before_seconds: int = Field(ge=0)
    actual_seconds: int = Field(gt=0)
    target_seconds: int | None = Field(default=None, gt=0)
    target_met: bool | None = None
    formula: str = Field(min_length=1)
    note: str | None = None


class ItemTimingSummary(StrictDomainModel):
    block_sequence: int = Field(ge=1)
    set_group_sequence: int = Field(ge=1)
    item_sequence: int = Field(ge=1)
    block_start_elapsed_seconds: int = Field(ge=0)
    block_finish_elapsed_seconds: int = Field(gt=0)
    repetitions: tuple[CalculatedRepetitionTiming, ...] = Field(min_length=1)
    active_seconds: int = Field(gt=0)
    rest_seconds: int = Field(ge=0)
    captured_elapsed_seconds: int = Field(gt=0)
    fastest_seconds: int = Field(gt=0)
    slowest_seconds: int = Field(gt=0)
    mean_seconds: float = Field(gt=0)
    median_seconds: float = Field(gt=0)
    range_seconds: int = Field(ge=0)
    target_seconds: int | None = Field(default=None, gt=0)
    targets_met_count: int | None = Field(default=None, ge=0)


def calculate_item_timing(
    capture: ItemTimingCapture,
) -> ItemTimingSummary:
    previous_elapsed = capture.block_start_elapsed_seconds
    calculated: list[CalculatedRepetitionTiming] = []

    for reading in capture.readings:
        actual_seconds = (
            reading.finish_elapsed_seconds - previous_elapsed - reading.rest_before_seconds
        )
        target_met = (
            actual_seconds <= capture.target_seconds if capture.target_seconds is not None else None
        )
        calculated.append(
            CalculatedRepetitionTiming(
                block_sequence=capture.block_sequence,
                set_group_sequence=capture.set_group_sequence,
                item_sequence=capture.item_sequence,
                repetition_number=reading.repetition_number,
                previous_elapsed_seconds=previous_elapsed,
                finish_elapsed_seconds=reading.finish_elapsed_seconds,
                rest_before_seconds=reading.rest_before_seconds,
                actual_seconds=actual_seconds,
                target_seconds=capture.target_seconds,
                target_met=target_met,
                formula=(
                    f"{reading.finish_elapsed_seconds} - {previous_elapsed} "
                    f"- {reading.rest_before_seconds} = {actual_seconds}"
                ),
                note=reading.note,
            )
        )
        previous_elapsed = reading.finish_elapsed_seconds

    values = [repetition.actual_seconds for repetition in calculated]
    active_seconds = sum(values)
    rest_seconds = sum(repetition.rest_before_seconds for repetition in calculated)
    captured_elapsed_seconds = (
        capture.readings[-1].finish_elapsed_seconds - capture.block_start_elapsed_seconds
    )

    if captured_elapsed_seconds != active_seconds + rest_seconds:
        raise ValueError("Captured elapsed time must reconcile to active and rest seconds.")

    targets_met_count = (
        sum(repetition.target_met is True for repetition in calculated)
        if capture.target_seconds is not None
        else None
    )

    return ItemTimingSummary(
        block_sequence=capture.block_sequence,
        set_group_sequence=capture.set_group_sequence,
        item_sequence=capture.item_sequence,
        block_start_elapsed_seconds=capture.block_start_elapsed_seconds,
        block_finish_elapsed_seconds=(capture.readings[-1].finish_elapsed_seconds),
        repetitions=tuple(calculated),
        active_seconds=active_seconds,
        rest_seconds=rest_seconds,
        captured_elapsed_seconds=captured_elapsed_seconds,
        fastest_seconds=min(values),
        slowest_seconds=max(values),
        mean_seconds=mean(values),
        median_seconds=median(values),
        range_seconds=max(values) - min(values),
        target_seconds=capture.target_seconds,
        targets_met_count=targets_met_count,
    )
