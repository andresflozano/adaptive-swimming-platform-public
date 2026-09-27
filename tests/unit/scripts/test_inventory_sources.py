from pathlib import Path

from scripts.inventory_sources import inventory_source_files

from adaptive_swimming.domain.source_identity import source_id_from_sha256


def test_inventory_excludes_zone_identifier_files(tmp_path: Path) -> None:
    source_file = tmp_path / "Rutina 16 semanas.docx"
    metadata_file = tmp_path / "Rutina 16 semanas.docx:Zone.Identifier"

    source_file.write_bytes(b"workout source")
    metadata_file.write_bytes(b"metadata")

    rows = inventory_source_files(tmp_path)

    assert len(rows) == 1
    sha256 = str(rows[0]["sha256"])

    assert rows[0]["source_id"] == source_id_from_sha256(sha256)
    assert "source_filename" not in rows[0]
    assert rows[0]["file_extension"] == "docx"
    assert rows[0]["size_bytes"] == len(b"workout source")
    assert rows[0]["scope_status"] == "PENDING_REVIEW"
    assert rows[0]["source_role"] == "UNCLASSIFIED"
    assert len(str(rows[0]["sha256"])) == 64
