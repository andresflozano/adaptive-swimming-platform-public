from __future__ import annotations

import pytest
from pydantic import ValidationError

from adaptive_swimming.source_program import (
    SourceSet,
    SourceSetStructure,
    parse_nominal_source_set,
)


def test_parses_single_distance_set() -> None:
    parsed = parse_nominal_source_set("200 m easy freestyle")

    assert parsed.structure_type == SourceSetStructure.SINGLE_DISTANCE
    assert parsed.outer_series_count is None
    assert parsed.repetitions_per_series == 1
    assert parsed.total_repetitions == 1
    assert parsed.distance_per_repetition_m == 200
    assert parsed.nominal_distance_m == 200


def test_parses_flat_repetition_set() -> None:
    parsed = parse_nominal_source_set("6x50 con 30 segundos de pausa", sequence=2)

    assert parsed.sequence == 2
    assert parsed.structure_type == SourceSetStructure.FLAT_REPETITION
    assert parsed.outer_series_count is None
    assert parsed.repetitions_per_series == 6
    assert parsed.total_repetitions == 6
    assert parsed.distance_per_repetition_m == 50
    assert parsed.nominal_distance_m == 300


def test_parses_nested_repetition_without_flattening_structure() -> None:
    parsed = parse_nominal_source_set("3x2x200 con pausa entre repeticiones y series")

    assert parsed.structure_type == SourceSetStructure.NESTED_REPETITION
    assert parsed.outer_series_count == 3
    assert parsed.repetitions_per_series == 2
    assert parsed.total_repetitions == 6
    assert parsed.distance_per_repetition_m == 200
    assert parsed.nominal_distance_m == 1200


def test_accepts_uppercase_repetition_separator() -> None:
    parsed = parse_nominal_source_set("4X3X100")

    assert parsed.structure_type == SourceSetStructure.NESTED_REPETITION
    assert parsed.nominal_distance_m == 1200


@pytest.mark.parametrize("value", ["", "   ", "swim easy", "x100"])
def test_rejects_unsupported_or_blank_instruction(value: str) -> None:
    with pytest.raises(ValueError):
        parse_nominal_source_set(value)


def test_source_set_is_immutable() -> None:
    parsed = parse_nominal_source_set("200 m easy freestyle")

    with pytest.raises(ValidationError):
        parsed.nominal_distance_m = 300


def test_rejects_inconsistent_nested_total() -> None:
    with pytest.raises(
        ValidationError,
        match="Nested-repetition total",
    ):
        SourceSet(
            sequence=1,
            raw_instruction="3x2x200",
            structure_type=SourceSetStructure.NESTED_REPETITION,
            outer_series_count=3,
            repetitions_per_series=2,
            total_repetitions=5,
            distance_per_repetition_m=200,
            nominal_distance_m=1000,
        )


def test_rejects_inconsistent_nominal_distance() -> None:
    with pytest.raises(
        ValidationError,
        match="Nominal distance",
    ):
        SourceSet(
            sequence=1,
            raw_instruction="6x50",
            structure_type=SourceSetStructure.FLAT_REPETITION,
            repetitions_per_series=6,
            total_repetitions=6,
            distance_per_repetition_m=50,
            nominal_distance_m=250,
        )


@pytest.mark.parametrize(
    "instruction",
    [
        "1\u2019 pausa",
        "2\u2019 pausa o 50 suave (25+25)",
        "3' pausa",
        "4\u2032 descanso",
    ],
)
def test_rejects_timing_only_instruction_as_nominal_distance(
    instruction: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported leading source-set structure",
    ):
        parse_nominal_source_set(instruction)
