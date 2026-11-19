FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
RUN apt-get update && apt-get install -y --no-install-recommends libxcb1 libgl1 libglib2.0-0 libgomp1 fonts-dejavu-core libseccomp2 && rm -rf /var/lib/apt/lists/*
COPY scripts/prepare_ocr.py /tmp/prepare_ocr.py
RUN /app/.venv/bin/python /tmp/prepare_ocr.py && rm /tmp/prepare_ocr.py
COPY scripts/prepare_embeddings.py /tmp/prepare_embeddings.py
RUN /app/.venv/bin/python /tmp/prepare_embeddings.py && chmod -R a+rX /opt/embedding-models && rm /tmp/prepare_embeddings.py
COPY app ./app
COPY scripts/prepare_paddle.py /tmp/prepare_paddle.py
RUN /app/.venv/bin/python /tmp/prepare_paddle.py && chmod -R a+rX /opt/ocr-models && rm /tmp/prepare_paddle.py
COPY scripts/prepare_gitleaks.py /tmp/prepare_gitleaks.py
RUN /app/.venv/bin/python /tmp/prepare_gitleaks.py && rm /tmp/prepare_gitleaks.py
COPY migrations ./migrations
COPY alembic.ini ./
RUN useradd --uid 10001 --create-home app
USER app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
# Explicit target for local ML workloads. The default remains the lightweight base.
FROM base AS neural
USER root
# CPU-only Torch avoids pulling CUDA runtime into the optional ML image.
RUN uv pip install --python /app/.venv/bin/python \
    --index-url https://download.pytorch.org/whl/cpu "torch>=2.4,<3"
RUN uv pip install --python /app/.venv/bin/python \
    "transformers>=4.46,<6" "setfit>=1.1,<2" \
    "datasets>=3,<5" "accelerate>=1,<2" "sentence-transformers>=3,<6"
USER app

FROM base AS final
