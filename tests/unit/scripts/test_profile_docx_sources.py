from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from scripts.profile_docx_sources import profile_docx

from adaptive_swimming.domain.source_identity import source_id_from_sha256

DOCUMENT_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document
    xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
>
    <w:body>
        <w:p>
            <w:r>
                <w:t>Warm-up 200m</w:t>
            </w:r>
        </w:p>
        <w:p>
            <w:r>
                <w:t>Main set 4x100m</w:t>
            </w:r>
        </w:p>
        <w:p />
    </w:body>
</w:document>
"""


def create_test_docx(file_path: Path) -> None:
    with ZipFile(file_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "word/document.xml",
            DOCUMENT_XML,
        )
        archive.writestr(
            "word/media/test-image.png",
            b"not-a-real-image",
        )


def test_profile_docx_reads_structure_without_modifying_source(
    tmp_path: Path,
) -> None:
    docx_path = tmp_path / "representative.docx"
    create_test_docx(docx_path)

    source_bytes_before = docx_path.read_bytes()

    profile = profile_docx(docx_path)

    source_bytes_after = docx_path.read_bytes()

    sha256 = str(profile["sha256"])

    assert profile["source_id"] == source_id_from_sha256(sha256)
    assert "source_filename" not in profile
    assert profile["docx_valid"] == "YES"
    assert profile["paragraph_count"] == 3
    assert profile["nonempty_paragraph_count"] == 2
    assert profile["table_count"] == 0
    assert profile["text_character_count"] == 27
    assert profile["embedded_media_count"] == 1
    assert profile["error"] == ""
    assert source_bytes_after == source_bytes_before


def test_profile_docx_reports_invalid_package(
    tmp_path: Path,
) -> None:
    docx_path = tmp_path / "invalid.docx"
    docx_path.write_text("not a DOCX package", encoding="utf-8")

    profile = profile_docx(docx_path)

    assert profile["docx_valid"] == "NO"
    assert str(profile["error"]).startswith("BadZipFile:")
