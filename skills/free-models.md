# Free models (as of 2026-09-03)

Macha defaults to live free APIs plus local Ollama. It does not ship model weight files (no GGUF, no safetensors).

## What `provider: auto` picks

1. **Ollama** if `http://127.0.0.1:11434` answers — `llama3.2` or whatever is already pulled.
2. **OpenRouter** if `OPENROUTER_API_KEY` is set — `openrouter/free` (a $0 router that picks a current free model).
3. **Groq** if `GROQ_API_KEY` is set — `openai/gpt-oss-20b` (tool-capable). `llama-3.3-70b-versatile` was shut down 2026-08-16.
4. **Gemini** if `GEMINI_API_KEY` is set — `gemini-3.6-flash` via Google's OpenAI-compatible endpoint.
5. If none of those work, `macha doctor` prints how to get a free key and exits non-zero.

If OpenRouter returns HTTP 429, chat may fall through to Groq then Gemini when those keys exist.

## OpenRouter slugs you can pin

These advertised tools/function calling and $0 pricing on OpenRouter `/api/v1/models` on 2026-09-03:

- `openrouter/free`
- `minimax/minimax-m3:free`
- `nvidia/nemotron-3-ultra-550b-a55b:free`
- `z-ai/glm-5.2:free`
- `thinkingmachines/inkling:free`
- `poolside/laguna-s-2.1:free`
- `cohere/north-mini-code:free`

If a slug 404s later, open https://openrouter.ai/models?max_price=0 and copy a current `:free` id into `llm.yaml`.

## Paid — do not treat as free

- **ox-alpha** is now **`z-ai/glm-5.3-flash`** and is paid.
- **`moonshotai/kimi-k3`** is paid.

Do not default the bot to either of those. Do not claim to be those models.
