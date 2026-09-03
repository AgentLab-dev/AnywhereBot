from __future__ import annotations

import pytest

from anywherebot.providers import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_GROQ_MODEL,
    DEFAULT_OPENROUTER_MODEL,
    FREE_OPENROUTER_SLUGS,
    KEY_HELP,
    PAID_NOT_FREE,
    ProviderError,
    pick_ollama_model,
    resolve_auto,
    resolve_provider,
    settings_for,
)


def test_free_slugs_are_the_verified_2026_09_03_list() -> None:
    assert FREE_OPENROUTER_SLUGS == (
        "openrouter/free",
        "minimax/minimax-m3:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "z-ai/glm-5.2:free",
        "thinkingmachines/inkling:free",
        "poolside/laguna-s-2.1:free",
        "cohere/north-mini-code:free",
    )
    assert "z-ai/glm-5.3-flash" in PAID_NOT_FREE
    assert "moonshotai/kimi-k3" in PAID_NOT_FREE
    assert DEFAULT_OPENROUTER_MODEL == "openrouter/free"
    assert DEFAULT_GROQ_MODEL == "openai/gpt-oss-20b"
    assert DEFAULT_GEMINI_MODEL == "gemini-3.6-flash"


def test_auto_picks_ollama_when_probe_succeeds() -> None:
    settings = resolve_auto(
        {},
        probe_ollama=lambda _url: True,
        ollama_tags={"models": [{"name": "llama3.2:latest"}]},
    )
    assert settings.provider == "ollama"
    assert settings.model.startswith("llama3.2")
    assert settings.api_key == "ollama"


def test_auto_uses_already_pulled_ollama_model() -> None:
    settings = resolve_auto(
        {},
        probe_ollama=lambda _url: True,
        ollama_tags={"models": [{"name": "qwen2.5:7b"}]},
    )
    assert settings.model == "qwen2.5:7b"


def test_auto_openrouter_before_groq_and_gemini() -> None:
    env = {
        "OPENROUTER_API_KEY": "or-key",
        "GROQ_API_KEY": "groq-key",
        "GEMINI_API_KEY": "gem-key",
    }
    settings = resolve_auto(env, probe_ollama=lambda _url: False)
    assert settings.provider == "openrouter"
    assert settings.model == "openrouter/free"
    assert [f.provider for f in settings.fallbacks] == ["groq", "gemini"]


def test_auto_groq_when_no_openrouter() -> None:
    settings = resolve_auto(
        {"GROQ_API_KEY": "g", "GEMINI_API_KEY": "m"},
        probe_ollama=lambda _url: False,
    )
    assert settings.provider == "groq"
    assert settings.model == "openai/gpt-oss-20b"
    assert settings.fallbacks == []


def test_auto_gemini_last() -> None:
    settings = resolve_auto(
        {"GEMINI_API_KEY": "m"},
        probe_ollama=lambda _url: False,
    )
    assert settings.provider == "gemini"
    assert settings.model == "gemini-3.6-flash"
    assert settings.base_url.endswith("/")


def test_auto_none_raises_key_help() -> None:
    with pytest.raises(ProviderError) as exc:
        resolve_auto({}, probe_ollama=lambda _url: False)
    assert "openrouter.ai/keys" in str(exc.value)
    assert "console.groq.com" in str(exc.value)
    assert "aistudio.google.com" in str(exc.value)
    assert KEY_HELP.strip() == str(exc.value).strip()


def test_empty_env_values_do_not_count_as_keys() -> None:
    with pytest.raises(ProviderError):
        resolve_auto(
            {"OPENROUTER_API_KEY": "  ", "GROQ_API_KEY": ""},
            probe_ollama=lambda _url: False,
        )


def test_explicit_groq_requires_key() -> None:
    with pytest.raises(ProviderError, match="GROQ_API_KEY"):
        settings_for("groq", {})


def test_resolve_provider_auto_and_pin() -> None:
    pinned = resolve_provider(
        "openrouter",
        {"OPENROUTER_API_KEY": "k"},
        model="minimax/minimax-m3:free",
    )
    assert pinned.model == "minimax/minimax-m3:free"
    auto = resolve_provider(
        "auto",
        {"OPENROUTER_API_KEY": "k"},
        probe_ollama=lambda _url: False,
    )
    assert auto.model == "openrouter/free"


def test_pick_ollama_prefers_llama32() -> None:
    assert (
        pick_ollama_model(
            {"models": [{"name": "mistral"}, {"name": "llama3.2:latest"}]}
        )
        == "llama3.2:latest"
    )


def test_openai_compat_needs_url_and_model() -> None:
    with pytest.raises(ProviderError, match="base_url"):
        settings_for("openai_compat", {}, model="x")
    got = settings_for(
        "openai_compat",
        {},
        model="local-model",
        base_url="http://127.0.0.1:1234/v1",
    )
    assert got.api_key == "ollama"
