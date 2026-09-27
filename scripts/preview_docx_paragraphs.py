from __future__ import annotations

import argparse
import zipfile
from pathlib import Path
from xml.etree import ElementTree

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIRECTORY = PROJECT_ROOT / "data" / "raw"
WORD_DOCUMENT_PATH = "word/document.xml"
WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NAMESPACES = {"w": WORD_NAMESPACE}


def extract_nonempty_paragraphs(file_path: Path) -> list[str]:
    with zipfile.ZipFile(file_path) as docx_archive:
        document_xml = docx_archive.read(WORD_DOCUMENT_PATH)

    document_root = ElementTree.fromstring(document_xml)
    paragraphs: list[str] = []

    for paragraph in document_root.findall(".//w:p", NAMESPACES):
        text = "".join(
            text_element.text or ""
            for text_element in paragraph.findall(".//w:t", NAMESPACES)
        ).strip()

        if text:
            paragraphs.append(text)

    return paragraphs


def resolve_source_path(filename: str) -> Path:
    source_path = RAW_DIRECTORY / filename

    if not source_path.is_file():
        raise FileNotFoundError(f"Source DOCX does not exist: {source_path}")

    if source_path.suffix.casefold() != ".docx":
        raise ValueError(f"Source must be a DOCX file: {source_path}")

    return source_path


def preview_document(filename: str, maximum_paragraphs: int) -> None:
    source_path = resolve_source_path(filename)
    paragraphs = extract_nonempty_paragraphs(source_path)

    print("=" * 80)
    print(f"Source: {filename}")
    print(f"Non-empty paragraphs: {len(paragraphs)}")
    print(f"Preview limit: {maximum_paragraphs}")
    print("=" * 80)

    for sequence, paragraph in enumerate(paragraphs[:maximum_paragraphs], start=1):
        print(f"{sequence:03d}: {paragraph}")

    remaining = len(paragraphs) - maximum_paragraphs
    if remaining > 0:
        print(f"... {remaining} additional paragraphs not displayed.")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Display a read-only numbered preview of non-empty DOCX paragraphs."
    )
    parser.add_argument(
        "filename",
        help="Exact DOCX filename inside data/raw.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of non-empty paragraphs to display.",
    )
    arguments = parser.parse_args()

    if arguments.limit < 1:
        parser.error("--limit must be at least 1")

    return arguments


def main() -> None:
    arguments = parse_arguments()
    preview_document(
        filename=arguments.filename,
        maximum_paragraphs=arguments.limit,
    )


if __name__ == "__main__":
    main()
