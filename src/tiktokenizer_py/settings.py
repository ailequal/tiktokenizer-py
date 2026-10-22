"""Runtime settings, read from ``APP_*`` environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from tiktokenizer_py.schemas import MAX_BODY_BYTES, MAX_TEXT_CHARS


@dataclass(frozen=True, slots=True)
class Settings:
    max_text_chars: int = MAX_TEXT_CHARS
    max_body_bytes: int = MAX_BODY_BYTES
    # Where prices fetched at runtime are saved; None keeps them in memory only.
    data_dir: Path | None = None

    @classmethod
    def from_env(cls) -> Settings:
        data_dir = os.environ.get("APP_DATA_DIR")
        return cls(
            max_text_chars=int(os.environ.get("APP_MAX_TEXT_CHARS", str(MAX_TEXT_CHARS))),
            max_body_bytes=int(os.environ.get("APP_MAX_BODY_BYTES", str(MAX_BODY_BYTES))),
            data_dir=Path(data_dir) if data_dir else None,
        )
