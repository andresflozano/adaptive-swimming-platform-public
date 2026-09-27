from __future__ import annotations

import re

from adaptive_swimming.source_program.models import SourceSet, SourceSetStructure

_NESTED_REPETITION_PATTERN = re.compile(
    r"^(?P<outer>\d+)\s*[xX]\s*(?P<inner>\d+)\s*[xX]\s*(?P<distance>\d+)\b"
)
_FLAT_REPETITION_PATTERN = re.compile(r"^(?P<repetitions>\d+)\s*[xX]\s*(?P<distance>\d+)\b")
_SINGLE_DISTANCE_PATTERN = re.compile(r"^(?P<distance>\d+)\b")


def parse_nominal_source_set(raw_instruction: str, *, sequence: int = 1) -> SourceSet:
    """Parse the leading nominal set structure from a historical instruction.

    Trailing source wording is preserved but not semantically interpreted.
    Unsupported leading syntax raises ValueError instead of guessing.
    """

    instruction = raw_instruction.strip()
    if not instruction:
        raise ValueError("Source-set instruction cannot be blank.")

    nested_match = _NESTED_REPETITION_PATTERN.match(instruction)
    if nested_match is not None:
        outer_series_count = int(nested_match.group("outer"))
        repetitions_per_series = int(nested_match.group("inner"))
        distance_per_repetition_m = int(nested_match.group("distance"))
        total_repetitions = outer_series_count * repetitions_per_series

        return SourceSet(
            sequence=sequence,
            raw_instruction=instruction,
            structure_type=SourceSetStructure.NESTED_REPETITION,
            outer_series_count=outer_series_count,
            repetitions_per_series=repetitions_per_series,
            total_repetitions=total_repetitions,
            distance_per_repetition_m=distance_per_repetition_m,
            nominal_distance_m=total_repetitions * distance_per_repetition_m,
        )

    flat_match = _FLAT_REPETITION_PATTERN.match(instruction)
    if flat_match is not None:
        repetitions = int(flat_match.group("repetitions"))
        distance_per_repetition_m = int(flat_match.group("distance"))

        return SourceSet(
            sequence=sequence,
            raw_instruction=instruction,
            structure_type=SourceSetStructure.FLAT_REPETITION,
            repetitions_per_series=repetitions,
            total_repetitions=repetitions,
            distance_per_repetition_m=distance_per_repetition_m,
            nominal_distance_m=repetitions * distance_per_repetition_m,
        )

    timing_only_match = re.match(
        r"^\d+\s*[\u2019\u2032']",
        instruction,
    )
    if timing_only_match is not None:
        raise ValueError(f"Unsupported leading source-set structure: {raw_instruction!r}")

    single_match = _SINGLE_DISTANCE_PATTERN.match(instruction)
    if single_match is not None:
        distance_per_repetition_m = int(single_match.group("distance"))

        return SourceSet(
            sequence=sequence,
            raw_instruction=instruction,
            structure_type=SourceSetStructure.SINGLE_DISTANCE,
            repetitions_per_series=1,
            total_repetitions=1,
            distance_per_repetition_m=distance_per_repetition_m,
            nominal_distance_m=distance_per_repetition_m,
        )

    raise ValueError(f"Unsupported leading source-set structure: {raw_instruction!r}")
