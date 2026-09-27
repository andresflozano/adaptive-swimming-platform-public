from __future__ import annotations

import pytest
from pydantic import ValidationError

from adaptive_swimming.source_program import SourceSetStructure
from adaptive_swimming.source_program.timing import (
    SourceTimingApplication,
    SourceTimingExpression,
    SourceTimingParseStatus,
    SourceTimingType,
    parse_source_timing_expressions,
)


def test_parses_explicit_recovery() -> None:
    expressions = parse_source_timing_expressions("6x50 con 30” pausa")

    assert len(expressions) == 1
    assert expressions[0].duration_seconds == 30
    assert expressions[0].timing_type == SourceTimingType.RECOVERY_DURATION
    assert expressions[0].application == SourceTimingApplication.BETWEEN_REPETITIONS


def test_parses_double_apostrophe_seconds() -> None:
    expression = parse_source_timing_expressions("2x100 con 45’’ pausa")[0]

    assert expression.duration_seconds == 45


def test_parses_nested_recovery_hierarchy() -> None:
    expressions = parse_source_timing_expressions(
        "3x2x200 con 1’ pausa entre pasadas y 2’ entre series"
    )

    assert tuple(value.duration_seconds for value in expressions) == (60, 120)
    assert tuple(value.application for value in expressions) == (
        SourceTimingApplication.BETWEEN_REPETITIONS,
        SourceTimingApplication.BETWEEN_SERIES,
    )


def test_parses_nested_block_recovery() -> None:
    expressions = parse_source_timing_expressions(
        "4x3x100 con 1’ pausa entre cienes y 3’ entre bloques"
    )

    assert expressions[1].duration_seconds == 180
    assert expressions[1].application == SourceTimingApplication.BETWEEN_BLOCKS


def test_parses_marked_send_off() -> None:
    expression = parse_source_timing_expressions("2x50 cada 1’30”")[0]

    assert expression.timing_type == SourceTimingType.SEND_OFF_INTERVAL
    assert expression.duration_seconds == 90
    assert expression.application == SourceTimingApplication.REPETITION_START_INTERVAL


def test_parses_dot_notation_only_in_send_off_context() -> None:
    expression = parse_source_timing_expressions("5x100 cada 2.30” t/desc")[0]

    assert expression.duration_seconds == 150
    assert expression.parse_status == SourceTimingParseStatus.SOURCE_CONTEXT_SUPPORTED
    assert parse_source_timing_expressions("5x100 a 2.30") == ()


def test_single_distance_implicit_recovery_stays_unresolved() -> None:
    expression = parse_source_timing_expressions(
        "400 con 40”",
        structure_type=SourceSetStructure.SINGLE_DISTANCE,
    )[0]

    assert expression.timing_type == SourceTimingType.RECOVERY_DURATION_CANDIDATE
    assert expression.application == SourceTimingApplication.UNRESOLVED
    assert expression.parse_status == SourceTimingParseStatus.PENDING_CONTEXT_REVIEW


def test_repeated_implicit_recovery_uses_source_context() -> None:
    expression = parse_source_timing_expressions(
        "2x300 con 40”",
        structure_type=SourceSetStructure.FLAT_REPETITION,
    )[0]

    assert expression.application == SourceTimingApplication.BETWEEN_REPETITIONS
    assert expression.parse_status == SourceTimingParseStatus.SOURCE_CONTEXT_SUPPORTED


def test_parses_standalone_recovery_without_faking_distance() -> None:
    expression = parse_source_timing_expressions("2’ pausa o 50 suave (25+25)")[0]

    assert expression.duration_seconds == 120
    assert expression.application == SourceTimingApplication.UNRESOLVED


def test_ignores_breathing_cadence() -> None:
    assert parse_source_timing_expressions("hipoxico cada 7") == ()


def test_timing_expression_is_immutable() -> None:
    expression = parse_source_timing_expressions("6x50 con 30” pausa")[0]

    with pytest.raises(ValidationError):
        expression.duration_seconds = 45


def test_rejects_blank_instruction() -> None:
    with pytest.raises(ValueError, match="cannot be blank"):
        parse_source_timing_expressions("   ")


def test_rejects_invalid_timing_expression() -> None:
    with pytest.raises(ValidationError):
        SourceTimingExpression(
            sequence=1,
            timing_type=SourceTimingType.RECOVERY_DURATION,
            duration_seconds=0,
            application=SourceTimingApplication.BETWEEN_REPETITIONS,
            evidence_text="con 0 pausa",
            parse_status=SourceTimingParseStatus.LEXICALLY_SUPPORTED,
        )
