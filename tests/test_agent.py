from __future__ import annotations

from pathlib import Path
from typing import Any

from anywherebot.agent import Agent
from anywherebot.config import BotConfig
from anywherebot.llm import ChatResponse, ToolCall


class ScriptLLM:
    def __init__(self, replies: list[ChatResponse]) -> None:
        self.replies = list(replies)
        self.calls: list[list[dict[str, Any]]] = []

    def chat(self, messages, tools=None, *, stream=False, on_token=None):
        self.calls.append(messages)
        return self.replies.pop(0)


def test_agent_runs_tool_then_final(bot_root: Path) -> None:
    config = BotConfig.load(
        bot_root,
        env={"OPENROUTER_API_KEY": "k"},
        probe_ollama=lambda _url: False,
    )
    llm = ScriptLLM(
        [
            ChatResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="1",
                        name="write_file",
                        arguments={"path": "note.txt", "content": "hi"},
                    )
                ],
            ),
            ChatResponse(content="Wrote the note."),
        ]
    )
    reply = Agent(config, llm=llm).ask("write a note")
    assert reply == "Wrote the note."
    assert (bot_root / "workspace" / "note.txt").read_text(encoding="utf-8") == "hi"
    assert any(m.get("role") == "tool" for m in llm.calls[-1])


def test_agent_plain_reply(bot_root: Path) -> None:
    config = BotConfig.load(
        bot_root,
        env={"GROQ_API_KEY": "k"},
        probe_ollama=lambda _url: False,
    )
    agent = Agent(config, llm=ScriptLLM([ChatResponse(content="hello")]))
    assert agent.ask("hi") == "hello"
    session = next((bot_root / ".anywherebot" / "sessions").glob("*.jsonl"))
    text = session.read_text(encoding="utf-8")
    assert "hello" in text
