from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from anywherebot.llm import LLMClient, LLMError, RateLimited
from anywherebot.providers import LLMSettings


def _settings(provider: str, model: str, url: str, key: str = "k") -> LLMSettings:
    return LLMSettings(
        provider=provider,
        model=model,
        base_url=url,
        api_key_env=f"{provider.upper()}_API_KEY",
        api_key=key,
    )


class ScriptedTransport(httpx.BaseTransport):
    def __init__(self, script: list[tuple[int, dict[str, Any] | str]]) -> None:
        self.script = list(script)
        self.calls: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        status, body = self.script.pop(0)
        if isinstance(body, str):
            content = body.encode("utf-8")
        else:
            content = json.dumps(body).encode("utf-8")
        return httpx.Response(status, content=content, request=request)


def test_chat_parses_tool_calls() -> None:
    transport = ScriptedTransport(
        [
            (
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "c1",
                                        "function": {
                                            "name": "list_dir",
                                            "arguments": '{"path": "."}',
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                },
            )
        ]
    )
    client = httpx.Client(transport=transport)
    llm = LLMClient(
        _settings("openrouter", "openrouter/free", "https://openrouter.ai/api/v1"),
        client=client,
    )
    response = llm.chat([{"role": "user", "content": "hi"}])
    assert response.tool_calls[0].name == "list_dir"
    assert response.tool_calls[0].arguments == {"path": "."}
    req = transport.calls[0]
    assert req.headers["Authorization"] == "Bearer k"
    assert req.headers["X-Title"] == "AnywhereBot"


def test_429_falls_through_to_groq() -> None:
    openrouter = _settings(
        "openrouter", "openrouter/free", "https://openrouter.ai/api/v1", "or"
    )
    groq = _settings("groq", "openai/gpt-oss-20b", "https://api.groq.com/openai/v1", "g")
    openrouter.fallbacks = [groq]
    transport = ScriptedTransport(
        [
            (429, {"error": "rate limited"}),
            (
                200,
                {"choices": [{"message": {"content": "from groq"}}]},
            ),
        ]
    )
    llm = LLMClient(openrouter, client=httpx.Client(transport=transport))
    response = llm.chat([{"role": "user", "content": "hi"}])
    assert response.content == "from groq"
    assert response.provider == "groq"
    assert response.model == "openai/gpt-oss-20b"
    assert len(transport.calls) == 2


def test_429_without_fallback_raises() -> None:
    transport = ScriptedTransport([(429, {"error": "nope"})])
    llm = LLMClient(
        _settings("openrouter", "openrouter/free", "https://openrouter.ai/api/v1"),
        client=httpx.Client(transport=transport),
    )
    with pytest.raises(RateLimited):
        llm.chat([{"role": "user", "content": "hi"}])


def test_http_error() -> None:
    transport = ScriptedTransport([(500, "boom")])
    llm = LLMClient(
        _settings("groq", "openai/gpt-oss-20b", "https://api.groq.com/openai/v1"),
        client=httpx.Client(transport=transport),
    )
    with pytest.raises(LLMError, match="500"):
        llm.chat([{"role": "user", "content": "hi"}])
