"""OpenAI-compatible chat client with optional OpenRouter 429 fallback."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from anywherebot.providers import LLMSettings

OnToken = Callable[[str], None]


class LLMError(RuntimeError):
    pass


class RateLimited(LLMError):
    pass


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    raw_arguments: str = ""


@dataclass
class ChatResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    provider: str = ""


def _headers(settings: LLMSettings) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }
    if "openrouter.ai" in settings.base_url:
        headers["HTTP-Referer"] = "https://github.com/AgentLab-dev/AnywhereBot"
        headers["X-Title"] = "Macha"
    return headers


def _parse_tool_calls(raw: list[dict[str, Any]] | None) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for item in raw or []:
        fn = item.get("function") or {}
        raw_args = fn.get("arguments") or ""
        if not isinstance(raw_args, str):
            raw_args = json.dumps(raw_args)
        try:
            parsed = json.loads(raw_args) if raw_args.strip() else {}
        except json.JSONDecodeError:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {"value": parsed}
        calls.append(
            ToolCall(
                id=str(item.get("id") or f"call_{len(calls)}"),
                name=str(fn.get("name") or ""),
                arguments=parsed,
                raw_arguments=raw_args,
            )
        )
    return calls


def _parse_message(message: dict[str, Any]) -> ChatResponse:
    content = message.get("content")
    if content is None:
        text = ""
    elif isinstance(content, list):
        text = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    else:
        text = str(content)
    return ChatResponse(
        content=text,
        tool_calls=_parse_tool_calls(message.get("tool_calls")),
    )


def _raise_http(response: httpx.Response) -> None:
    body = (response.text or "")[:400]
    detail = f"HTTP {response.status_code} from {response.request.url}: {body}"
    if response.status_code == 429:
        raise RateLimited(detail)
    raise LLMError(detail)


def _consume_sse(response: httpx.Response, on_token: OnToken | None) -> ChatResponse:
    content_parts: list[str] = []
    tool_acc: dict[int, dict[str, Any]] = {}
    for line in response.iter_lines():
        if not line:
            continue
        if line.startswith("data:"):
            payload = line[5:].strip()
        else:
            continue
        if payload == "[DONE]":
            break
        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            continue
        choice = (chunk.get("choices") or [{}])[0]
        delta = choice.get("delta") or {}
        piece = delta.get("content") or ""
        if piece:
            content_parts.append(piece)
            if on_token:
                on_token(piece)
        for tc in delta.get("tool_calls") or []:
            index = int(tc.get("index") or 0)
            slot = tool_acc.setdefault(
                index, {"id": "", "function": {"name": "", "arguments": ""}}
            )
            if tc.get("id"):
                slot["id"] = tc["id"]
            fn = tc.get("function") or {}
            if fn.get("name"):
                slot["function"]["name"] += fn["name"]
            if fn.get("arguments"):
                slot["function"]["arguments"] += fn["arguments"]
    ordered = [tool_acc[i] for i in sorted(tool_acc)]
    return ChatResponse(
        content="".join(content_parts),
        tool_calls=_parse_tool_calls(ordered),
    )


class LLMClient:
    def __init__(
        self,
        settings: LLMSettings,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self._client = client

    def _http(self, settings: LLMSettings) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=settings.timeout_s)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        stream: bool = False,
        on_token: OnToken | None = None,
    ) -> ChatResponse:
        chain = [self.settings, *self.settings.fallbacks]
        last_error: Exception | None = None
        for index, cfg in enumerate(chain):
            try:
                response = self._chat_once(
                    cfg, messages, tools, stream=stream, on_token=on_token
                )
                response.model = cfg.model
                response.provider = cfg.provider
                return response
            except RateLimited as exc:
                last_error = exc
                if index == len(chain) - 1:
                    raise
                continue
        assert last_error is not None
        raise last_error

    def list_models(self) -> list[str]:
        http = self._http(self.settings)
        own = self._client is None
        try:
            response = http.get(
                f"{self.settings.base_url.rstrip('/')}/models",
                headers=_headers(self.settings),
            )
            if response.status_code >= 400:
                _raise_http(response)
            data = response.json()
            items = data.get("data") or data.get("models") or []
            ids: list[str] = []
            for item in items:
                if isinstance(item, dict):
                    mid = item.get("id") or item.get("name")
                    if mid:
                        ids.append(str(mid))
                elif item:
                    ids.append(str(item))
            return ids
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not list models: {exc}") from exc
        finally:
            if own:
                http.close()

    def _chat_once(
        self,
        settings: LLMSettings,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        *,
        stream: bool,
        on_token: OnToken | None,
    ) -> ChatResponse:
        payload: dict[str, Any] = {"model": settings.model, "messages": messages}
        if tools:
            payload["tools"] = tools
        if stream:
            payload["stream"] = True
        http = self._http(settings)
        own = self._client is None
        url = f"{settings.base_url.rstrip('/')}/chat/completions"
        try:
            if stream:
                with http.stream(
                    "POST", url, headers=_headers(settings), json=payload
                ) as response:
                    if response.status_code >= 400:
                        response.read()
                        _raise_http(response)
                    return _consume_sse(response, on_token)
            response = http.post(url, headers=_headers(settings), json=payload)
            if response.status_code >= 400:
                _raise_http(response)
            data = response.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            return _parse_message(message)
        except (RateLimited, LLMError):
            raise
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        finally:
            if own:
                http.close()
