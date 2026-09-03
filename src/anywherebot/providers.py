"""Free-first LLM provider presets and `provider: auto` resolution.

Verified against live provider docs / OpenRouter GET /api/v1/models on 2026-09-03.
Do not default to paid slugs (ox-alpha / z-ai/glm-5.3-flash, moonshotai/kimi-k3).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx

# OpenRouter :free slugs that advertise tools/function calling (2026-09-03).
# `openrouter/free` is a $0 router that picks among current free models.
FREE_OPENROUTER_SLUGS: tuple[str, ...] = (
    "openrouter/free",
    "minimax/minimax-m3:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "z-ai/glm-5.2:free",
    "thinkingmachines/inkling:free",
    "poolside/laguna-s-2.1:free",
    "cohere/north-mini-code:free",
)

# Paid models people confuse with "free flash / open" — never auto-select these.
PAID_NOT_FREE: tuple[str, ...] = (
    "z-ai/glm-5.3-flash",  # formerly marketed as ox-alpha
    "moonshotai/kimi-k3",
)

DEFAULT_OLLAMA_MODEL = "llama3.2"
DEFAULT_OPENROUTER_MODEL = "openrouter/free"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"

OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

DUMMY_OLLAMA_KEY = "ollama"

AUTO_ORDER = ("ollama", "openrouter", "groq", "gemini")

KEY_HELP = """\
No free LLM is reachable.

AnywhereBot prefers live FREE models. Get one of these (no paid plan required):

  1. Ollama (local, no API key)
     https://ollama.com
     ollama pull llama3.2

  2. OpenRouter — hosted $0 router + :free slugs
     https://openrouter.ai/keys
     export OPENROUTER_API_KEY=...
     default model: openrouter/free

  3. Groq — free tier (llama-3.3-70b-versatile shut down 2026-08-16)
     https://console.groq.com
     export GROQ_API_KEY=...
     default model: openai/gpt-oss-20b

  4. Gemini — free tier, OpenAI-compatible endpoint
     https://aistudio.google.com/apikey
     export GEMINI_API_KEY=...
     default model: gemini-3.6-flash

Copy .env.example to .env, set one key, then:
  python -m anywherebot doctor

Paid (do not use as the default): ox-alpha is now z-ai/glm-5.3-flash;
moonshotai/kimi-k3 is also paid.
"""


class ProviderError(RuntimeError):
    """No usable free provider, or a pinned provider is misconfigured."""


@dataclass
class LLMSettings:
    provider: str
    model: str
    base_url: str
    api_key_env: str
    api_key: str
    timeout_s: float = 120.0
    via: str = ""
    fallbacks: list[LLMSettings] = field(default_factory=list)

    def describe(self) -> str:
        env_note = (
            f"via {self.api_key_env}"
            if self.api_key_env and self.api_key_env != "OLLAMA"
            else "no API key needed"
        )
        extra = f" ({self.via})" if self.via else ""
        return (
            f"provider={self.provider}{extra}  model={self.model}\n"
            f"    base_url={self.base_url}\n"
            f"    {env_note}"
        )


PRESETS: dict[str, dict[str, str]] = {
    "ollama": {
        "base_url": OLLAMA_BASE_URL,
        "model": DEFAULT_OLLAMA_MODEL,
        "api_key_env": "OLLAMA",
    },
    "openrouter": {
        "base_url": OPENROUTER_BASE_URL,
        "model": DEFAULT_OPENROUTER_MODEL,
        "api_key_env": "OPENROUTER_API_KEY",
    },
    "groq": {
        "base_url": GROQ_BASE_URL,
        "model": DEFAULT_GROQ_MODEL,
        "api_key_env": "GROQ_API_KEY",
    },
    "gemini": {
        "base_url": GEMINI_BASE_URL,
        "model": DEFAULT_GEMINI_MODEL,
        "api_key_env": "GEMINI_API_KEY",
    },
    "openai_compat": {
        "base_url": "",
        "model": "",
        "api_key_env": "OPENAI_API_KEY",
    },
}


def env_value(env: Mapping[str, str], name: str) -> str:
    return (env.get(name) or "").strip()


def _ollama_origin(base_url: str) -> str:
    origin = base_url.rstrip("/")
    if origin.endswith("/v1"):
        origin = origin[: -len("/v1")]
    return origin


def ollama_reachable(
    base_url: str = OLLAMA_BASE_URL,
    timeout_s: float = 0.4,
    client: httpx.Client | None = None,
) -> bool:
    """True if something that looks like Ollama answers on the host."""
    url = f"{_ollama_origin(base_url)}/api/tags"
    own = client is None
    http = client or httpx.Client(timeout=timeout_s)
    try:
        response = http.get(url)
        return response.status_code < 500
    except httpx.HTTPError:
        return False
    finally:
        if own:
            http.close()


def fetch_ollama_tags(
    base_url: str = OLLAMA_BASE_URL,
    timeout_s: float = 0.8,
    client: httpx.Client | None = None,
) -> dict[str, Any] | None:
    url = f"{_ollama_origin(base_url)}/api/tags"
    own = client is None
    http = client or httpx.Client(timeout=timeout_s)
    try:
        response = http.get(url)
        if response.status_code >= 400:
            return None
        data = response.json()
        return data if isinstance(data, dict) else None
    except (httpx.HTTPError, ValueError):
        return None
    finally:
        if own:
            http.close()


def pick_ollama_model(
    tags: Mapping[str, Any] | None,
    preferred: str = DEFAULT_OLLAMA_MODEL,
) -> str:
    """Use llama3.2 if present, else the first local tag, else the preferred default."""
    models = []
    if tags:
        for item in tags.get("models") or []:
            name = str(item.get("name") or item.get("model") or "")
            if name:
                models.append(name)
    if not models:
        return preferred
    for candidate in (preferred, "llama3.1", "llama3"):
        for name in models:
            bare = name.split(":", 1)[0]
            if bare == candidate or name.startswith(candidate):
                return name
    return models[0]


def _key_for(provider: str, env: Mapping[str, str]) -> str:
    if provider == "ollama":
        return env_value(env, "OLLAMA_API_KEY") or DUMMY_OLLAMA_KEY
    if provider == "openai_compat":
        return env_value(env, "OPENAI_API_KEY") or DUMMY_OLLAMA_KEY
    preset = PRESETS[provider]
    return env_value(env, preset["api_key_env"])


def has_key(provider: str, env: Mapping[str, str]) -> bool:
    if provider == "ollama":
        return True
    key = _key_for(provider, env)
    return bool(key) and key != DUMMY_OLLAMA_KEY


def settings_for(
    provider: str,
    env: Mapping[str, str],
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key_env: str | None = None,
    timeout_s: float = 120.0,
    via: str = "",
) -> LLMSettings:
    if provider not in PRESETS:
        raise ProviderError(
            f"Unknown provider {provider!r}. "
            f"Use one of: auto, {', '.join(PRESETS)}"
        )
    preset = PRESETS[provider]
    resolved_model = (model or "").strip() or preset["model"]
    resolved_url = (base_url or "").strip() or preset["base_url"]
    resolved_env = (api_key_env or "").strip() or preset["api_key_env"]
    if provider == "openai_compat" and not resolved_url:
        raise ProviderError(
            "provider: openai_compat needs base_url (vLLM / llama.cpp / LM Studio)."
        )
    if provider == "openai_compat" and not resolved_model:
        raise ProviderError("provider: openai_compat needs model.")
    key = env_value(env, resolved_env) if resolved_env not in ("", "OLLAMA") else ""
    if provider == "ollama":
        key = key or DUMMY_OLLAMA_KEY
    elif provider == "openai_compat":
        key = key or DUMMY_OLLAMA_KEY
    elif not key:
        raise ProviderError(
            f"provider: {provider} needs {resolved_env} in the environment.\n\n{KEY_HELP}"
        )
    return LLMSettings(
        provider=provider,
        model=resolved_model,
        base_url=resolved_url.rstrip("/") + ("/" if provider == "gemini" else ""),
        api_key_env=resolved_env,
        api_key=key,
        timeout_s=timeout_s,
        via=via,
    )


def resolve_auto(
    env: Mapping[str, str] | None = None,
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key_env: str | None = None,
    timeout_s: float = 120.0,
    probe_ollama: Callable[[str], bool] | None = None,
    ollama_tags: Mapping[str, Any] | None = None,
) -> LLMSettings:
    """Ollama → OpenRouter → Groq → Gemini. Raises ProviderError if none work."""
    env = env if env is not None else os.environ
    probe = probe_ollama or (lambda url: ollama_reachable(url))
    ollama_url = (base_url or "").strip() or env_value(env, "ANYWHEREBOT_BASE_URL") or OLLAMA_BASE_URL
    # Only treat an override URL as Ollama when it still looks local-ish, or when
    # no cloud key is the intended target — always probe the given URL first.
    if probe(ollama_url):
        chosen_model = (model or "").strip()
        if not chosen_model:
            tags = ollama_tags if ollama_tags is not None else fetch_ollama_tags(ollama_url)
            chosen_model = pick_ollama_model(tags, DEFAULT_OLLAMA_MODEL)
        return settings_for(
            "ollama",
            env,
            model=chosen_model,
            base_url=ollama_url,
            api_key_env=api_key_env,
            timeout_s=timeout_s,
            via="auto: Ollama answered",
        )

    cloud_order = ("openrouter", "groq", "gemini")
    chosen: LLMSettings | None = None
    fallbacks: list[LLMSettings] = []
    for name in cloud_order:
        if not has_key(name, env):
            continue
        # A yaml/env model pin applies to the first cloud provider that wins
        # (typically an OpenRouter :free slug). Later fallbacks keep defaults.
        use_model = (model or "").strip() if chosen is None else None
        use_url = (base_url or "").strip() if chosen is None else None
        try:
            item = settings_for(
                name,
                env,
                model=use_model,
                base_url=use_url,
                api_key_env=api_key_env if chosen is None else None,
                timeout_s=timeout_s,
                via=f"auto: {PRESETS[name]['api_key_env']}",
            )
        except ProviderError:
            continue
        if chosen is None:
            chosen = item
        else:
            fallbacks.append(item)
    if chosen is None:
        raise ProviderError(KEY_HELP)
    if chosen.provider == "openrouter" and fallbacks:
        chosen.fallbacks = fallbacks
    return chosen


def resolve_provider(
    provider: str,
    env: Mapping[str, str] | None = None,
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key_env: str | None = None,
    timeout_s: float = 120.0,
    probe_ollama: Callable[[str], bool] | None = None,
    ollama_tags: Mapping[str, Any] | None = None,
) -> LLMSettings:
    env = env if env is not None else os.environ
    name = (provider or "auto").strip().lower()
    if name == "auto":
        return resolve_auto(
            env,
            model=model,
            base_url=base_url,
            api_key_env=api_key_env,
            timeout_s=timeout_s,
            probe_ollama=probe_ollama,
            ollama_tags=ollama_tags,
        )
    return settings_for(
        name,
        env,
        model=model,
        base_url=base_url,
        api_key_env=api_key_env,
        timeout_s=timeout_s,
    )
