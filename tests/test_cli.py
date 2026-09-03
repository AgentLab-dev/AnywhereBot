from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from anywherebot.cli import main
from anywherebot.providers import KEY_HELP
from anywherebot.serve import PAGE

_CLEAR = (
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "ANYWHEREBOT_PROVIDER",
    "ANYWHEREBOT_MODEL",
    "ANYWHEREBOT_BASE_URL",
    "ANYWHEREBOT_API_KEY_ENV",
)


def _clear_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _CLEAR:
        monkeypatch.delenv(name, raising=False)


def test_doctor_no_backend_prints_help(
    bot_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(bot_root)
    monkeypatch.setattr("anywherebot.providers.ollama_reachable", lambda *a, **k: False)
    _clear_provider_env(monkeypatch)
    code = main(["--root", str(bot_root), "doctor"])
    captured = capsys.readouterr()
    assert code == 1
    assert "openrouter.ai/keys" in captured.err
    assert "console.groq.com" in captured.err
    assert "aistudio.google.com" in captured.err
    assert "ollama.com" in captured.err
    assert KEY_HELP.strip() in captured.err.strip()


def test_doctor_ok_openrouter(
    bot_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(bot_root)
    monkeypatch.setattr("anywherebot.providers.ollama_reachable", lambda *a, **k: False)
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"id": "openrouter/free"}, {"id": "minimax/minimax-m3:free"}]},
            request=request,
        )

    real_client = httpx.Client
    monkeypatch.setattr(
        "anywherebot.llm.httpx.Client",
        lambda *a, **k: real_client(transport=httpx.MockTransport(handler)),
    )
    code = main(["--root", str(bot_root), "doctor"])
    out = capsys.readouterr().out
    assert code == 0
    assert "provider=openrouter" in out
    assert "openrouter/free" in out
    assert "OPENROUTER_API_KEY" in out
    assert "Ollama on localhost:11434" in out
    assert "kimi-k3" in out
    assert "Macha free-model path" in out


def test_doctor_does_not_crash_on_unexpected_error(
    bot_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(bot_root)

    def boom(*_a, **_k):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr("anywherebot.cli.BotConfig.load", boom)
    code = main(["--root", str(bot_root), "doctor"])
    err = capsys.readouterr().err
    assert code == 1
    assert "disk on fire" in err
    assert "openrouter.ai/keys" in err


def test_once_mocked(
    bot_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from anywherebot.llm import ChatResponse

    class Fake:
        def __init__(self, *_a, **_k) -> None:
            pass

        def chat(self, messages, tools=None, *, stream=False, on_token=None):
            return ChatResponse(content="ok-from-fake")

    monkeypatch.setattr("anywherebot.providers.ollama_reachable", lambda *a, **k: False)
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setattr("anywherebot.agent.LLMClient", Fake)
    code = main(["--root", str(bot_root), "once", "hello"])
    assert code == 0
    assert "ok-from-fake" in capsys.readouterr().out


def test_models_lists_ids(
    bot_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("anywherebot.providers.ollama_reachable", lambda *a, **k: False)
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "g")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models")
        return httpx.Response(
            200,
            json={"data": [{"id": "gemini-3.6-flash"}]},
            request=request,
        )

    real_client = httpx.Client
    monkeypatch.setattr(
        "anywherebot.llm.httpx.Client",
        lambda *a, **k: real_client(transport=httpx.MockTransport(handler)),
    )
    code = main(["--root", str(bot_root), "models"])
    out = capsys.readouterr().out
    assert code == 0
    assert "gemini-3.6-flash" in out


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "doctor" in out
    assert "Macha" in out


def test_macha_module_calls_same_cli(capsys: pytest.CaptureFixture[str]) -> None:
    from macha.__main__ import main as macha_main

    assert macha_main(["--help"]) == 0
    assert "Macha" in capsys.readouterr().out


def test_serve_page_is_macha() -> None:
    assert "<title>Macha</title>" in PAGE
    assert "<h1>Macha</h1>" in PAGE
    assert "AnywhereBot" not in PAGE
