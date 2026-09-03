FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE llm.yaml bot.md ./
COPY src ./src
COPY skills ./skills
COPY workspace ./workspace

RUN pip install --no-cache-dir .

EXPOSE 8765

# Interactive `chat` needs a TTY. The local HTML UI is the Docker default.
CMD ["python", "-m", "anywherebot", "serve", "--host", "0.0.0.0", "--port", "8765"]
