from __future__ import annotations

from pathlib import Path

import pytest
import yaml

BOT_MD = """# Macha

You are Macha, a portable assistant.
"""

LLM_AUTO = {
    "provider": "auto",
    "timeout_s": 30,
}


@pytest.fixture
def bot_root(tmp_path: Path) -> Path:
    (tmp_path / "bot.md").write_text(BOT_MD, encoding="utf-8")
    (tmp_path / "llm.yaml").write_text(yaml.safe_dump(LLM_AUTO), encoding="utf-8")
    (tmp_path / "workspace").mkdir()
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "README.md").write_text("# Skills\n", encoding="utf-8")
    (tmp_path / "skills" / "free-models.md").write_text(
        "Use the free model auto selected.\n", encoding="utf-8"
    )
    return tmp_path


def write_llm(root: Path, **fields: object) -> None:
    (root / "llm.yaml").write_text(yaml.safe_dump(fields), encoding="utf-8")
