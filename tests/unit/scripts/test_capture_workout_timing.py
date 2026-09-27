from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from scripts.capture_workout_timing import (
    TimingCaptureInput,
    build_capture_template,
    calculate_capture,
    parse_elapsed_seconds,
)
from tests.unit.test_configurable_workout_proposal import build_parent

from adaptive_swimming.persistence.session_records import save_generated_workout


def test_parses_seconds_and_mm_ss() -> None:
    assert parse_elapsed_seconds(65) == 65
    assert parse_elapsed_seconds("65") == 65
    assert parse_elapsed_seconds("1:05") == 65
    assert parse_elapsed_seconds("18:30") == 1110


@pytest.mark.parametrize("value", ("", "1:60", "abc", "1:2:3", -1))
def test_rejects_invalid_elapsed_values(value: str | int) -> None:
    with pytest.raises(ValueError):
        parse_elapsed_seconds(value)


def test_template_uses_planned_repetitions_target_and_rest() -> None:
    template = build_capture_template(
        build_parent(),
        block_sequence=4,
        set_group_sequence=1,
        item_sequence=1,
    )
    assert template["generated_workout_id"] == "GW_20260905_001_V1"
    assert template["target_seconds"] == 65
    assert len(template["readings"]) == 4
    assert tuple(reading["rest_before"] for reading in template["readings"]) == (
        0,
        30,
        30,
        30,
    )


def test_template_rejects_unknown_coordinate() -> None:
    with pytest.raises(ValueError, match="planned item"):
        build_capture_template(
            build_parent(),
            block_sequence=4,
            set_group_sequence=1,
            item_sequence=99,
        )


def pool_test_four_input() -> TimingCaptureInput:
    return TimingCaptureInput.model_validate(
        {
            "generated_workout_id": "GW_20260905_001_V1",
            "block_sequence": 4,
            "set_group_sequence": 1,
            "item_sequence": 1,
            "block_start_elapsed": "18:30",
            "target_seconds": 65,
            "readings": [
                {"repetition_number": 1, "finish_elapsed": "19:30"},
                {
                    "repetition_number": 2,
                    "finish_elapsed": "20:57",
                    "rest_before": "0:30",
                },
                {
                    "repetition_number": 3,
                    "finish_elapsed": "22:27",
                    "rest_before": 30,
                },
                {
                    "repetition_number": 4,
                    "finish_elapsed": "23:55",
                    "rest_before": 30,
                },
            ],
        }
    )


def test_calculates_and_converts_capture() -> None:
    summary, results = calculate_capture(
        generated_workout=build_parent(),
        capture_input=pool_test_four_input(),
    )
    assert tuple(item.actual_seconds for item in results) == (60, 57, 60, 58)
    assert tuple(item.rest_after_seconds for item in results) == (30, 30, 30, None)
    assert summary.targets_met_count == 4


def test_rejects_wrong_generated_workout_id() -> None:
    payload = pool_test_four_input().model_dump()
    payload["generated_workout_id"] = "GW_20260905_999_V1"
    with pytest.raises(ValueError, match="does not belong"):
        calculate_capture(
            generated_workout=build_parent(),
            capture_input=TimingCaptureInput.model_validate(payload),
        )


def test_direct_file_help_succeeds() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/capture_workout_timing.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "--template" in completed.stdout
    assert "--capture" in completed.stdout


def test_module_help_succeeds() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.capture_workout_timing", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0


def test_template_cli_writes_only_stdout(tmp_path: Path) -> None:
    generated_path = save_generated_workout(build_parent(), tmp_path / "generated")
    before = tuple(sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")))
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.capture_workout_timing",
            "--generated-workout",
            str(generated_path),
            "--template",
            "--block-sequence",
            "4",
            "--set-group-sequence",
            "1",
            "--item-sequence",
            "1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    after = tuple(sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")))
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["target_seconds"] == 65
    assert after == before


def test_calculate_cli_json_writes_only_stdout(tmp_path: Path) -> None:
    generated_path = save_generated_workout(build_parent(), tmp_path / "generated")
    capture_path = tmp_path / "capture.json"
    capture_path.write_text(pool_test_four_input().model_dump_json(indent=2), encoding="utf-8")
    before = tuple(sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")))
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.capture_workout_timing",
            "--generated-workout",
            str(generated_path),
            "--capture",
            str(capture_path),
            "--output-format",
            "json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    after = tuple(sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")))
    payload = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert payload["writes_performed"] is False
    assert [row["actual_seconds"] for row in payload["repetition_results"]] == [
        60,
        57,
        60,
        58,
    ]
    assert after == before


def test_capture_input_rejects_extra_fields() -> None:
    payload = pool_test_four_input().model_dump()
    payload["heart_rate"] = 150
    with pytest.raises(ValidationError):
        TimingCaptureInput.model_validate(payload)
