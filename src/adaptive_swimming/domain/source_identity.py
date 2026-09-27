from __future__ import annotations

import re

SOURCE_ID_PATTERN = re.compile(r"^SRC_[0-9A-F]{12}$")


def source_id_from_sha256(sha256: str) -> str:
    normalized_hash = sha256.strip().lower()

    if not re.fullmatch(r"[0-9a-f]{64}", normalized_hash):
        raise ValueError("SHA-256 must contain exactly 64 hexadecimal characters.")

    return f"SRC_{normalized_hash[:12].upper()}"
