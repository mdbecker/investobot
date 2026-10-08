FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
COPY pyproject.toml uv.lock .
RUN uv sync --locked --no-install-project
COPY . .
RUN uv sync --locked
ENV PATH="/opt/venv/bin:$PATH"
CMD ["python", "-m", "invest.web"]
