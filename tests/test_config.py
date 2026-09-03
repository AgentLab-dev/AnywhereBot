from __future__ import annotations

from pathlib import Path

from anywherebot.config import BotConfig

from tests.conftest import write_llm


def test_load_auto_openrouter(bot_root: Path) -> None:
    config = BotConfig.load(
        bot_root,
        env={"OPENROUTER_API_KEY": "sk-or-test"},
        probe_ollama=lambda _url: False,
    )
    assert config.llm.provider == "openrouter"
    assert config.llm.model == "openrouter/free"
    prompt = config.system_prompt()
    assert "Macha" in prompt
    assert "free-models.md" in prompt
    assert "Use the free model auto selected." in prompt
    assert "README.md" not in prompt


def test_env_override_pins_provider(bot_root: Path) -> None:
    write_llm(bot_root, provider="auto")
    config = BotConfig.load(
        bot_root,
        env={
            "ANYWHEREBOT_PROVIDER": "groq",
            "GROQ_API_KEY": "g",
            "OPENROUTER_API_KEY": "or",
        },
        probe_ollama=lambda _url: False,
    )
    assert config.llm.provider == "groq"
    assert config.llm.model == "openai/gpt-oss-20b"


def test_default_yaml_is_auto() -> None:
    repo = Path(__file__).resolve().parents[1]
    text = (repo / "llm.yaml").read_text(encoding="utf-8")
    assert "provider: auto" in text
    assert "ox-alpha" in text
    assert "kimi-k3" in text
    assert "openrouter/free" in text
    assert "minimax/minimax-m3:free" in text
