"""Workspace-rooted tools the model can call."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

MAX_READ = 80_000
MAX_FETCH = 40_000
SHELL_TIMEOUT = 30

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and folders under workspace/ (or an allowed host path).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path inside workspace/. Default is '.'",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a UTF-8 text file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace one occurrence of old_text with new_text in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a shell command with cwd=workspace/. Not network-jailed.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "GET a public http(s) URL and return text.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
]


def openai_tools() -> list[dict[str, Any]]:
    return TOOLS


class ToolError(RuntimeError):
    pass


class Toolbelt:
    def __init__(
        self,
        workspace: Path,
        *,
        allow_host: bool = False,
        fetch_client: httpx.Client | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.allow_host = allow_host
        self.fetch_client = fetch_client

    def resolve(self, raw: str) -> Path:
        path = Path(raw or ".").expanduser()
        if not path.is_absolute():
            path = self.workspace / path
        path = path.resolve()
        if self.allow_host:
            return path
        try:
            path.relative_to(self.workspace)
        except ValueError as exc:
            raise ToolError(
                f"Path {raw!r} is outside workspace/. Pass --allow-host to leave it."
            ) from exc
        return path

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        handlers = {
            "list_dir": self.list_dir,
            "read_file": self.read_file,
            "write_file": self.write_file,
            "edit_file": self.edit_file,
            "run_shell": self.run_shell,
            "web_fetch": self.web_fetch,
        }
        if name not in handlers:
            raise ToolError(f"Unknown tool {name!r}")
        return handlers[name](**{k: v for k, v in arguments.items() if k in _ARGS[name]})

    def list_dir(self, path: str = ".") -> str:
        target = self.resolve(path)
        if not target.exists():
            raise ToolError(f"Not found: {path}")
        if not target.is_dir():
            raise ToolError(f"Not a directory: {path}")
        names = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
        return "\n".join(names) if names else "(empty)"

    def read_file(self, path: str) -> str:
        target = self.resolve(path)
        if not target.is_file():
            raise ToolError(f"Not a file: {path}")
        data = target.read_text(encoding="utf-8", errors="replace")
        if len(data) > MAX_READ:
            return data[:MAX_READ] + f"\n\n[truncated at {MAX_READ} characters]"
        return data

    def write_file(self, path: str, content: str) -> str:
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to {target.relative_to(self.workspace) if _inside(target, self.workspace) else target}"

    def edit_file(self, path: str, old_text: str, new_text: str) -> str:
        current = self.read_file(path)
        count = current.count(old_text)
        if count == 0:
            raise ToolError("old_text was not found in the file.")
        if count > 1:
            raise ToolError(f"old_text matched {count} times; make it unique.")
        target = self.resolve(path)
        target.write_text(current.replace(old_text, new_text, 1), encoding="utf-8")
        return f"Edited {path}"

    def run_shell(self, command: str) -> str:
        if not command or not str(command).strip():
            raise ToolError("command is required")
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=SHELL_TIMEOUT,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolError(f"Command timed out after {SHELL_TIMEOUT}s") from exc
        out = (completed.stdout or "") + (completed.stderr or "")
        if completed.returncode != 0:
            out = f"exit {completed.returncode}\n{out}"
        return out[-MAX_READ:] or "(no output)"

    def web_fetch(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ToolError("url must be http or https")
        own = self.fetch_client is None
        http = self.fetch_client or httpx.Client(timeout=20.0, follow_redirects=True)
        try:
            response = http.get(url, headers={"User-Agent": "AnywhereBot/0.1"})
            text = response.text
            header = f"HTTP {response.status_code} {url}\n\n"
            if len(text) > MAX_FETCH:
                text = text[:MAX_FETCH] + f"\n\n[truncated at {MAX_FETCH} characters]"
            return header + text
        except httpx.HTTPError as exc:
            raise ToolError(f"Fetch failed: {exc}") from exc
        finally:
            if own:
                http.close()


_ARGS = {
    "list_dir": {"path"},
    "read_file": {"path"},
    "write_file": {"path", "content"},
    "edit_file": {"path", "old_text", "new_text"},
    "run_shell": {"command"},
    "web_fetch": {"url"},
}


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
