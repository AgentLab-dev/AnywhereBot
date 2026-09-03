"""Tiny HTML chat UI (stdlib only)."""

from __future__ import annotations

import json
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from anywherebot.agent import Agent
from anywherebot.config import BotConfig

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>AnywhereBot</title>
  <style>
    :root { color-scheme: dark; }
    body { font: 16px/1.4 system-ui, sans-serif; margin: 0; background: #111; color: #eee; }
    main { max-width: 42rem; margin: 0 auto; padding: 1rem; display: flex; flex-direction: column; height: 100vh; }
    h1 { font-size: 1.1rem; margin: 0 0 .5rem; }
    .meta { color: #9aa; font-size: .85rem; margin-bottom: 1rem; }
    #log { flex: 1; overflow: auto; white-space: pre-wrap; }
    .user { color: #9cf; margin: .6rem 0; }
    .bot { color: #eee; margin: .6rem 0; }
    form { display: flex; gap: .5rem; margin-top: .75rem; }
    textarea { flex: 1; min-height: 3.2rem; resize: vertical; background: #1b1b1b; color: #eee; border: 1px solid #333; padding: .5rem; }
    button { background: #3a7; color: #041; border: 0; padding: 0 .9rem; font-weight: 600; }
  </style>
</head>
<body>
<main>
  <h1>AnywhereBot</h1>
  <div class="meta" id="meta"></div>
  <div id="log"></div>
  <form id="f">
    <textarea id="q" placeholder="Ask the bot…" autofocus></textarea>
    <button type="submit">Send</button>
  </form>
</main>
<script>
const log = document.getElementById('log');
const q = document.getElementById('q');
fetch('/api/status').then(r => r.json()).then(s => {
  document.getElementById('meta').textContent =
    s.provider + ' · ' + s.model + (s.via ? ' · ' + s.via : '');
}).catch(() => {});
document.getElementById('f').onsubmit = async (e) => {
  e.preventDefault();
  const text = q.value.trim();
  if (!text) return;
  q.value = '';
  log.innerHTML += '<div class="user">you: ' + escapeHtml(text) + '</div>';
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: {'content-type': 'application/json'},
    body: JSON.stringify({message: text}),
  });
  const data = await res.json();
  log.innerHTML += '<div class="bot">bot: ' + escapeHtml(data.reply || data.error || '') + '</div>';
  log.scrollTop = log.scrollHeight;
};
function escapeHtml(s) {
  return s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
}
</script>
</body>
</html>
"""


class _Handler(BaseHTTPRequestHandler):
    server_version = "AnywhereBot/0.1"

    def __init__(self, agent: Agent, *args: Any, **kwargs: Any) -> None:
        self.agent = agent
        super().__init__(*args, **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _json(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/status":
            llm = self.agent.config.llm
            self._json(
                200,
                {
                    "provider": llm.provider,
                    "model": llm.model,
                    "via": llm.via,
                    "base_url": llm.base_url,
                },
            )
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/api/chat":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
            message = str(data.get("message") or "").strip()
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json(400, {"error": "invalid JSON"})
            return
        if not message:
            self._json(400, {"error": "message is required"})
            return
        try:
            reply = self.agent.ask(message)
        except Exception as exc:  # noqa: BLE001 — surface to the browser
            self._json(500, {"error": str(exc)})
            return
        self._json(200, {"reply": reply})


def serve(config: BotConfig, host: str = "127.0.0.1", port: int = 8765) -> None:
    agent = Agent(config)
    handler = partial(_Handler, agent)
    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"AnywhereBot chat: http://{host}:{port}")
    print(config.llm.describe())
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        httpd.server_close()
