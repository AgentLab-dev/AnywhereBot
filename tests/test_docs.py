from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_readme_has_free_models_section() -> None:
    text = (REPO / "README.md").read_text(encoding="utf-8")
    assert "## Free models (as of 2026-09-03)" in text
    assert "provider: auto" in text
    assert "openrouter/free" in text
    assert "openai/gpt-oss-20b" in text
    assert "gemini-3.6-flash" in text
    assert "z-ai/glm-5.3-flash" in text
    assert "moonshotai/kimi-k3" in text
    assert "ox-alpha" in text


def test_bot_md_stays_general_and_mentions_free_model() -> None:
    text = (REPO / "bot.md").read_text(encoding="utf-8")
    assert "AnywhereBot" in text
    assert "free" in text.lower()
    assert "ox-alpha" in text
    assert "kimi-k3" in text


def test_gitignore_blocks_weight_dumps() -> None:
    text = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert "*.gguf" in text
    assert "*.safetensors" in text
    skip = {".git", ".venv", "venv", "__pycache__"}
    leaked = [
        path
        for pattern in ("*.gguf", "*.safetensors")
        for path in REPO.rglob(pattern)
        if not skip.intersection(path.parts)
    ]
    assert leaked == []


def test_no_secrets_in_tree() -> None:
    example = (REPO / ".env.example").read_text(encoding="utf-8")
    assert "sk-" not in example
    assert "OPENROUTER_API_KEY=" in example or "# OPENROUTER_API_KEY=" in example
