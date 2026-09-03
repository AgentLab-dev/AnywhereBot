"""Tool-calling agent loop."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol

from anywherebot.config import BotConfig
from anywherebot.llm import ChatResponse, LLMClient, ToolCall
from anywherebot.memory import SessionLog
from anywherebot.tools import Toolbelt, openai_tools

MAX_TOOL_ROUNDS = 12

OnToken = Callable[[str], None]
OnTool = Callable[[str, dict[str, Any], str], None]


class ChatModel(Protocol):
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        stream: bool = False,
        on_token: OnToken | None = None,
    ) -> ChatResponse: ...


def _assistant_message(response: ChatResponse) -> dict[str, Any]:
    message: dict[str, Any] = {
        "role": "assistant",
        "content": response.content or "",
    }
    if response.tool_calls:
        message["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": call.raw_arguments
                    or json.dumps(call.arguments),
                },
            }
            for call in response.tool_calls
        ]
    return message


class Agent:
    def __init__(
        self,
        config: BotConfig,
        llm: ChatModel | None = None,
        tools: Toolbelt | None = None,
        session: SessionLog | None = None,
    ) -> None:
        self.config = config
        self.llm = llm or LLMClient(config.llm)
        self.tools = tools or Toolbelt(config.workspace, allow_host=config.allow_host)
        self.session = session or SessionLog(config.sessions_dir)
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": config.system_prompt()}
        ]

    def reset(self) -> None:
        self.messages = [{"role": "system", "content": self.config.system_prompt()}]
        self.session = SessionLog(self.config.sessions_dir)

    def ask(
        self,
        user_text: str,
        *,
        stream: bool = False,
        on_token: OnToken | None = None,
        on_tool: OnTool | None = None,
    ) -> str:
        self.messages.append({"role": "user", "content": user_text})
        self.session.write("user", user_text)
        tools = openai_tools()
        last_response: ChatResponse | None = None
        for _round in range(MAX_TOOL_ROUNDS):
            use_stream = stream and on_token is not None
            last_response = self.llm.chat(
                self.messages,
                tools=tools,
                stream=use_stream,
                on_token=on_token if use_stream else None,
            )
            self.messages.append(_assistant_message(last_response))
            if not last_response.tool_calls:
                reply = last_response.content or ""
                self.session.write("assistant", reply)
                return reply
            for call in last_response.tool_calls:
                output = self._run_tool(call)
                if on_tool:
                    on_tool(call.name, call.arguments, output)
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": output,
                    }
                )
                self.session.write(
                    "tool",
                    output,
                    name=call.name,
                    arguments=call.arguments,
                    tool_call_id=call.id,
                )
        leftover = (last_response.content if last_response else "") or (
            f"Stopped after {MAX_TOOL_ROUNDS} tool rounds without a final answer."
        )
        self.session.write("assistant", leftover, stopped=True)
        return leftover

    def _run_tool(self, call: ToolCall) -> str:
        try:
            return self.tools.call(call.name, call.arguments)
        except Exception as exc:  # noqa: BLE001 — surface any tool failure to the model
            return f"ERROR: {exc}"
