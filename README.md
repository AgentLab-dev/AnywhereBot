# AnywhereBot

A portable standalone AI bot. Personality, skills, and LLM settings are plain files. Clone the folder, point `llm.yaml` at a local or free OpenAI-compatible model, and talk to it. No Cursor, no Vercel, no hosted account.

The bot's "computer" is `workspace/`: it can list, read, write, and edit files there, run a shell with that as cwd, and fetch public URLs.

## Run locally with Ollama (no API key)

1. Install Python 3.11+ and [Ollama](https://ollama.com).
2. Pull a small chat model (tool calling is better on `llama3.1` than `llama3.2`):

```bash
ollama pull llama3.2
```

3. From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m anywherebot doctor
python -m anywherebot chat
```

`llm.yaml` already targets `http://127.0.0.1:11434/v1`. Ollama ignores the API key.

```bash
python -m anywherebot once "Create workspace/hello.txt with a haiku about USB sticks"
python -m anywherebot models
python -m anywherebot serve    # tiny HTML chat at http://127.0.0.1:8765
```

## Run with a free Groq or Gemini key

Copy `.env.example` to `.env` and set **one** key. Then change `llm.yaml` (no code changes):

**Groq** — key from [console.groq.com](https://console.groq.com). Current free/fast tool-capable chat model (Llama 3.3 70B was shut down 2026-08-16):

```yaml
provider: groq
model: openai/gpt-oss-20b
# base_url and api_key_env default to https://api.groq.com/openai/v1 and GROQ_API_KEY
```

If that id 404s, run `python -m anywherebot models` and paste a listed id. Other production ids: `openai/gpt-oss-120b`, `qwen/qwen3.6-27b`.

**Gemini** — key from [Google AI Studio](https://aistudio.google.com/apikey). OpenAI-compatible endpoint:

```yaml
provider: gemini
model: gemini-3.6-flash
```

**OpenRouter** — [openrouter.ai/keys](https://openrouter.ai/keys). Prefer a free slug:

```yaml
provider: openrouter
model: openrouter/free
```

`provider: auto` tries Ollama on `127.0.0.1:11434`, then the first set env var among `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`. Omit `model:` if you want each provider's default.

## Docker

```bash
cp .env.example .env          # optional; fill a cloud key if you are not using Ollama
docker compose up --build
```

Open http://127.0.0.1:8765. `127.0.0.1` inside the container is not your laptop, so point the bot at Ollama explicitly:

```bash
# Ollama on the host
ANYWHEREBOT_BASE_URL=http://host.docker.internal:11434/v1 docker compose up --build

# Ollama as a sidecar
ANYWHEREBOT_BASE_URL=http://ollama:11434/v1 docker compose --profile ollama up --build
```

For Groq in Docker, set `GROQ_API_KEY` in `.env` and `provider: groq` in `llm.yaml`. Leave `ANYWHEREBOT_BASE_URL` empty.

## Copy the same bot to another machine

The bot **is** the files:

| File | What it is |
| --- | --- |
| `bot.md` | Identity and tone |
| `skills/*.md` | Extra instructions |
| `llm.yaml` | Provider, model, base URL |
| `.env` | API keys (never commit) |
| `workspace/` | The bot's disk |

```bash
git clone <this-repo>
cd <this-repo>
cp .env.example .env          # only if you use a cloud key
# edit llm.yaml if this machine's Ollama/Groq setup differs
pip install -e .
python -m anywherebot doctor
python -m anywherebot chat
```

Same git clone on a Pi or a cheap VPS is enough. Sessions are JSONL under `.anywherebot/sessions/` (gitignored).

## Turn it into a different bot

1. Rewrite `bot.md` — name, job, tone, hard rules.
2. Add `skills/your-skill.md` (see `skills/example-research.md`). `skills/README.md` is not loaded.
3. Restart chat. No Python changes.

`--allow-host` lets file tools leave `workspace/`. `run_shell` is **not** network-jailed; it only sets cwd to `workspace/` and a timeout. Prefer Docker if you need a harder box.

## CLI

```
python -m anywherebot              # interactive chat
python -m anywherebot chat
python -m anywherebot once "..."
python -m anywherebot doctor
python -m anywherebot models
python -m anywherebot serve [--host 127.0.0.1] [--port 8765]
anywherebot                        # same, after pip install
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Tests mock the LLM and HTTP. They do not need network or API keys.

## License

MIT. No telemetry.
