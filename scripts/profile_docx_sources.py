from __future__ import annotations

import csv
import hashlib
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from adaptive_swimming.domain.source_identity import source_id_from_sha256

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIRECTORY = PROJECT_ROOT / "data" / "raw"
OUTPUT_PATH = PROJECT_ROOT / "data" / "docx_structure_profile.tsv"

WORD_DOCUMENT_PATH = "word/document.xml"
WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NAMESPACES = {"w": WORD_NAMESPACE}


def calculate_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()

    with file_path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def count_text_characters(element: ElementTree.Element) -> int:
    text_values = [
        text_element.text or "" for text_element in element.findall(".//w:t", NAMESPACES)
    ]
    return len("".join(text_values).strip())


def profile_docx(file_path: Path) -> dict[str, str | int]:
    sha256 = calculate_sha256(file_path)

    profile: dict[str, str | int] = {
        "source_id": source_id_from_sha256(sha256),
        "size_bytes": file_path.stat().st_size,
        "sha256": sha256,
        "docx_valid": "NO",
        "paragraph_count": 0,
        "nonempty_paragraph_count": 0,
        "table_count": 0,
        "table_row_count": 0,
        "table_cell_count": 0,
        "text_character_count": 0,
        "embedded_media_count": 0,
        "error": "",
    }

    try:
        with zipfile.ZipFile(file_path) as docx_archive:
            archive_names = docx_archive.namelist()

            if WORD_DOCUMENT_PATH not in archive_names:
                raise ValueError(f"Missing required DOCX component: {WORD_DOCUMENT_PATH}")

            document_xml = docx_archive.read(WORD_DOCUMENT_PATH)
            document_root = ElementTree.fromstring(document_xml)

            paragraphs = document_root.findall(".//w:p", NAMESPACES)
            tables = document_root.findall(".//w:tbl", NAMESPACES)
            table_rows = document_root.findall(".//w:tr", NAMESPACES)
            table_cells = document_root.findall(".//w:tc", NAMESPACES)

            nonempty_paragraph_count = sum(
                1 for paragraph in paragraphs if count_text_characters(paragraph) > 0
            )

            embedded_media_count = sum(
                1
                for archive_name in archive_names
                if archive_name.startswith("word/media/") and not archive_name.endswith("/")
            )

            profile.update(
                {
                    "docx_valid": "YES",
                    "paragraph_count": len(paragraphs),
                    "nonempty_paragraph_count": nonempty_paragraph_count,
                    "table_count": len(tables),
                    "table_row_count": len(table_rows),
                    "table_cell_count": len(table_cells),
                    "text_character_count": count_text_characters(document_root),
                    "embedded_media_count": embedded_media_count,
                }
            )

    except (
        ElementTree.ParseError,
        OSError,
        ValueError,
        zipfile.BadZipFile,
    ) as error:
        profile["error"] = f"{type(error).__name__}: {error}"

    return profile


def collect_docx_profiles(
    raw_directory: Path,
) -> list[dict[str, str | int]]:
    if not raw_directory.exists():
        raise FileNotFoundError(f"Raw source directory does not exist: {raw_directory}")

    docx_files = sorted(
        raw_directory.glob("*.docx"),
        key=lambda file_path: file_path.name.casefold(),
    )

    return [profile_docx(file_path) for file_path in docx_files]


def write_profiles(
    output_path: Path,
    profiles: list[dict[str, str | int]],
) -> None:
    fieldnames = [
        "source_id",
        "size_bytes",
        "sha256",
        "docx_valid",
        "paragraph_count",
        "nonempty_paragraph_count",
        "table_count",
        "table_row_count",
        "table_cell_count",
        "text_character_count",
        "embedded_media_count",
        "error",
    ]

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(profiles)


def main() -> None:
    profiles = collect_docx_profiles(RAW_DIRECTORY)
    write_profiles(OUTPUT_PATH, profiles)

    valid_count = sum(1 for profile in profiles if profile["docx_valid"] == "YES")
    invalid_count = len(profiles) - valid_count

    print(f"DOCX files profiled: {len(profiles)}")
    print(f"Valid DOCX packages: {valid_count}")
    print(f"Invalid DOCX packages: {invalid_count}")
    print(f"Profile written to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
