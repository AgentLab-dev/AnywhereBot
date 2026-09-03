"""Load bot.md, skills, and llm.yaml from a folder of plain files."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from anywherebot.providers import LLMSettings, env_value, resolve_provider

ENV_OVERRIDES = (
    ("ANYWHEREBOT_PROVIDER", "provider"),
    ("ANYWHEREBOT_MODEL", "model"),
    ("ANYWHEREBOT_BASE_URL", "base_url"),
    ("ANYWHEREBOT_API_KEY_ENV", "api_key_env"),
)


class ConfigError(ValueError):
    pass


def find_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for path in (here, *here.parents):
        if (path / "llm.yaml").is_file() and (path / "bot.md").is_file():
            return path
    return here


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Missing {path}. Clone the repo or copy llm.yaml.")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must be a mapping.")
    return data


def _load_skills(skills_dir: Path) -> list[tuple[str, str]]:
    if not skills_dir.is_dir():
        return []
    loaded: list[tuple[str, str]] = []
    for path in sorted(skills_dir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        loaded.append((path.name, path.read_text(encoding="utf-8").strip()))
    return loaded


@dataclass
class BotConfig:
    root: Path
    workspace: Path
    sessions_dir: Path
    allow_host: bool
    llm: LLMSettings
    bot_md: str
    skills: list[tuple[str, str]]

    def system_prompt(self) -> str:
        parts = [self.bot_md.strip()]
        for name, body in self.skills:
            parts.append(f"\n\n# Skill: {name}\n\n{body}")
        return "".join(parts).strip() + "\n"

    @classmethod
    def load(
        cls,
        root: Path | None = None,
        *,
        allow_host: bool = False,
        env: dict[str, str] | None = None,
        probe_ollama=None,
        ollama_tags=None,
    ) -> BotConfig:
        root = find_root(root)
        environ = env if env is not None else os.environ
        if env is None:
            load_dotenv(root / ".env", override=False)
            environ = os.environ
        raw = _read_yaml(root / "llm.yaml")
        for env_name, key in ENV_OVERRIDES:
            value = env_value(environ, env_name)
            if value:
                raw[key] = value
        provider = str(raw.get("provider") or "auto")
        timeout = float(raw.get("timeout_s") or 120)
        llm = resolve_provider(
            provider,
            environ,
            model=raw.get("model"),
            base_url=raw.get("base_url"),
            api_key_env=raw.get("api_key_env"),
            timeout_s=timeout,
            probe_ollama=probe_ollama,
            ollama_tags=ollama_tags,
        )
        bot_path = root / "bot.md"
        if not bot_path.is_file():
            raise ConfigError(f"Missing {bot_path}.")
        workspace = root / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        sessions = root / ".anywherebot" / "sessions"
        return cls(
            root=root,
            workspace=workspace,
            sessions_dir=sessions,
            allow_host=allow_host,
            llm=llm,
            bot_md=bot_path.read_text(encoding="utf-8"),
            skills=_load_skills(root / "skills"),
        )
