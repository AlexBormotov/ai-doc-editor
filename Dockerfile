FROM python:3.12-slim

# LibreOffice (doc -> docx, docx -> pdf, previews) and fonts metric-compatible with the common
# Office fonts (Carlito = Calibri, Caladea = Cambria, Liberation = Arial/Times/Courier), so
# LibreOffice lays out Word documents the way Word does.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-writer-nogui fonts-liberation fonts-crosextra-carlito \
        fonts-crosextra-caladea fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    OLLAMA_BASE_URL=http://host.docker.internal:11434/v1 \
    LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1 \
    RUNS_DIR=/app/runs

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "ai_doc_reader.api:app", "--host", "0.0.0.0", "--port", "8000"]
