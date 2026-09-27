from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictSourceModel(BaseModel):
    """Immutable source-program model with strict field ownership."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceSetStructure(StrEnum):
    SINGLE_DISTANCE = "SINGLE_DISTANCE"
    FLAT_REPETITION = "FLAT_REPETITION"
    NESTED_REPETITION = "NESTED_REPETITION"


class SourceSet(StrictSourceModel):
    """Nominal structure parsed from one historical swimming-set instruction.

    This model preserves source structure only. It does not assign executable
    exercises, intensities, equipment, rests, or training authority.
    """

    sequence: int = Field(ge=1)
    raw_instruction: str = Field(min_length=1)
    structure_type: SourceSetStructure
    outer_series_count: int | None = Field(default=None, ge=1)
    repetitions_per_series: int = Field(ge=1)
    total_repetitions: int = Field(ge=1)
    distance_per_repetition_m: int = Field(gt=0)
    nominal_distance_m: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_structure(self) -> Self:
        if self.structure_type == SourceSetStructure.SINGLE_DISTANCE:
            if self.outer_series_count is not None:
                raise ValueError("Single-distance sets cannot define outer series.")
            if self.repetitions_per_series != 1 or self.total_repetitions != 1:
                raise ValueError("Single-distance sets require exactly one repetition.")

        elif self.structure_type == SourceSetStructure.FLAT_REPETITION:
            if self.outer_series_count is not None:
                raise ValueError("Flat repetitions cannot define outer series.")
            if self.total_repetitions != self.repetitions_per_series:
                raise ValueError("Flat-repetition total must equal repetitions per series.")

        elif self.structure_type == SourceSetStructure.NESTED_REPETITION:
            if self.outer_series_count is None:
                raise ValueError("Nested repetitions require outer_series_count.")
            expected_total = self.outer_series_count * self.repetitions_per_series
            if self.total_repetitions != expected_total:
                raise ValueError(
                    "Nested-repetition total must equal outer series multiplied "
                    "by repetitions per series."
                )

        expected_distance = self.total_repetitions * self.distance_per_repetition_m
        if self.nominal_distance_m != expected_distance:
            raise ValueError(
                "Nominal distance must equal total repetitions multiplied by "
                "distance per repetition."
            )

        return self
