# Runtime image for the V1.1 FastAPI service. Dependencies are resolved solely
# by uv from the committed lock file; local configuration and model weights are
# provided at runtime and never copied into the image.
FROM python:3.11-slim

WORKDIR /app/backend

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        curl \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Install the package manager from its official image rather than using pip for
# project dependency management.
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/backend/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .

EXPOSE 8888

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl --fail --silent http://localhost:8888/api/health || exit 1

CMD ["uv", "run", "--no-sync", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8888"]
