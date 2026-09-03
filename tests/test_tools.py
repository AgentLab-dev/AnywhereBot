from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from anywherebot.tools import ToolError, Toolbelt, openai_tools


def test_workspace_roundtrip(tmp_path: Path) -> None:
    tools = Toolbelt(tmp_path)
    assert "Wrote" in tools.call(
        "write_file", {"path": "a.txt", "content": "alpha"}
    )
    assert tools.call("read_file", {"path": "a.txt"}) == "alpha"
    assert "Edited" in tools.call(
        "edit_file", {"path": "a.txt", "old_text": "alpha", "new_text": "beta"}
    )
    assert tools.call("read_file", {"path": "a.txt"}) == "beta"
    listing = tools.call("list_dir", {"path": "."})
    assert "a.txt" in listing


def test_rejects_escape(tmp_path: Path) -> None:
    tools = Toolbelt(tmp_path)
    with pytest.raises(ToolError, match="outside workspace"):
        tools.call("read_file", {"path": "../secret.txt"})


def test_allow_host_reads_outside(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("ok", encoding="utf-8")
    tools = Toolbelt(tmp_path, allow_host=True)
    assert tools.call("read_file", {"path": str(outside)}) == "ok"


def test_run_shell(tmp_path: Path) -> None:
    tools = Toolbelt(tmp_path)
    out = tools.call("run_shell", {"command": "pwd"})
    assert str(tmp_path.resolve()) in out


def test_web_fetch_mocked(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="hello world", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    tools = Toolbelt(tmp_path, fetch_client=client)
    body = tools.call("web_fetch", {"url": "https://example.com"})
    assert "HTTP 200" in body
    assert "hello world" in body
    with pytest.raises(ToolError):
        tools.call("web_fetch", {"url": "file:///etc/passwd"})


def test_openai_tools_cover_workspace_ops() -> None:
    names = {t["function"]["name"] for t in openai_tools()}
    assert names == {
        "list_dir",
        "read_file",
        "write_file",
        "edit_file",
        "run_shell",
        "web_fetch",
    }
