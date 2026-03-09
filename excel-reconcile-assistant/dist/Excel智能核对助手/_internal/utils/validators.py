from __future__ import annotations

from pathlib import Path


def is_supported_filename(filename: str) -> bool:
    return Path(filename).suffix.lower() in {".csv", ".xlsx", ".xls"}
