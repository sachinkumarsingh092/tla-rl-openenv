FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        default-jre-headless \
        curl \
        git && \
    rm -rf /var/lib/apt/lists/*

RUN curl -L -o /opt/tla2tools.jar \
    https://github.com/tlaplus/tlaplus/releases/download/v1.8.0/tla2tools.jar

ENV TLA2TOOLS_JAR=/opt/tla2tools.jar
ENV JAVA_BIN=java

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* /app/env/
WORKDIR /app/env

RUN uv sync --no-install-project --no-editable 2>/dev/null || \
    uv pip install --system openenv-core[core]>=0.2.2

COPY . /app/env

RUN uv sync --no-editable 2>/dev/null || \
    uv pip install --system -e .

ENV PATH="/app/env/.venv/bin:$PATH"
ENV PYTHONPATH="/app/env:$PYTHONPATH"
ENV ENABLE_WEB_INTERFACE=true

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["sh", "-c", "cd /app/env && python -m uvicorn server.app:app --host 0.0.0.0 --port 8000 --ws-ping-interval 60 --ws-ping-timeout 120"]
