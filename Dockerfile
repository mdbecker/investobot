FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS vector_builder
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev libsqlite3-dev && rm -rf /var/lib/apt/lists/*
COPY scripts/build_sqlite_vec.py /build_sqlite_vec.py
RUN python /build_sqlite_vec.py

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project
COPY --from=vector_builder /build/vec0.so /opt/investobot/vec0.so
COPY scripts/bake_analytics_runtime.py /opt/investobot/bake_analytics_runtime.py
RUN /opt/venv/bin/python /opt/investobot/bake_analytics_runtime.py
ENV INVEST_ANALYTICS_RUNTIME=/opt/investobot/analytics-runtime.json
COPY . ./
RUN uv sync --locked
ENV PATH="/opt/venv/bin:$PATH"
CMD ["python", "-m", "invest.web"]
