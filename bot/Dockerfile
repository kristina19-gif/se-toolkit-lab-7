ARG REGISTRY_PREFIX=harbor.pg.innopolis.university/docker-hub-cache/

FROM ${REGISTRY_PREFIX}astral/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

COPY bot/pyproject.toml bot/uv.lock ./bot/

RUN --mount=type=cache,target=/root/.cache/uv \
    cd /app/bot && uv sync --frozen --no-dev

COPY bot /app/bot

RUN --mount=type=cache,target=/root/.cache/uv \
    cd /app/bot && uv sync --frozen --no-dev

FROM ${REGISTRY_PREFIX}python:3.11-slim-bookworm

WORKDIR /app/bot

COPY --from=builder /app/bot /app/bot

ENV PATH="/app/bot/.venv/bin:${PATH}"

CMD ["python", "bot.py"]
