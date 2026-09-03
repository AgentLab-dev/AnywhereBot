# AnywhereBot

A portable standalone AI bot. Personality, skills, and LLM settings are plain files. Clone the folder, point `llm.yaml` at a local or free OpenAI-compatible model, and talk to it. No Cursor, no Vercel, no hosted account.

The bot's "computer" is `workspace/`: it can list, read, write, and edit files there, run a shell with that as cwd, and fetch public URLs.

Default setup is **`provider: auto`**: live FREE hosted models, then local Ollama. No paid plan. This repo does not ship GGUF or safetensors weights.

## Free models (as of 2026-09-03)

`provider: auto` tries endpoints in this order and stops at the first that works:

| Order | When | Default model | Key / URL |
| --- | --- | --- | --- |
| 1 | Ollama answers on `localhost:11434` | `llama3.2` or whatever is already pulled | none |
| 2 | `OPENROUTER_API_KEY` | `openrouter/free` (router picks a $0 model) | [openrouter.ai/keys](https://openrouter.ai/keys) |
| 3 | `GROQ_API_KEY` | `openai/gpt-oss-20b` | [console.groq.com](https://console.groq.com) |
| 4 | `GEMINI_API_KEY` | `gemini-3.6-flash` | [Google AI Studio](https://aistudio.google.com/apikey) |

If none work, `python -m anywherebot doctor` prints a one-screen “get a free key” note and exits `1` (no crash). If OpenRouter returns HTTP 429, chat falls through to Groq then Gemini when those keys exist.

**Paid — do not use as the default.** `ox-alpha` is now `z-ai/glm-5.3-flash` (paid). `moonshotai/kimi-k3` is paid.

Copy-paste `llm.yaml` (this is also the repo default):

```yaml
provider: auto
# Leave model unset so each free backend uses its own default.
timeout_s: 120

# Pin a named OpenRouter :free slug instead of the router:
# provider: openrouter
# model: minimax/minimax-m3:free
# model: nvidia/nemotron-3-ultra-550b-a55b:free
# model: z-ai/glm-5.2:free
# model: thinkingmachines/inkling:free
# model: poolside/laguna-s-2.1:free
# model: cohere/north-mini-code:free
```

Named `:free` slugs above advertised **tools/function calling** and $0 pricing on OpenRouter `GET /api/v1/models` on 2026-09-03. If a slug 404s later, open [openrouter.ai/models?max_price=0](https://openrouter.ai/models?max_price=0) and paste a current `:free` id.

```bash
cp .env.example .env    # set one key if Ollama is not running
python -m anywherebot doctor
python -m anywherebot chat
```

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

With `provider: auto`, a running Ollama wins even if cloud keys are also set.

```bash
python -m anywherebot once "Create workspace/hello.txt with a haiku about USB sticks"
python -m anywherebot models
python -m anywherebot serve    # tiny HTML chat at http://127.0.0.1:8765
```

## Pin Groq or Gemini

Copy `.env.example` to `.env` and set **one** key. You can leave `provider: auto`, or pin:

**Groq** — key from [console.groq.com](https://console.groq.com). Current free/fast tool-capable chat model (`llama-3.3-70b-versatile` was shut down 2026-08-16):

```yaml
provider: groq
model: openai/gpt-oss-20b
```

If that id 404s, run `python -m anywherebot models` and paste a listed id. Other production ids: `openai/gpt-oss-120b`, `qwen/qwen3.6-27b`.

**Gemini** — key from [Google AI Studio](https://aistudio.google.com/apikey). OpenAI-compatible endpoint:

```yaml
provider: gemini
model: gemini-3.6-flash
```

**OpenRouter** — [openrouter.ai/keys](https://openrouter.ai/keys). Prefer the free router or a `:free` slug:

```yaml
provider: openrouter
model: openrouter/free
```

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

For Groq in Docker, set `GROQ_API_KEY` in `.env`. Leave `ANYWHEREBOT_BASE_URL` empty so auto skips Ollama and uses the key.

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
# edit llm.yaml only if you want to pin a provider
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
