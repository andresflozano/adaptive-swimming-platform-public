from pathlib import Path

import pytest
import scripts.create_baseline_pool_test as baseline_script
from scripts.create_baseline_pool_test import (
    create_baseline_pool_test_records,
    validate_date_text,
)

from adaptive_swimming.persistence.session_records import (
    load_generated_workout,
    load_session_result,
)


def test_create_baseline_records_rejects_invalid_pool_length(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="Pool length must be at least one meter",
    ):
        create_baseline_pool_test_records(
            date_text="20260901",
            sequence=1,
            pool_length_meters=0,
            available_training_minutes=45,
            generated_directory=tmp_path / "generated",
            result_directory=tmp_path / "results",
        )

    assert not (tmp_path / "generated").exists()
    assert not (tmp_path / "results").exists()


def test_create_baseline_records_rejects_invalid_available_time(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="Available training time must be at least one minute",
    ):
        create_baseline_pool_test_records(
            date_text="20260901",
            sequence=1,
            pool_length_meters=12.5,
            available_training_minutes=0,
            generated_directory=tmp_path / "generated",
            result_directory=tmp_path / "results",
        )

    assert not (tmp_path / "generated").exists()
    assert not (tmp_path / "results").exists()


def test_create_baseline_records_rolls_back_generated_workout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated_directory = tmp_path / "generated"
    result_directory = tmp_path / "results"

    def fail_session_result_write(
        *_args: object,
        **_kwargs: object,
    ) -> Path:
        raise RuntimeError("Simulated result write failure.")

    monkeypatch.setattr(
        baseline_script,
        "save_session_result",
        fail_session_result_write,
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated result write failure",
    ):
        baseline_script.create_baseline_pool_test_records(
            date_text="20260901",
            sequence=1,
            pool_length_meters=25,
            available_training_minutes=45,
            generated_directory=generated_directory,
            result_directory=result_directory,
        )

    assert not tuple(generated_directory.glob("*.json"))

    if result_directory.exists():
        assert not tuple(result_directory.glob("*.json"))


def test_create_baseline_records_writes_linked_pair(
    tmp_path: Path,
) -> None:
    generated_directory = tmp_path / "generated"
    result_directory = tmp_path / "results"

    generated_path, result_path = create_baseline_pool_test_records(
        date_text="20260901",
        sequence=1,
        pool_length_meters=25,
        available_training_minutes=45,
        generated_directory=generated_directory,
        result_directory=result_directory,
    )

    generated = load_generated_workout(generated_path)
    result = load_session_result(result_path)

    assert generated.available_training_seconds == 2700
    assert result.generated_workout_id == (generated.generated_workout_id)
    assert generated.planned_distance_meters == 2600
    assert generated.configured_rest_seconds == 1050
    assert generated.known_swim_seconds == 1324
    assert generated.unresolved_distance_meters == 1200


def test_create_baseline_records_rejects_existing_pair_member(
    tmp_path: Path,
) -> None:
    generated_directory = tmp_path / "generated"
    result_directory = tmp_path / "results"
    result_directory.mkdir(parents=True)

    existing_result = result_directory / "SR_20260901_001_V1.json"
    existing_result.write_text(
        "existing",
        encoding="utf-8",
    )

    with pytest.raises(
        FileExistsError,
        match="partial or duplicate baseline record pair",
    ):
        create_baseline_pool_test_records(
            date_text="20260901",
            sequence=1,
            pool_length_meters=25,
            available_training_minutes=45,
            generated_directory=generated_directory,
            result_directory=result_directory,
        )

    assert not generated_directory.exists()
    assert existing_result.read_text(encoding="utf-8") == "existing"


def test_create_baseline_records_rejects_invalid_sequence(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="Sequence must be at least one",
    ):
        create_baseline_pool_test_records(
            date_text="20260901",
            sequence=0,
            pool_length_meters=25,
            available_training_minutes=45,
            generated_directory=tmp_path / "generated",
            result_directory=tmp_path / "results",
        )


def test_validate_date_text_accepts_valid_calendar_date() -> None:
    validate_date_text("20260901")


@pytest.mark.parametrize(
    "date_text",
    (
        "2026-09-01",
        "2026091",
        "YYYYMMDD",
    ),
)
def test_validate_date_text_rejects_invalid_format(
    date_text: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="YYYYMMDD format",
    ):
        validate_date_text(date_text)


@pytest.mark.parametrize(
    "date_text",
    (
        "20260230",
        "20261301",
        "20260001",
    ),
)
def test_validate_date_text_rejects_impossible_date(
    date_text: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="valid calendar date",
    ):
        validate_date_text(date_text)


def test_create_baseline_records_preserves_fractional_pool_length(
    tmp_path: Path,
) -> None:
    generated_path, result_path = create_baseline_pool_test_records(
        date_text="20260901",
        sequence=1,
        pool_length_meters=12.5,
        available_training_minutes=45,
        generated_directory=tmp_path / "generated",
        result_directory=tmp_path / "results",
    )

    generated = load_generated_workout(generated_path)
    result = load_session_result(result_path)

    assert generated.pool_length_meters == 12.5
    assert result.generated_workout_id == generated.generated_workout_id
