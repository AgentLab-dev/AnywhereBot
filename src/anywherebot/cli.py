"""Command-line interface: chat, once, doctor, models, serve."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from anywherebot.agent import Agent
from anywherebot.config import BotConfig, ConfigError, find_root
from anywherebot.llm import LLMClient, LLMError
from anywherebot.providers import KEY_HELP, ProviderError

USAGE = """Macha — personal portable assistant

  macha              interactive chat
  macha chat
  macha once "..."
  macha doctor
  macha models
  macha serve [--host 127.0.0.1] [--port 8765]

  python -m macha    same
  anywherebot        compatibility alias
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="macha",
        description="Macha — personal portable assistant. Personality and LLM live in files.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Folder that contains llm.yaml and bot.md (default: walk up from cwd)",
    )
    parser.add_argument(
        "--allow-host",
        action="store_true",
        help="Let file tools leave workspace/",
    )
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("chat", help="Interactive chat (default)")
    once = sub.add_parser("once", help="One shot, then exit")
    once.add_argument("prompt", nargs="+")
    sub.add_parser("doctor", help="Check the free-model path and print what would run")
    sub.add_parser("models", help="List models on the resolved endpoint")
    serve = sub.add_parser("serve", help="Tiny HTML chat UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    return parser


def _load(args: argparse.Namespace) -> BotConfig:
    root = find_root(args.root) if args.root else find_root()
    return BotConfig.load(root, allow_host=args.allow_host)


def cmd_doctor(args: argparse.Namespace) -> int:
    """Probe free endpoints in order. Never crash; print how to get a key if none work."""
    try:
        config = _load(args)
    except (ProviderError, ConfigError) as exc:
        print(str(exc).rstrip(), file=sys.stderr)
        if KEY_HELP.strip() not in str(exc):
            print("\n" + KEY_HELP, file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"doctor could not load config: {exc}", file=sys.stderr)
        print("\n" + KEY_HELP, file=sys.stderr)
        return 1

    llm = config.llm
    print("Macha free-model path")
    print("  1. Ollama on localhost:11434 (or ANYWHEREBOT_BASE_URL)")
    print("  2. OPENROUTER_API_KEY → openrouter/free  (or a pinned :free slug)")
    print("  3. GROQ_API_KEY → openai/gpt-oss-20b")
    print("  4. GEMINI_API_KEY → gemini-3.6-flash")
    print()
    print("OK  " + llm.describe())
    if llm.fallbacks:
        print("    429 fallbacks:")
        for item in llm.fallbacks:
            print(f"      - {item.provider} / {item.model}")
    try:
        ids = LLMClient(llm).list_models()
        preview = ", ".join(ids[:8]) if ids else "(none listed)"
        extra = f" (+{len(ids) - 8} more)" if len(ids) > 8 else ""
        print(f"    models endpoint: {preview}{extra}")
    except LLMError as exc:
        print(f"    models endpoint: not reachable ({exc})")
        if llm.provider != "ollama":
            print("    The key is set; chat may still work. If it 401s, re-copy the key.")
    print()
    print("Paid reminder: z-ai/glm-5.3-flash (ox-alpha) and moonshotai/kimi-k3 are not free.")
    return 0


def cmd_models(args: argparse.Namespace) -> int:
    config = _load(args)
    print(config.llm.describe())
    ids = LLMClient(config.llm).list_models()
    if not ids:
        print("(no models listed)")
        return 0
    for mid in ids:
        print(mid)
    return 0


def cmd_once(args: argparse.Namespace) -> int:
    config = _load(args)
    prompt = " ".join(args.prompt)
    reply = Agent(config).ask(prompt)
    print(reply)
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    config = _load(args)
    agent = Agent(config)
    print("Macha  ·  " + config.llm.describe().split("\n")[0])
    print("Type /reset to start a new session, /exit to quit.")
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line in {"/exit", "/quit"}:
            return 0
        if line == "/reset":
            agent.reset()
            print("(new session)")
            continue
        try:
            reply = agent.ask(line, stream=True, on_token=lambda t: print(t, end="", flush=True))
        except LLMError as exc:
            print(f"llm error: {exc}", file=sys.stderr)
            continue
        if reply and not reply.endswith("\n"):
            print()
        if not reply:
            print()
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from anywherebot.serve import serve

    serve(_load(args), host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {"-h", "--help", "help"}:
        print(USAGE)
        return 0
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    cmd = args.cmd or "chat"
    handlers = {
        "chat": cmd_chat,
        "once": cmd_once,
        "doctor": cmd_doctor,
        "models": cmd_models,
        "serve": cmd_serve,
    }
    try:
        return handlers[cmd](args)
    except (ProviderError, ConfigError) as exc:
        print(str(exc).rstrip(), file=sys.stderr)
        if KEY_HELP.strip() not in str(exc):
            print("\n" + KEY_HELP, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        return 130
    except Exception as exc:  # noqa: BLE001 — CLI must not crash
        print(f"macha: {exc}", file=sys.stderr)
        return 1
