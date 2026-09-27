from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from adaptive_swimming.domain.source_identity import source_id_from_sha256

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIRECTORY = PROJECT_ROOT / "data" / "raw"
MANIFEST_PATH = PROJECT_ROOT / "data" / "source_manifest.tsv"
ZONE_IDENTIFIER_SUFFIX = ":Zone.Identifier"


def calculate_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()

    with file_path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def inventory_source_files(raw_directory: Path) -> list[dict[str, str | int]]:
    if not raw_directory.exists():
        raise FileNotFoundError(f"Raw source directory does not exist: {raw_directory}")

    source_files = sorted(
        (
            file_path
            for file_path in raw_directory.iterdir()
            if file_path.is_file() and not file_path.name.endswith(ZONE_IDENTIFIER_SUFFIX)
        ),
        key=lambda file_path: file_path.name.casefold(),
    )

    rows: list[dict[str, str | int]] = []

    for file_path in source_files:
        sha256 = calculate_sha256(file_path)

        rows.append(
            {
                "source_id": source_id_from_sha256(sha256),
                "file_extension": file_path.suffix.lower().lstrip("."),
                "size_bytes": file_path.stat().st_size,
                "sha256": sha256,
                "scope_status": "PENDING_REVIEW",
                "source_role": "UNCLASSIFIED",
                "notes": "",
            }
        )

    return rows


def write_manifest(
    manifest_path: Path,
    rows: list[dict[str, str | int]],
) -> None:
    fieldnames = [
        "source_id",
        "file_extension",
        "size_bytes",
        "sha256",
        "scope_status",
        "source_role",
        "notes",
    ]

    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    with manifest_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def report_duplicate_hashes(
    rows: list[dict[str, str | int]],
) -> None:
    source_ids_by_hash: defaultdict[str, list[str]] = defaultdict(list)

    for row in rows:
        source_ids_by_hash[str(row["sha256"])].append(str(row["source_id"]))

    duplicates = {
        file_hash: filenames
        for file_hash, filenames in source_ids_by_hash.items()
        if len(filenames) > 1
    }

    if not duplicates:
        print("Duplicate source hashes: none")
        return

    print("Duplicate source hashes:")

    for file_hash, filenames in sorted(duplicates.items()):
        print(f"  {file_hash}")
        for filename in filenames:
            print(f"    - {filename}")


def main() -> None:
    rows = inventory_source_files(RAW_DIRECTORY)
    write_manifest(MANIFEST_PATH, rows)

    print(f"Source files inventoried: {len(rows)}")
    print(f"Manifest written to: {MANIFEST_PATH}")
    report_duplicate_hashes(rows)


if __name__ == "__main__":
    main()
