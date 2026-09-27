from __future__ import annotations

import re
from enum import StrEnum

from pydantic import Field

from adaptive_swimming.source_program.models import SourceSetStructure, StrictSourceModel

_DURATION = r"(?:\d+[’'′](?:\d{1,2}[”\"″]?)?|\d+[”\"″]|\d+’’)"
_DOT_SEND_OFF_DURATION = r"\d+[.]\d{2}[”\"″]"

_NESTED_RECOVERY = re.compile(
    rf"\bcon\s+(?P<inner>{_DURATION})\s+pausa\s+entre\s+"
    r"(?P<inner_unit>pasadas|cienes|repeticiones)\s+y\s+"
    rf"(?P<outer>{_DURATION})\s+entre\s+(?P<outer_unit>series|bloques)\b",
    re.IGNORECASE,
)
_EXPLICIT_RECOVERY = re.compile(
    rf"\bcon\s+(?P<duration>{_DURATION})\s+(?:pausa|descanso)\b",
    re.IGNORECASE,
)
_STANDALONE_RECOVERY = re.compile(
    rf"^(?P<duration>{_DURATION})\s+pausa\b",
    re.IGNORECASE,
)
_SEND_OFF = re.compile(
    rf"\b(?:largando\s+)?cada\s+(?P<duration>{_DURATION})",
    re.IGNORECASE,
)
_DOT_SEND_OFF = re.compile(
    rf"\b(?:largando\s+)?cada\s+(?P<duration>{_DOT_SEND_OFF_DURATION})",
    re.IGNORECASE,
)
_IMPLICIT_RECOVERY = re.compile(
    rf"\bcon\s+(?P<duration>{_DURATION})(?=\s|,|$)",
    re.IGNORECASE,
)


class SourceTimingType(StrEnum):
    RECOVERY_DURATION = "RECOVERY_DURATION"
    RECOVERY_DURATION_CANDIDATE = "RECOVERY_DURATION_CANDIDATE"
    SEND_OFF_INTERVAL = "SEND_OFF_INTERVAL"


class SourceTimingApplication(StrEnum):
    BETWEEN_REPETITIONS = "BETWEEN_REPETITIONS"
    BETWEEN_SERIES = "BETWEEN_SERIES"
    BETWEEN_BLOCKS = "BETWEEN_BLOCKS"
    REPETITION_START_INTERVAL = "REPETITION_START_INTERVAL"
    UNRESOLVED = "UNRESOLVED"


class SourceTimingParseStatus(StrEnum):
    LEXICALLY_SUPPORTED = "LEXICALLY_SUPPORTED"
    SOURCE_CONTEXT_SUPPORTED = "SOURCE_CONTEXT_SUPPORTED"
    PENDING_CONTEXT_REVIEW = "PENDING_CONTEXT_REVIEW"


class SourceTimingExpression(StrictSourceModel):
    sequence: int = Field(ge=1)
    timing_type: SourceTimingType
    duration_seconds: int = Field(gt=0)
    application: SourceTimingApplication
    evidence_text: str = Field(min_length=1)
    parse_status: SourceTimingParseStatus


def _duration_seconds(raw_duration: str, *, dot_send_off: bool = False) -> int:
    if dot_send_off:
        minutes_text, seconds_and_mark = raw_duration.split(".", maxsplit=1)
        seconds_text = re.sub(r"[”\"″]$", "", seconds_and_mark)
        seconds = int(seconds_text)
        if seconds >= 60:
            raise ValueError("Send-off seconds must be less than 60.")
        return int(minutes_text) * 60 + seconds

    double_apostrophe = re.fullmatch(r"(?P<seconds>\d+)’’", raw_duration)
    if double_apostrophe is not None:
        return int(double_apostrophe.group("seconds"))

    minutes = re.fullmatch(
        r"(?P<minutes>\d+)[’'′](?P<seconds>\d{1,2})?[”\"″]?",
        raw_duration,
    )
    if minutes is not None:
        seconds_text = minutes.group("seconds")
        seconds = int(seconds_text) if seconds_text else 0
        if seconds >= 60:
            raise ValueError("Duration seconds must be less than 60.")
        return int(minutes.group("minutes")) * 60 + seconds

    seconds_match = re.fullmatch(
        r"(?P<seconds>\d+)[”\"″]",
        raw_duration,
    )
    if seconds_match is not None:
        return int(seconds_match.group("seconds"))

    raise ValueError(f"Unsupported duration expression: {raw_duration!r}")


def _expression(
    *,
    sequence: int,
    timing_type: SourceTimingType,
    duration_seconds: int,
    application: SourceTimingApplication,
    evidence_text: str,
    parse_status: SourceTimingParseStatus,
) -> SourceTimingExpression:
    return SourceTimingExpression(
        sequence=sequence,
        timing_type=timing_type,
        duration_seconds=duration_seconds,
        application=application,
        evidence_text=evidence_text,
        parse_status=parse_status,
    )


def parse_source_timing_expressions(
    raw_instruction: str,
    *,
    structure_type: SourceSetStructure | None = None,
) -> tuple[SourceTimingExpression, ...]:
    instruction = raw_instruction.strip()
    if not instruction:
        raise ValueError("Source timing instruction cannot be blank.")

    nested = _NESTED_RECOVERY.search(instruction)
    if nested is not None:
        outer_application = (
            SourceTimingApplication.BETWEEN_SERIES
            if nested.group("outer_unit").lower() == "series"
            else SourceTimingApplication.BETWEEN_BLOCKS
        )
        return (
            _expression(
                sequence=1,
                timing_type=SourceTimingType.RECOVERY_DURATION,
                duration_seconds=_duration_seconds(nested.group("inner")),
                application=SourceTimingApplication.BETWEEN_REPETITIONS,
                evidence_text=nested.group(0),
                parse_status=SourceTimingParseStatus.LEXICALLY_SUPPORTED,
            ),
            _expression(
                sequence=2,
                timing_type=SourceTimingType.RECOVERY_DURATION,
                duration_seconds=_duration_seconds(nested.group("outer")),
                application=outer_application,
                evidence_text=nested.group(0),
                parse_status=SourceTimingParseStatus.LEXICALLY_SUPPORTED,
            ),
        )

    explicit = _EXPLICIT_RECOVERY.search(instruction)
    if explicit is not None:
        return (
            _expression(
                sequence=1,
                timing_type=SourceTimingType.RECOVERY_DURATION,
                duration_seconds=_duration_seconds(explicit.group("duration")),
                application=SourceTimingApplication.BETWEEN_REPETITIONS,
                evidence_text=explicit.group(0),
                parse_status=SourceTimingParseStatus.LEXICALLY_SUPPORTED,
            ),
        )

    standalone = _STANDALONE_RECOVERY.search(instruction)
    if standalone is not None:
        return (
            _expression(
                sequence=1,
                timing_type=SourceTimingType.RECOVERY_DURATION,
                duration_seconds=_duration_seconds(standalone.group("duration")),
                application=SourceTimingApplication.UNRESOLVED,
                evidence_text=standalone.group(0),
                parse_status=SourceTimingParseStatus.SOURCE_CONTEXT_SUPPORTED,
            ),
        )

    send_off = _SEND_OFF.search(instruction)
    if send_off is not None:
        return (
            _expression(
                sequence=1,
                timing_type=SourceTimingType.SEND_OFF_INTERVAL,
                duration_seconds=_duration_seconds(send_off.group("duration")),
                application=SourceTimingApplication.REPETITION_START_INTERVAL,
                evidence_text=send_off.group(0),
                parse_status=SourceTimingParseStatus.LEXICALLY_SUPPORTED,
            ),
        )

    dot_send_off = _DOT_SEND_OFF.search(instruction)
    if dot_send_off is not None:
        return (
            _expression(
                sequence=1,
                timing_type=SourceTimingType.SEND_OFF_INTERVAL,
                duration_seconds=_duration_seconds(
                    dot_send_off.group("duration"),
                    dot_send_off=True,
                ),
                application=SourceTimingApplication.REPETITION_START_INTERVAL,
                evidence_text=dot_send_off.group(0),
                parse_status=SourceTimingParseStatus.SOURCE_CONTEXT_SUPPORTED,
            ),
        )

    implicit = _IMPLICIT_RECOVERY.search(instruction)
    if implicit is not None:
        application = (
            SourceTimingApplication.UNRESOLVED
            if structure_type == SourceSetStructure.SINGLE_DISTANCE
            else SourceTimingApplication.BETWEEN_REPETITIONS
        )
        status = (
            SourceTimingParseStatus.PENDING_CONTEXT_REVIEW
            if application == SourceTimingApplication.UNRESOLVED
            else SourceTimingParseStatus.SOURCE_CONTEXT_SUPPORTED
        )
        return (
            _expression(
                sequence=1,
                timing_type=SourceTimingType.RECOVERY_DURATION_CANDIDATE,
                duration_seconds=_duration_seconds(implicit.group("duration")),
                application=application,
                evidence_text=implicit.group(0),
                parse_status=status,
            ),
        )

    return ()
