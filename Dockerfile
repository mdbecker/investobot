FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
COPY pyproject.toml .
RUN uv sync --no-install-project
COPY . .
RUN uv sync
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-m", "invest.web"]
