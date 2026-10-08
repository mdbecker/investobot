FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
COPY pyproject.toml uv.lock .
RUN uv sync --locked --no-install-project
COPY . .
RUN uv sync --locked
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-m", "invest.web"]
