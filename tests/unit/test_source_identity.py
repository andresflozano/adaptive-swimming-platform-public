import pytest

from adaptive_swimming.domain.source_identity import source_id_from_sha256


def test_source_id_is_stable_and_anonymous() -> None:
    source_hash = "8c962466bdcc1efa53f61787f84e6b6a216c4c5e6d0939520baa2d61d372b008"

    assert source_id_from_sha256(source_hash) == "SRC_8C962466BDCC"


def test_source_id_accepts_uppercase_hash() -> None:
    source_hash = "A" * 64

    assert source_id_from_sha256(source_hash) == "SRC_AAAAAAAAAAAA"


@pytest.mark.parametrize(
    "invalid_hash",
    [
        "",
        "abc",
        "g" * 64,
        "0" * 63,
        "0" * 65,
    ],
)
def test_source_id_rejects_invalid_hash(invalid_hash: str) -> None:
    with pytest.raises(ValueError):
        source_id_from_sha256(invalid_hash)
