from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from scripts.preview_docx_paragraphs import (
    extract_nonempty_paragraphs,
    resolve_source_path,
)

DOCUMENT_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document
    xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
>
    <w:body>
        <w:p>
            <w:r>
                <w:t>200 m easy freestyle</w:t>
            </w:r>
        </w:p>
        <w:p />
        <w:p>
            <w:r>
                <w:t>4x50 con 30 segundos pausa</w:t>
            </w:r>
        </w:p>
    </w:body>
</w:document>
"""


def create_test_docx(file_path: Path) -> None:
    with ZipFile(file_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "word/document.xml",
            DOCUMENT_XML,
        )


def test_extract_nonempty_paragraphs_preserves_order(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "workout.docx"
    create_test_docx(source_path)

    source_before = source_path.read_bytes()
    paragraphs = extract_nonempty_paragraphs(source_path)
    source_after = source_path.read_bytes()

    assert paragraphs == [
        "200 m easy freestyle",
        "4x50 con 30 segundos pausa",
    ]
    assert source_after == source_before


def test_resolve_source_path_rejects_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        resolve_source_path("missing.docx")


def test_resolve_source_path_rejects_non_docx(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"pdf")

    monkeypatch.setattr(
        "scripts.preview_docx_paragraphs.RAW_DIRECTORY",
        tmp_path,
    )

    with pytest.raises(ValueError):
        resolve_source_path(source_path.name)
