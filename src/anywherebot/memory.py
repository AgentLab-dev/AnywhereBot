"""JSONL session log under .anywherebot/sessions/."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SessionLog:
    def __init__(self, directory: Path, session_id: str | None = None) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.session_id = session_id or stamp
        self.path = self.directory / f"{self.session_id}.jsonl"

    def write(self, role: str, content: str | None = None, **extra: Any) -> None:
        record: dict[str, Any] = {"ts": utc_now(), "role": role}
        if content is not None:
            record["content"] = content
        record.update(extra)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
